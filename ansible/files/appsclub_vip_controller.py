#!/usr/bin/python3
"""AppsClub VIP reconciler, intended to run on the gateway under systemd.

CTFd Teams / non-shared challenges only. The gateway owns its firewall;
worker access uses an SSH forced command permitting only tightly validated
Kubernetes NetworkPolicy CRUD and read-only resource snapshots.
"""
from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import logging
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

LOG = logging.getLogger("appsclub-vip")
REGEX = re.compile(r"10\.60\.2\.10:(3\d{4})")
IDENT = re.compile(r"[a-f0-9]{16}\Z")
POD_LABEL = "chall-manager.ctfer.io/identity"
MANAGED_LABEL = "appsclub.io/managed-by"
WORKER = "appsclub-sync@10.60.2.10"
SSH_KEY = "/etc/appsclub-vip/worker_ed25519"
KNOWN_HOSTS = "/etc/appsclub-vip/known_hosts"
STATE_DIR = Path("/var/lib/appsclub-vip")
CHAINS = ("ACVIP_FWD", "ACVIP_DNAT", "ACVIP_SNAT")


def run(argv: list[str], *, input_text: str | None = None, timeout: int = 20) -> str:
    proc = subprocess.run(argv, input=input_text, text=True, capture_output=True,
                          check=False, timeout=timeout)
    if proc.returncode:
        raise RuntimeError(f"Command {argv[0]} exited {proc.returncode}: {proc.stderr.strip()[:450]}")
    return proc.stdout


def worker(op: str, data: str | None = None) -> str:
    return run(["/usr/bin/ssh", "-T", "-i", SSH_KEY, "-o", "IdentitiesOnly=yes",
                "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={KNOWN_HOSTS}",
                WORKER, op], input_text=data)


def load_registry(path: Path) -> dict[str, list[str]]:
    raw = json.loads(path.read_text())
    # Dynamic per-device memberships live outside Git/Ansible static seed files.
    # A stale broker roster must NOT keep granting VIP access.
    dynamic_path = Path("/var/lib/appsclub-vip/dynamic-peers.json")
    if dynamic_path.exists():
        import time
        if time.time() - dynamic_path.stat().st_mtime <= 35:
            dynamic = json.loads(dynamic_path.read_text())
            if not isinstance(dynamic, dict):
                raise ValueError("Invalid dynamic VPN roster")
            for team_id, entry in dynamic.items():
                if not isinstance(entry, dict) or not isinstance(entry.get("peers"), list):
                    raise ValueError("Malformed dynamic VPN peer entry")
                if team_id not in raw:
                    raw[team_id] = {"peers": []}
                raw[team_id]["peers"] = raw[team_id].get("peers", []) + entry["peers"]
        else:
            LOG.warning("Ignoring stale dynamic VPN roster (broker stopped)")
    if not isinstance(raw, dict):
        raise ValueError("Missing or empty VPN team registry")
    teams: dict[str, list[str]] = {}
    seen = set()
    for sid, entry in raw.items():
        if not sid.isdecimal() or not 1 <= int(sid) <= 254 or not isinstance(entry, dict):
            raise ValueError(f"Invalid team: {sid}")
        peer_list = entry.get("peers", [])
        if not isinstance(peer_list, list) or not peer_list:
            raise ValueError(f"Missing VPN peers for team {sid}")
        peers = []
        for cidr in peer_list:
            net = ipaddress.ip_network(cidr, strict=True)
            if (net.version != 4 or net.prefixlen != 32 or
                    not net.subnet_of(ipaddress.ip_network("10.77.0.0/24")) or
                    str(net.network_address) in ("10.77.0.1", "10.77.0.2") or
                    str(net) in seen):
                raise ValueError(f"Invalid or duplicated WireGuard peer {cidr}")
            seen.add(str(net)); peers.append(str(net))
        teams[sid] = peers
    return teams


def get_instances(sid: str) -> list[dict]:
    url = f"http://10.60.2.10:31080/api/v1/instance?sourceId={sid}"
    with urllib.request.urlopen(url, timeout=8) as response:
        raw = response.read(1024 * 1024).decode()
    instances = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        item = item.get("result", item)
        if isinstance(item, dict) and "challengeId" in item:
            if str(item.get("sourceId", sid)) != sid:
                raise ValueError(f"sourceId mismatch: expected team {sid}")
            instances.append(item)
    return instances


def snapshot() -> dict:
    result = json.loads(worker("snapshot"))
    if "10.79.0.0/16" not in result.get("worker_allowed_ips", ""):
        raise RuntimeError("Worker peer must route team SNAT range 10.79.0.0/16")
    if not isinstance(result.get("items"), list):
        raise ValueError("Invalid worker resource snapshot")
    return result


def desired(teams: dict, items: list[dict]) -> list[dict]:
    pods = [v for v in items if v.get("kind") == "Pod"]
    svcs = [v for v in items if v.get("kind") == "Service"]
    policies = [v for v in items if v.get("kind") == "NetworkPolicy"]
    protected = {v.get("metadata", {}).get("labels", {}).get(POD_LABEL)
                 for v in policies if v.get("metadata", {}).get("name", "").startswith("emp-ntp-")}
    result = []
    for sid, peers in teams.items():
        for inst in get_instances(sid):
            cid = str(inst["challengeId"])
            if not cid.isdecimal() or not 1 <= int(cid) <= 254:
                raise ValueError(f"Challenge ID outside pilot VIP range: {cid}")
            info = inst.get("connectionInfo", "")
            if not isinstance(info, str):
                raise ValueError(f"Malformed connection info for {sid}/{cid}")
            match = REGEX.search(info)
            if not match:
                LOG.warning("Skipping %s/%s: no private NodePort", sid, cid)
                continue
            port = int(match.group(1))
            matching = [s for s in svcs if any(p.get("nodePort") == port
                         for p in s.get("spec", {}).get("ports", []))]
            if len(matching) != 1:
                LOG.warning("Skipping %s/%s: missing/ambiguous service", sid, cid)
                continue
            svc = matching[0]
            identity = svc.get("metadata", {}).get("labels", {}).get(POD_LABEL, "")
            if not IDENT.fullmatch(identity) or identity not in protected:
                LOG.warning("Skipping %s/%s: missing identity or SDK NetworkPolicy", sid, cid)
                continue
            matching_pods = [p for p in pods if p.get("metadata", {}).get("labels", {}).get(POD_LABEL) == identity
                             and p.get("status", {}).get("phase") == "Running"
                             and p.get("status", {}).get("podIP")
                             and not p.get("metadata", {}).get("deletionTimestamp")
                             and any(c.get("type") == "Ready" and c.get("status") == "True"
                                     for c in p.get("status", {}).get("conditions", []))]
            if len(matching_pods) != 1:
                LOG.warning("Skipping %s/%s: zero or multiple ready Pods", sid, cid)
                continue
            pod_ip = matching_pods[0]["status"]["podIP"]
            if ipaddress.ip_address(pod_ip) not in ipaddress.ip_network("10.42.0.0/24"):
                raise ValueError("Unexpected Pod IP")
            result.append({"team": sid, "challenge": cid, "identity": identity,
                           "vip": f"10.78.{sid}.{cid}", "source_ip": f"10.79.{sid}.1",
                           "pod_ip": pod_ip, "peers": peers})
    if len({x["vip"] for x in result}) != len(result):
        raise ValueError("VIP collision")
    if len({x["pod_ip"] for x in result}) != len(result):
        raise ValueError("A Pod belongs to more than one instance")
    return sorted(result, key=lambda x: (int(x["team"]), int(x["challenge"])))


def policy(x: dict) -> dict:
    return {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
            "metadata": {"name": "appsclub-vip-" + x["identity"],
                         "namespace": "cm-target-daunsoix", "labels": {MANAGED_LABEL: "vip-sync"}},
            "spec": {"podSelector": {"matchLabels": {POD_LABEL: x["identity"]}},
                     "policyTypes": ["Ingress"],
                     "ingress": [{"from": [{"ipBlock": {"cidr": x["source_ip"] + "/32"}}],
                                  "ports": [{"protocol": "TCP"}]}]}}


def ipt(*args: str, table: str = "filter") -> str:
    cmd = ["/usr/sbin/iptables", "-w"]
    if table != "filter":
        cmd += ["-t", table]
    return run(cmd + list(args))


def ensure_chains() -> None:
    for name, table in (("ACVIP_FWD", "filter"), ("ACVIP_DNAT", "nat"), ("ACVIP_SNAT", "nat")):
        try:
            ipt("-N", name, table=table)
        except RuntimeError:
            ipt("-S", name, table=table)  # Existing chain is acceptable.
    for table, parent, options, child in (
        ("filter", "FORWARD", ["-i", "wg0"], "ACVIP_FWD"),
        ("nat", "PREROUTING", ["-i", "wg0"], "ACVIP_DNAT"),
        ("nat", "POSTROUTING", ["-o", "wg0"], "ACVIP_SNAT"),
    ):
        # Keep controller jump before the WireGuard DROP.
        while True:
            try:
                ipt("-D", parent, *options, "-j", child, table=table)
            except RuntimeError:
                break
        ipt("-I", parent, "1", *options, "-j", child, table=table)


def clear_owned() -> None:
    # Fail closed: do not clear Docker, WireGuard or built-in firewall chains.
    for name, table in (("ACVIP_FWD", "filter"), ("ACVIP_DNAT", "nat"), ("ACVIP_SNAT", "nat")):
        try:
            ipt("-F", name, table=table)
        except RuntimeError:
            pass


def legacy_check() -> None:
    forward = ipt("-S", "FORWARD")
    prerouting = ipt("-S", "PREROUTING", table="nat")
    postrouting = ipt("-S", "POSTROUTING", table="nat")
    forbidden = ["CTF_VIP_", "AC_VIP_", "--dport 32667", "--dport 31403"]
    if any(s in (forward + prerouting + postrouting) for s in forbidden):
        raise RuntimeError("Legacy pilot firewall rules are attached; remove them before activation")
    if "-A FORWARD -i wg0 -j DROP" not in forward.splitlines():
        raise RuntimeError("Missing WireGuard deny-all FORWARD rule")


def build_rules(plan: list[dict]) -> list[tuple[str, str, list[str]]]:
    rules: list[tuple[str, str, list[str]]] = []
    for x in plan:
        for peer in x["peers"]:
            rules.extend([
                ("filter", "ACVIP_FWD", ["-i", "wg0", "-o", "wg0", "-s", peer,
                                         "-d", x["pod_ip"] + "/32", "-p", "tcp", "-j", "ACCEPT"]),
                ("filter", "ACVIP_FWD", ["-i", "wg0", "-o", "wg0", "-s", x["pod_ip"] + "/32",
                                         "-d", peer, "-p", "tcp", "-m", "conntrack",
                                         "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"]),
                ("nat", "ACVIP_DNAT", ["-s", peer, "-d", x["vip"] + "/32",
                                          "-p", "tcp", "-j", "DNAT", "--to-destination", x["pod_ip"]]),
                ("nat", "ACVIP_SNAT", ["-s", peer, "-d", x["pod_ip"] + "/32",
                                          "-p", "tcp", "-j", "SNAT", "--to-source", x["source_ip"]]),
            ])
    return rules


def fw_matches(plan: list[dict]) -> bool:
    try:
        forward_lines = [
            line for line in ipt("-S", "FORWARD").splitlines()
            if line.startswith("-A FORWARD ")
        ]
        if not forward_lines or forward_lines[0] != "-A FORWARD -i wg0 -j ACVIP_FWD":
            return False
        for table, parent, options, child in (
            ("filter", "FORWARD", ["-i", "wg0"], "ACVIP_FWD"),
            ("nat", "PREROUTING", ["-i", "wg0"], "ACVIP_DNAT"),
            ("nat", "POSTROUTING", ["-o", "wg0"], "ACVIP_SNAT"),
        ):
            ipt("-C", parent, *options, "-j", child, table=table)
        rules = build_rules(plan)
        for name, table, expected in (("ACVIP_FWD", "filter", 2),
                                      ("ACVIP_DNAT", "nat", 1),
                                      ("ACVIP_SNAT", "nat", 1)):
            output = ipt("-S", name, table=table)
            count = sum(line.startswith("-A " + name + " ") for line in output.splitlines())
            if count != expected * sum(len(x["peers"]) for x in plan):
                return False
        # Check rule semantics, not only counts (a manually changed rule must trigger repair).
        for table, chain, args in rules:
            ipt("-C", chain, *args, table=table)
        return True
    except RuntimeError:
        return False


def apply_firewall(plan: list[dict]) -> None:
    ensure_chains()
    clear_owned()
    for table, chain, args in build_rules(plan):
        ipt("-A", chain, *args, table=table)


def verify_gateway_peers(plan: list[dict]) -> None:
    ips = run(["/usr/bin/wg", "show", "wg0", "allowed-ips"])
    allowed = {v for line in ips.splitlines() for v in line.split()[1:]}
    for x in plan:
        for peer in x["peers"]:
            if peer not in allowed:
                raise RuntimeError(f"VPN peer not installed on gateway: {peer}")


def reconcile(plan: list[dict], resources: list[dict]) -> None:
    verify_gateway_peers(plan)
    legacy_check()
    owned = [p for p in resources if p.get("kind") == "NetworkPolicy"
             and p.get("metadata", {}).get("labels", {}).get(MANAGED_LABEL) == "vip-sync"]
    wanted = {"appsclub-vip-" + x["identity"] for x in plan}
    current_state = STATE_DIR / "last-plan.json"
    same_plan = current_state.exists() and json.loads(current_state.read_text()) == plan
    expected_policies = {"appsclub-vip-" + x["identity"]: policy(x)["spec"] for x in plan}
    same_policies = (
        {p["metadata"]["name"] for p in owned} == wanted
        and all(p.get("spec") == expected_policies.get(p["metadata"]["name"])
                for p in owned)
    )
    if same_plan and same_policies and fw_matches(plan):
        LOG.info("No changes: %s active instance(s)", len(plan))
        return
    # Install policies BEFORE opening firewall. Failed apply -> fail-closed on gateway.
    for x in plan:
        worker("apply", json.dumps(policy(x)))
    apply_firewall(plan)
    # Revoke obsolete policies AFTER the gateway no longer forwards to old Pods.
    for item in owned:
        name = item["metadata"]["name"]
        if name not in wanted:
            if not re.fullmatch(r"appsclub-vip-[a-f0-9]{16}", name):
                raise ValueError("Unexpected managed policy name")
            worker("delete " + name)
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = STATE_DIR / "last-plan.json.tmp"
    temp.write_text(json.dumps(plan, indent=2) + "\n")
    temp.chmod(0o600)
    temp.replace(current_state)
    LOG.info("Applied %s instance(s) with scoped forward/return rules", len(plan))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("/etc/appsclub-vip/vpn-team-peers.json"))
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    with open("/run/lock/appsclub-vip.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        teams = load_registry(options.registry)
        snap = snapshot()
        plan = desired(teams, snap["items"])
        print(json.dumps(plan, indent=2))
        if options.apply:
            reconcile(plan, snap["items"])
        else:
            LOG.info("DRY RUN: no changes made")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        main()
    except Exception as exc:
        LOG.error("Sync failed: %s", exc)
        # Never leave old VIP access in place when current ownership is unknown.
        # Requires root; harmless during an unprivileged dry run.
        if "--apply" in sys.argv:
            clear_owned()
            LOG.error("Cleared controller-owned firewall chains (fail closed)")
        sys.exit(1)

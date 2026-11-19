#!/usr/bin/python3
"""Restricted K3s operations for AppsClub VIP controller.

Only the worker-side SSH forced-command dispatcher should invoke this program
through a dedicated, narrowly scoped sudoers entry. Root-owned, not writable
by the SSH account.
"""
import ipaddress
import json
import re
import subprocess
import sys

NS = "cm-target-daunsoix"
LABEL = "chall-manager.ctfer.io/identity"
MANAGED = "appsclub.io/managed-by"
NAME_RE = re.compile(r"appsclub-vip-([a-f0-9]{16})\Z")
K3S = "/usr/local/bin/k3s"


def kubectl(*args, input_text=None):
    result = subprocess.run(
        [K3S, "kubectl", "-n", NS, *args],
        input=input_text, text=True, capture_output=True, timeout=15, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:500])
    return result.stdout


def validate_policy(obj):
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON object")
    meta = obj.get("metadata", {})
    name = meta.get("name", "")
    match = NAME_RE.fullmatch(name)
    if not match or meta.get("namespace") != NS:
        raise ValueError("Invalid resource name or namespace")
    if obj.get("kind") != "NetworkPolicy" or obj.get("apiVersion") != "networking.k8s.io/v1":
        raise ValueError("Only networking.k8s.io/v1 NetworkPolicy is allowed")
    if meta.get("labels", {}) != {MANAGED: "vip-sync"}:
        raise ValueError("Unexpected labels")
    spec = obj.get("spec")
    if not isinstance(spec, dict) or set(spec) != {"podSelector", "policyTypes", "ingress"}:
        raise ValueError("Unexpected NetworkPolicy fields")
    if spec["podSelector"] != {"matchLabels": {LABEL: match.group(1)}}:
        raise ValueError("Pod selector must be exact identity")
    if spec["policyTypes"] != ["Ingress"]:
        raise ValueError("Only Ingress is allowed")
    ingress = spec["ingress"]
    if not isinstance(ingress, list) or len(ingress) != 1:
        raise ValueError("Expected exactly one ingress rule")
    rule = ingress[0]
    if set(rule) != {"from", "ports"}:
        raise ValueError("Expected one TCP port ingress")
    ports = rule["ports"]
    if (not isinstance(ports, list) or len(ports) != 1 or
            not isinstance(ports[0], dict) or set(ports[0]) != {"protocol", "port"} or
            ports[0]["protocol"] != "TCP" or type(ports[0]["port"]) is not int or
            not 1 <= ports[0]["port"] <= 65535):
        raise ValueError("Expected one numeric TCP port ingress")
    sources = rule["from"]
    if not isinstance(sources, list) or len(sources) != 1:
        raise ValueError("Expected one source identity")
    if not isinstance(sources[0], dict) or set(sources[0]) != {"ipBlock"}:
        raise ValueError("Expected exact ipBlock source")
    cidr = sources[0]["ipBlock"].get("cidr", "")
    ip = ipaddress.ip_network(cidr, strict=True)
    if ip.version != 4 or ip.prefixlen != 32 or ip.network_address.packed[0:2] != bytes([10, 79]):
        raise ValueError("Invalid team SNAT address")
    if not 1 <= ip.network_address.packed[2] <= 254 or ip.network_address.packed[3] != 1:
        raise ValueError("Unexpected SNAT identity format")
    # Strip all optional metadata and let Kubernetes own generated metadata.
    return {"apiVersion": obj["apiVersion"], "kind": obj["kind"],
            "metadata": {"name": name, "namespace": NS, "labels": {MANAGED: "vip-sync"}},
            "spec": spec}


def main():
    command = sys.argv[1:]
    if command == ["snapshot"]:
        items = json.loads(kubectl("get", "pods,svc,networkpolicies", "-o", "json"))["items"]
        wg = subprocess.run(["/usr/bin/wg", "show", "wg0", "allowed-ips"],
                            capture_output=True, text=True, check=True, timeout=5).stdout
        print(json.dumps({"items": items, "worker_allowed_ips": wg}))
    elif command == ["apply"]:
        raw = sys.stdin.read(32768)
        if len(raw) >= 32768:
            raise ValueError("Oversized policy")
        obj = validate_policy(json.loads(raw))
        print(kubectl("apply", "-f", "-", input_text=json.dumps(obj)).strip())
    elif len(command) == 2 and command[0] == "delete":
        name = command[1]
        if not NAME_RE.fullmatch(name):
            raise ValueError("Invalid policy name")
        try:
            obj = json.loads(kubectl("get", "networkpolicy", name, "-o", "json"))
        except RuntimeError as exc:
            if "NotFound" in str(exc) or "not found" in str(exc):
                return
            raise
        if obj.get("metadata", {}).get("labels", {}).get(MANAGED) != "vip-sync":
            raise ValueError("Refusing to delete non-owned policy")
        print(kubectl("delete", "networkpolicy", name, "--ignore-not-found=true").strip())
    else:
        raise ValueError("Unsupported operation")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

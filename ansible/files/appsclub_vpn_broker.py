#!/usr/bin/env python3
"""Gateway-local AppsClub WireGuard self-service broker (Python stdlib only).

The CTFd plugin accesses a credentialed UNIX socket. The broker trusts CTFd's
roster only after re-fetching it from CTFd over localhost with the shared token.
Keys are per device; private keys are generated once and returned once, never
persisted. Every 10 seconds a reconciler restores peers after wg-quick restarts
and revokes peers whose membership/role changed in CTFd.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hmac
import http.server
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import socketserver
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

LOG = logging.getLogger("appsclub-vpn")
DB_PATH = Path(os.environ.get("APPSCLUB_VPN_DB", "/var/lib/appsclub-vpn/peers.sqlite3"))
TOKEN_PATH = Path(os.environ.get("APPSCLUB_VPN_TOKEN", "/etc/appsclub-vpn/broker.token"))
SOCKET = Path(os.environ.get("APPSCLUB_VPN_SOCKET", "/run/appsclub-vpn/broker.sock"))
DYNAMIC = Path(os.environ.get("APPSCLUB_VPN_DYNAMIC", "/var/lib/appsclub-vip/dynamic-peers.json"))
ROSTER_URL = os.environ.get("APPSCLUB_VPN_ROSTER", "http://127.0.0.1:8000/plugins/appsclub-vpn/internal/roster")
WG = "/usr/bin/wg"
MAX_DEVICES_PER_USER = 2
MAX_TEAM_MEMBERS = 4
MAX_BODY = 4096
IP_RANGE = range(100, 255)  # Reserved solely for dynamically allocated user devices
KEY_RE = re.compile(r"[A-Za-z0-9+/]{43}=")


def command(argv: list[str], *, data: str | None = None, timeout: int = 8) -> str:
    proc = subprocess.run(argv, input=data, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"{argv[0]} exited with status {proc.returncode}")
    return proc.stdout.strip()


def read_token() -> str:
    token = TOKEN_PATH.read_text().strip()
    if len(token) < 32:
        raise RuntimeError("Missing/short broker token")
    return token


def get_roster() -> dict[int, int]:
    request = urllib.request.Request(ROSTER_URL, headers={"Authorization": "Bearer " + read_token()})
    with urllib.request.urlopen(request, timeout=5) as response:
        raw = response.read(262144)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("members"), list):
        raise RuntimeError("Invalid CTFd roster")
    roster: dict[int, int] = {}
    sizes: dict[int, int] = {}
    for member in data["members"]:
        if not isinstance(member, dict):
            raise RuntimeError("Malformed roster entry")
        uid, tid = member.get("user_id"), member.get("team_id")
        if type(uid) is not int or type(tid) is not int or uid <= 0 or not 1 <= tid <= 254:
            raise RuntimeError("Invalid team or user ID in roster")
        if uid in roster:
            raise RuntimeError("Duplicate roster user")
        roster[uid] = tid
        sizes[tid] = sizes.get(tid, 0) + 1
    for tid, count in sizes.items():
        if count > MAX_TEAM_MEMBERS:
            # No new VPN access for teams exceeding the competition limit.
            roster = {uid: team for uid, team in roster.items() if team != tid}
    return roster


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, team_id INTEGER NOT NULL,
        ip TEXT NOT NULL UNIQUE, public_key TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL, created_at INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS retired_keys (
        public_key TEXT PRIMARY KEY)""")
    conn.execute("CREATE INDEX IF NOT EXISTS devices_user ON devices(user_id)")
    conn.commit()
    return conn


@contextlib.contextmanager
def exclusive():
    with open("/run/lock/appsclub-vpn.lock", "a", encoding="utf8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def parse_user(obj: dict) -> int:
    uid = obj.get("user_id")
    if type(uid) is not int or uid <= 0:
        raise ValueError("Invalid user")
    return uid


def valid_public_key(key: str) -> bool:
    try:
        return bool(KEY_RE.fullmatch(key) and len(base64.b64decode(key, validate=True)) == 32)
    except (ValueError, base64.binascii.Error):
        return False


def generate_pair() -> tuple[str, str]:
    private = command([WG, "genkey"])
    public = command([WG, "pubkey"], data=private + "\n")
    if not valid_public_key(public):
        raise RuntimeError("Invalid WireGuard public key generated")
    return private, public


def current_gateway_ips() -> set[str]:
    rows = command([WG, "show", "wg0", "allowed-ips"])
    return {ip for row in rows.splitlines() for ip in row.split()[1:]}


def allocate_ip(conn: sqlite3.Connection) -> str:
    used = {row[0] for row in conn.execute("SELECT ip FROM devices")}
    used.update(current_gateway_ips())
    for octet in IP_RANGE:
        address = f"10.77.0.{octet}/32"
        if address not in used:
            return address
    raise RuntimeError("Dynamic VPN address pool exhausted")


def publish_dynamic(conn: sqlite3.Connection) -> None:
    teams: dict[str, dict] = {}
    for team_id, ip in conn.execute("SELECT team_id, ip FROM devices ORDER BY team_id, ip"):
        value = teams.setdefault(str(team_id), {"peers": []})
        value["peers"].append(ip)
    DYNAMIC.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = DYNAMIC.with_name(DYNAMIC.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as handle:
            json.dump(teams, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, DYNAMIC)
    finally:
        temp.unlink(missing_ok=True)


def remove_unknown_dynamic(authorized: set[str]) -> None:
    """All addresses .100-.254 belong exclusively to this broker.

    Remove orphaned peers even after a database restore/reset. Never touch
    the Ansible static peers (.10/.11/.20) or the worker (.2).
    """
    for line in command([WG, "show", "wg0", "allowed-ips"]).splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] in authorized:
            continue
        for address in fields[1:]:
            try:
                net = ipaddress.ip_network(address, strict=True)
            except ValueError:
                continue
            if net.version == 4 and net.prefixlen == 32 and net.network_address in ipaddress.ip_network("10.77.0.0/24") and net.network_address.packed[-1] >= 100:
                command([WG, "set", "wg0", "peer", fields[0], "remove"])
                break


def sync_wg(conn: sqlite3.Connection) -> None:
    """Remove retired/orphaned dynamic keys and ensure authorized devices."""
    active = conn.execute("SELECT public_key, ip FROM devices").fetchall()
    remove_unknown_dynamic({pub for pub, _ in active})
    for (pub,) in conn.execute("SELECT public_key FROM retired_keys"):
        command([WG, "set", "wg0", "peer", pub, "remove"])
    for pub, ip in active:
        command([WG, "set", "wg0", "peer", pub, "allowed-ips", ip])
    # Retired-key rows are kept: when wg-quick replaces peers, we must not
    # accidentally resurrect old keys. Historical list is small at CTF scale.
    publish_dynamic(conn)


def revoke_invalid(conn: sqlite3.Connection, roster: dict[int, int]) -> int:
    entries = conn.execute("SELECT device_id, user_id, team_id, public_key FROM devices").fetchall()
    invalid = [(did, pub) for did, uid, tid, pub in entries if roster.get(uid) != tid]
    with conn:
        for did, pub in invalid:
            conn.execute("INSERT OR IGNORE INTO retired_keys(public_key) VALUES (?)", (pub,))
            conn.execute("DELETE FROM devices WHERE device_id=?", (did,))
    return len(invalid)


def reconcile() -> dict:
    """Live CTFd roster determines active access; fail closed if unavailable."""
    with exclusive():
        conn = connect()
        try:
            try:
                roster = get_roster()
            except Exception:
                # Do not revoke persistent identity during a temporary outage,
                # but remove runtime access and the dynamic VIP registry.
                # Atomically publish an empty registry and remove all dynamic
                # peers before reporting error. Persistent DB remains intact.
                DYNAMIC.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                temp = DYNAMIC.with_name(DYNAMIC.name + ".offline." + secrets.token_hex(8))
                fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w") as handle:
                    handle.write("{}\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, DYNAMIC)
                remove_unknown_dynamic(set())
                raise RuntimeError("CTFd roster unavailable: dynamic VPN access suspended")
            removed = revoke_invalid(conn, roster)
            sync_wg(conn)
            return {"removed": removed, "active": conn.execute("SELECT count(*) FROM devices").fetchone()[0]}
        finally:
            conn.close()


def fetch_valid_user(payload: dict) -> tuple[int, int]:
    uid = parse_user(payload)
    roster = get_roster()
    tid = roster.get(uid)
    if tid is None:
        raise PermissionError("Account has no eligible team")
    return uid, tid


def status(payload: dict) -> dict:
    uid, tid = fetch_valid_user(payload)
    with exclusive():
        conn = connect()
        try:
            rows = conn.execute("SELECT device_id, label, ip FROM devices WHERE user_id=? AND team_id=? ORDER BY created_at", (uid, tid)).fetchall()
            devices = [{"device_id": x, "label": y, "ip": z.removesuffix("/32")} for x, y, z in rows]
            # The controller already authoritatively lists active team/challenge VIPs.
            plans = []
            state = Path("/var/lib/appsclub-vip/last-plan.json")
            if state.exists():
                plans = [p for p in json.loads(state.read_text()) if p.get("team") == str(tid)]
            return {"devices": devices, "team_id": tid, "instances": [
                {"challenge_id": p["challenge"], "vip": p["vip"]} for p in plans]}
        finally:
            conn.close()


def issue(payload: dict) -> dict:
    uid, tid = fetch_valid_user(payload)
    label = payload.get("label", "My device")
    if not isinstance(label, str) or not 1 <= len(label) <= 32 or any(ord(c) < 32 for c in label):
        raise ValueError("Invalid device name")
    with exclusive():
        conn = connect()
        try:
            fresh_roster = get_roster()
            revoke_invalid(conn, fresh_roster)
            if fresh_roster.get(uid) != tid:
                raise PermissionError("Team membership changed during request")
            if conn.execute("SELECT count(*) FROM devices WHERE user_id=?", (uid,)).fetchone()[0] >= MAX_DEVICES_PER_USER:
                raise ValueError("Maximum two VPN devices per player; revoke one first")
            address = allocate_ip(conn)
            private, public = generate_pair()
            did = uuid.uuid4().hex
            with conn:
                conn.execute("INSERT INTO devices VALUES (?,?,?,?,?,?,?)", (did, uid, tid, address, public, label, int(time.time())))
            sync_wg(conn)
            # The server private key never enters a log or the persistent database.
            config = ("[Interface]\nPrivateKey = " + private + "\nAddress = " + address +
                      "\n\n[Peer]\nPublicKey = " + command([WG, "show", "wg0", "public-key"]) +
                      "\nAllowedIPs = 10.77.0.0/24, 10.78.0.0/16\nEndpoint = 158.158.123.197:51820\nPersistentKeepalive = 25\n")
            return {"device_id": did, "ip": address, "config": config}
        finally:
            conn.close()


def revoke(payload: dict) -> dict:
    uid, _ = fetch_valid_user(payload)
    did = payload.get("device_id")
    if not isinstance(did, str) or not re.fullmatch(r"[a-f0-9]{32}", did):
        raise ValueError("Invalid device")
    with exclusive():
        conn = connect()
        try:
            row = conn.execute("SELECT public_key FROM devices WHERE device_id=? AND user_id=?", (did, uid)).fetchone()
            if not row:
                raise ValueError("Device not found")
            with conn:
                conn.execute("INSERT OR IGNORE INTO retired_keys(public_key) VALUES (?)", (row[0],))
                conn.execute("DELETE FROM devices WHERE device_id=? AND user_id=?", (did, uid))
            sync_wg(conn)
            return {"revoked": True}
        finally:
            conn.close()


class BrokerHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Do not log URLs/user IDs or confidential payloads.
        return

    def reply(self, status_code: int, obj: dict) -> None:
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + read_token()):
            return self.reply(403, {"error": "Forbidden"})
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            return self.reply(415, {"error": "Expected JSON"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("Invalid payload length")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Invalid payload")
            if self.path == "/v1/status":
                result = status(payload)
            elif self.path == "/v1/issue":
                result = issue(payload)
            elif self.path == "/v1/revoke":
                result = revoke(payload)
            else:
                return self.reply(404, {"error": "Not found"})
            self.reply(200, result)
        except PermissionError:
            self.reply(403, {"error": "Account not eligible"})
        except ValueError as exc:
            self.reply(400, {"error": str(exc)[:150]})
        except Exception:
            LOG.exception("Broker request failed (content suppressed)")
            self.reply(503, {"error": "VPN provisioner unavailable"})


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve():
    read_token()
    SOCKET.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(SOCKET.parent, 0, 1001)  # CTFd container UID/GID (must be verified)
    SOCKET.parent.chmod(0o750)
    if SOCKET.exists():
        SOCKET.unlink()
    with UnixHTTPServer(str(SOCKET), BrokerHandler) as server:
        os.chown(SOCKET, 0, 1001)
        SOCKET.chmod(0o660)
        LOG.info("VPN UNIX broker ready")
        server.serve_forever(poll_interval=0.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["serve", "reconcile", "check"])
    opt = parser.parse_args()
    if opt.command == "serve":
        serve()
    elif opt.command == "reconcile":
        print(json.dumps(reconcile()))
    elif opt.command == "check":
        with exclusive():
            with connect() as conn:
                print(json.dumps({"db_devices": conn.execute("SELECT count(*) FROM devices").fetchone()[0],
                                  "dynamic_registry": str(DYNAMIC)}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()

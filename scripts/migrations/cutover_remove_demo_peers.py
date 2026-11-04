#!/usr/bin/env python3
"""Explicit one-time cutover from static demo peers to self-service devices.

RUN ONLY AFTER the new profiles have been downloaded and tested by each user.
This is fail-closed and refuses to modify unrecognized/static production peers.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

root = Path.cwd()
p = root / "ansible/templates/wg0.conf.j2"
q = root / "config/wg-extra-peers.json"
r = root / "config/vpn-team-peers.json"
source = p.read_text()
peers = json.loads(q.read_text())
teams = json.loads(r.read_text())
expected = {"10.77.0.10/32", "10.77.0.11/32", "10.77.0.20/32"}
addresses = {peer["address"] for peer in peers}
static = {ip for team in teams.values() for ip in team.get("peers", [])}
if not addresses.issubset(expected - {"10.77.0.10/32"}) or not static.issubset(expected):
    raise SystemExit("STOP: unrecognized static peer; manual review required")
sections = source.split("[Peer]")
matching = [i for i, section in enumerate(sections) if "wg_client_public.stdout" in section]
if len(matching) != 1:
    raise SystemExit("STOP: expected one generated test peer section")
idx = matching[0]
if "{{ wg_client_address }}" not in sections[idx]:
    raise SystemExit("STOP: test peer address was modified")
# Make an explicit backup outside of the Git workspace.
backup = Path(tempfile.mkdtemp(prefix="appsclub-static-peers-backup-", dir="/tmp"))
backup.chmod(0o700)
for path in (p,q,r):
    shutil.copy2(path, backup / path.name)
new = "[Peer]".join(sections[:idx])
if idx + 1 < len(sections):
    new += "[Peer]" + "[Peer]".join(sections[idx+1:])
if source.count("[Peer]") - new.count("[Peer]") != 1:
    raise SystemExit("STOP: peer removal assertion failed")
p.write_text(new)
q.write_text("[]\n")
r.write_text("{}\n")
print("Removed only expected static demo peers. Worker WireGuard peer preserved.")
print("Backups:", backup)
print("NEXT: inspect git diff; then run install-wireguard.yml and deploy-vip-controller.yml")

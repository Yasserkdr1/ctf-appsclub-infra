#!/usr/bin/env python3
"""Safely extend the *existing* AppsClub VIP controller with dynamic peers.

Keep all existing local fixes; replace only the exact legacy registry read line.
"""
from pathlib import Path

path = Path("ansible/files/appsclub_vip_controller.py")
src = path.read_text()
needle = "    raw = json.loads(path.read_text())\n"
patch = '''    raw = json.loads(path.read_text())
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
'''
if "dynamic-peers.json" in src:
    print("ALREADY PATCHED: dynamic VPN roster support")
elif src.count(needle) == 1:
    updated = src.replace(needle, patch, 1)
    guard_old = 'if not isinstance(raw, dict) or not raw:'
    guard_new = 'if not isinstance(raw, dict):'
    if updated.count(guard_old) != 1:
        raise SystemExit("STOP: controller empty-registry guard differs")
    updated = updated.replace(guard_old, guard_new, 1)
    path.write_text(updated)
    print("PATCHED: dynamic roster merged with static Ansible peers, 35s TTL")
else:
    raise SystemExit("STOP: controller code differs; no file modified")

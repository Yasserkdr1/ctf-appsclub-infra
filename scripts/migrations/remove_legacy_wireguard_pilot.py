#!/usr/bin/env python3
"""Remove only the known fixed-NodePort pilot block from the IaC template.

The remote firewall is NOT changed. Re-run install-wireguard.yml to apply.
Stop rather than guess when the template no longer matches the known markers.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
template = root / 'ansible/templates/wg0.conf.j2'
playbook = root / 'ansible/playbooks/install-wireguard.yml'
s = template.read_text()
marker = '# APPSCLUB PILOT VPN ACCESS'
if marker in s:
    start = s.index(marker)
    ends = [i for delim in ('\n# Autoriser uniquement le ping', '\n[Peer]')
            if (i := s.find(delim, start)) >= 0]
    if not ends:
        raise SystemExit('STOP: cannot identify end of pilot block; edit manually')
    end = min(ends)
    fragment = s[start:end]
    if ('wg_challenge_nodeport' not in fragment or
            'wg_challenge_worker_ip' not in fragment or
            'SNAT' not in fragment):
        raise SystemExit('STOP: unknown pilot block, manual review required')
    template.write_text(s[:start].rstrip() + '\n' + s[end:].lstrip('\n'))
    print('Removed fixed-NodePort WireGuard pilot PostUp/PostDown block')
else:
    print('No legacy PostUp block present')

s = playbook.read_text()
lines = [line for line in s.splitlines(keepends=True)
         if not re.match(r'^    (wg_challenge_worker_ip|wg_challenge_nodeport|wg_gateway_private_ip):', line)]
if len(lines) != len(s.splitlines(keepends=True)):
    playbook.write_text(''.join(lines))
    print('Removed unused pilot variables')

#!/usr/bin/env python3
"""Idempotently prepare existing CTFd Dockerfile/Compose without rewriting YAML.

Guards preserve existing database/Redis/Chall-Manager configuration. Review
`git diff` before applying `install-ctfd.yml`.
"""
import re
from pathlib import Path

root = Path("ansible/files/ctfd")
dockerfile = root / "Dockerfile"
compose = root / "compose.yaml"
if not dockerfile.is_file() or not compose.is_file():
    raise SystemExit("STOP: CTFd Dockerfile/compose.yaml not found at expected paths")
if not (root / "appsclub_vpn/__init__.py").is_file():
    raise SystemExit("STOP: plugin directory not installed")

s = dockerfile.read_text()
if "appsclub_vpn" not in s:
    if "FROM " not in s:
        raise SystemExit("STOP: unexpected Dockerfile")
    s = s.rstrip() + "\n\n# AppsClub authenticated player VPN self-service plugin\nCOPY --chown=1001:1001 appsclub_vpn /opt/CTFd/CTFd/plugins/appsclub_vpn\n"
    dockerfile.write_text(s)
    print("UPDATED Dockerfile: bake plugin into CTFd image")
else:
    print("Dockerfile already references AppsClub VPN")

s = compose.read_text()
if "\t" in s:
    raise SystemExit("STOP: unexpected tabs in YAML")
lines = s.splitlines(keepends=True)
start = next((i for i, line in enumerate(lines) if re.fullmatch(r"  ctfd:\s*", line)), -1)
if start < 0:
    raise SystemExit("STOP: expected a service named ctfd")
end = next((i for i in range(start + 1, len(lines))
            if re.match(r"(?:  [A-Za-z0-9_-]+:|[A-Za-z0-9_-]+:)\s*$", lines[i])), len(lines))
service = lines[start:end]
needed = [
    "      - /run/appsclub-vpn:/run/appsclub-vpn:rw\n",
    "      - /etc/appsclub-vpn/broker.token:/run/secrets/appsclub-vpn-token:ro\n",
]
missing = [line for line in needed if line.strip() not in {x.strip() for x in service}]
if missing:
    volumes = next((i for i, line in enumerate(service) if re.fullmatch(r"    volumes:\s*", line)), None)
    if volumes is not None:
        if volumes + 1 < len(service) and service[volumes + 1].startswith("      ") and not service[volumes + 1].lstrip().startswith("-"):
            raise SystemExit("STOP: non-list volumes block; patch manually")
        service[volumes + 1:volumes + 1] = missing
    else:
        service.extend(["    volumes:\n"] + missing)
    lines[start:end] = service
    compose.write_text("".join(lines))
    print("UPDATED compose.yaml: credential and restricted broker socket mounts")
else:
    print("compose.yaml already has AppsClub VPN mounts")
print("REVIEW: git diff -- ansible/files/ctfd/Dockerfile ansible/files/ctfd/compose.yaml")

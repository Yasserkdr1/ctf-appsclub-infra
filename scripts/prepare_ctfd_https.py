#!/usr/bin/env python3
"""Idempotently enable CTFd reverse-proxy awareness for HTTPS ingress."""

from pathlib import Path

repo = Path(__file__).resolve().parent.parent
compose = repo / "ansible/files/ctfd/compose.yaml"
if not compose.is_file():
    raise SystemExit(f"ERROR: missing {compose}")
text = compose.read_text()
if "REVERSE_PROXY:" in text:
    import re
    matches = re.findall(r"(?m)^\s+REVERSE_PROXY:\s*(.*)$", text)
    if len(matches) != 1 or matches[0].strip(' "\'') not in ("True", "true", "1"):
        raise SystemExit("ERROR: inspect existing REVERSE_PROXY setting before continuing")
    print("OK: REVERSE_PROXY already enabled")
else:
    anchor = '      WORKERS: "2"'
    if text.count(anchor) != 1:
        raise SystemExit('ERROR: expected one WORKERS: "2" anchor; inspect compose.yaml')
    text = text.replace(anchor, anchor + '\n      REVERSE_PROXY: "True"', 1)
    compose.write_text(text)
    print(f"UPDATED: {compose.relative_to(repo)}")

if "SERVER_SENT_EVENTS:" in text:
    print("NOTICE: existing SERVER_SENT_EVENTS setting found; preserve it and inspect value")
else:
    print("OK: SERVER_SENT_EVENTS left at CTFd default (not disabled)")

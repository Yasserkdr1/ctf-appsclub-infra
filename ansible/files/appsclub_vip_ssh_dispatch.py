#!/usr/bin/python3
"""SSH authorized_keys forced command: never execute arbitrary client commands."""
import os
import re
import sys

command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
if command in ("snapshot", "apply"):
    args = [command]
elif re.fullmatch(r"delete appsclub-vip-[a-f0-9]{16}", command):
    args = command.split(" ")
else:
    print("Command not allowed", file=sys.stderr)
    sys.exit(1)
os.execv("/usr/bin/sudo", ["sudo", "-n", "/usr/local/sbin/appsclub-vip-k8s", *args])

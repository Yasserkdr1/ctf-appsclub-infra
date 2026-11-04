#!/usr/bin/env python3
import json
import re
import subprocess
import sys

source_id = sys.argv[1] if len(sys.argv) > 1 else "2"

if not source_id.isdigit():
    sys.exit("STOP: source_id must be numeric")

def remote(host, command):
    return subprocess.run(
        ["ssh", host, command],
        capture_output=True,
        text=True,
        check=True
    ).stdout

# 1. Instances belonging to this team
raw = remote(
    "ctf-gateway",
    "curl -fsS --max-time 10 "
    f"'http://10.60.2.10:31080/api/v1/instance?sourceId={source_id}'"
)

instances = []
for line in raw.splitlines():
    if line.strip():
        obj = json.loads(line)
        if "result" in obj:
            instances.append(obj["result"])
        elif "challengeId" in obj:
            instances.append(obj)

# 2. Kubernetes Services and Pods
services = json.loads(remote(
    "ctf-worker",
    "sudo k3s kubectl -n cm-target-daunsoix get svc -o json"
))["items"]

pods = json.loads(remote(
    "ctf-worker",
    "sudo k3s kubectl -n cm-target-daunsoix get pods -o json"
))["items"]

print(f"TEAM SOURCE ID: {source_id}")
print(f"INSTANCES: {len(instances)}")

for inst in instances:
    challenge = inst.get("challengeId")
    connection = inst.get("connectionInfo", "")

    match = re.search(r"10\.60\.2\.10:(\d{4,5})", connection)
    if not match:
        print(f"Challenge {challenge}: unrecognized connection info")
        continue

    nodeport = int(match.group(1))

    matching_services = [
        svc for svc in services
        if any(
            p.get("nodePort") == nodeport
            for p in svc["spec"].get("ports", [])
        )
    ]

    if len(matching_services) != 1:
        print(f"Challenge {challenge}: service not found or ambiguous")
        continue

    svc = matching_services[0]
    identity = svc["metadata"]["labels"].get(
        "chall-manager.ctfer.io/identity"
    )

    matching_pods = [
        pod for pod in pods
        if pod["metadata"]["labels"].get(
            "chall-manager.ctfer.io/identity"
        ) == identity
        and pod["status"].get("phase") == "Running"
    ]

    if len(matching_pods) != 1:
        print(f"Challenge {challenge}: Pod missing or ambiguous")
        continue

    pod_ip = matching_pods[0]["status"]["podIP"]

    print(f"""
CHALLENGE : {challenge}
TEAM      : {source_id}
IDENTITY  : {identity}
NODEPORT  : {nodeport} (internal, not exposed to the player)
POD IP    : {pod_ip}
TARGET VIP: 10.78.1.20 (pilot)
""")

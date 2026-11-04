# AppsClub CTF — VIP controller v2 (gateway-native)

## What this stage does

Runs the already-proven team-to-instance mapping on the **Azure gateway VM** every ~10 seconds, even with WSL closed. The controller queries Chall-Manager v0.6.6 at `10.60.2.10:31080`, joins a non-shared CTFd `sourceId` to its Kubernetes Service NodePort and one ready Pod, and manages `10.78.<team_id>.<challenge_id>` for its team's registered WireGuard peers. Only **actual Pod TCP ports** are reachable. No new WireGuard profile is generated on Start/Stop.

The same registered peers see the instance when **any team member** creates it. Stop/expiry clears firewall mappings and deletes the associated `appsclub-vip-*` NetworkPolicy on the next reconciliation. Unavailable API or worker snapshot triggers a fail-closed removal of **controller-owned** forwarding rules.

This is a controlled test-stage implementation for **CTFd Teams, non-shared challenges, one ready Pod/instance, team IDs 1–254, challenge IDs 1–254, TCP only**, one K3s node. Multi-container workloads, UDP and richer per-target subnet routing need further engineering.

## Security model

- Service runs as root on gateway for `iptables`, with a private SSH key stored only on gateway in `/etc/appsclub-vip`.
- On worker the `appsclub-sync` account accepts only this key from gateway `10.60.1.10`, uses OpenSSH forced command and `restrict`, and cannot run arbitrary SSH commands. Its `sudo` entry launches a root-owned validator limited to reading Pods/Services/NetworkPolicies and applying/deleting **only** narrowly scoped, namespaced, labelled `appsclub-vip-*` NetworkPolicies.
- SSH host key is pinned from the worker host key via Ansible, not blindly accepted from the network.
- The gateway allows `10.77.<player> -> 10.78.<team>.<challenge>` and SNATs to `10.79.<team>.1`. Per-instance Pod NetworkPolicy allows that team identity. Forward and return traffic both require a specific pair of peer and Pod addresses (the earlier unscoped `ESTABLISHED` pilot rule is replaced).
- Existing `ctf-system` admin API, Kubernetes control-plane, Docker and WireGuard deny-all rules are not modified.
- An API failure does **not** result in stale controller mappings remaining intentionally active: it clears controller-owned firewall chains. It cannot automatically revoke stray **legacy** rules from former pilots; audit and remove them before multi-team testing.
- On reboot, iptables rules are initially absent, and systemd timer reconstructs only currently owned instances. The first reconciliation may take a few seconds after boot.

## Install into the main IaC repo

Download `appsclub-vip-autosync-v2.zip` to Windows Downloads, then WSL:

```bash
cd ~/ctf/ctf-appsclub-infra
WIN_HOME="$(powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("UserProfile")' | tr -d '\r')"
unzip -o "$(wslpath -u "$WIN_HOME")/Downloads/appsclub-vip-autosync-v2.zip" -d .
python3 -m py_compile ansible/files/appsclub_vip_controller.py ansible/files/appsclub_vip_k8s.py ansible/files/appsclub_vip_ssh_dispatch.py
python3 -m unittest discover -s tests -p 'test_vip_controller.py' -v
```

### 1. Audit old pilot rules first

```bash
ssh ctf-gateway '
  echo "--- FORWARD ---"
  sudo iptables -S FORWARD
  echo "--- NAT ---"
  sudo iptables -t nat -S PREROUTING
  sudo iptables -t nat -S POSTROUTING
'

grep -nE 'APPSCLUB PILOT|wg_challenge_nodeport|32667|31403|CTF_VIP_' ansible/templates/wg0.conf.j2 ansible/playbooks/install-wireguard.yml || true
ssh ctf-worker 'sudo k3s kubectl -n cm-target-daunsoix get networkpolicy appsclub-vip-pilot --ignore-not-found -o yaml'
```

The package includes a **guarded cleanup** for this specific pilot. Review the diff before any deployment:

```bash
cd ~/ctf/ctf-appsclub-infra
python3 scripts/migrations/remove_legacy_wireguard_pilot.py
git diff -- ansible/templates/wg0.conf.j2 ansible/playbooks/install-wireguard.yml
cd ansible
ansible-playbook -i inventory.ini playbooks/install-wireguard.yml
ansible-playbook -i inventory.ini playbooks/cleanup-vip-pilot.yml
```

`wg-quick` reads the **current** configuration when shutting down; simply deleting the old `PostDown` rules from the template is not sufficient to remove old live firewall exceptions. The cleanup playbook saves `iptables-save` into `/var/backups`, deletes only recognized old gateway pilot rules, and removes `appsclub-vip-pilot` only after verifying its old Pod identity is absent. It never flushes `FORWARD`, `DOCKER-*`, `KUBE-*`, `wg0` deny-all, or new `ACVIP_*` chains. Stop and inspect any unexpected Ansible error. The controller refuses startup when it finds old `CTF_VIP_*` hooks or fixed pilot NodePorts.

### 2. Deploy code and restricted SSH access (timer stays OFF)

```bash
cd ~/ctf/ctf-appsclub-infra/ansible
ansible-playbook -i inventory.ini playbooks/deploy-vip-controller.yml --syntax-check
ansible-playbook -i inventory.ini playbooks/deploy-vip-controller.yml
```

This step is IaC-managed and **does not automatically start the controller**.

### 3. Check secure worker access and dry run

```bash
ssh ctf-gateway 'sudo /usr/bin/python3 /usr/local/libexec/appsclub-vip-controller.py'
```

The output should show Team 2 / challenge 13 while it is active; otherwise an empty array is valid. Inspect the SSH forced command with:

```bash
ssh ctf-gateway 'sudo ssh -T -i /etc/appsclub-vip/worker_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/etc/appsclub-vip/known_hosts appsclub-sync@10.60.2.10 snapshot' | python3 -c 'import json,sys; print("worker resources:",len(json.load(sys.stdin)["items"]))'
```

### 4. Start ONE synchronization and verify

```bash
ssh ctf-gateway 'sudo systemctl start appsclub-vip-sync.service && sudo journalctl -u appsclub-vip-sync.service -n 30 --no-pager'
ssh ctf-gateway 'sudo iptables -S ACVIP_FWD; sudo iptables -t nat -S ACVIP_DNAT'
ssh ctf-worker 'sudo k3s kubectl -n cm-target-daunsoix get networkpolicy -l appsclub.io/managed-by=vip-sync'
```

From Team-Alpha Windows VPN (WireGuard `AllowedIPs` includes `10.78.0.0/16`), with a running Team-Alpha instance:

```powershell
curl.exe --max-time 8 http://10.78.2.13:8000/health
nmap -sT -Pn -p 22,80,443,8000 10.78.2.13
```

Expect HTTP 200 and only the actual `8000/tcp` service open.

### 5. Enable automatic Start/Stop reconciliation

Only after the above preflight succeeds:

```bash
ssh ctf-gateway 'sudo systemctl enable --now appsclub-vip-sync.timer'
ssh ctf-gateway 'systemctl list-timers --all | grep appsclub-vip; sudo journalctl -u appsclub-vip-sync.service -n 25 --no-pager'
```

Use the **CTFd Start and Stop Instance buttons**, no manual `vip_sync.py --apply` on WSL. Wait for the next timer cycle (~10 seconds, plus execution time). Verify both the new VIP access and its loss after Stop. Do not change `AllowedIPs` when a new instance starts.

### 6. Change peer roster

Edit `config/vpn-team-peers.json` in Git; an example for four people in Team 2:

```json
{
  "2": {
    "name": "Team-Alpha",
    "peers": ["10.77.0.10/32", "10.77.0.11/32", "10.77.0.12/32", "10.77.0.13/32"]
  }
}
```

**Only assign a peer after its distinct public key is installed into the gateway WireGuard config by Ansible and its private key has been delivered securely to its owner.** The JSON is *not* a WireGuard key generator or automatic CTFd registration service. Re-run the deploy playbook to upload changed registry. Future work will replace this static roster with an authenticated CTFd plugin/API for per-user device enrollment and revocation.

### 7. Stop service and rollback

```bash
ssh ctf-gateway 'sudo systemctl disable --now appsclub-vip-sync.timer'
```

To immediately deny controller-managed connections without deleting an instance:

```bash
ssh ctf-gateway 'sudo iptables -w -F ACVIP_FWD; sudo iptables -w -t nat -F ACVIP_DNAT; sudo iptables -w -t nat -F ACVIP_SNAT'
```

Remove the timer and units via Ansible after rollback testing, rather than deleting Kubernetes Deployments/instances manually. Stopping the timer alone does **not** remove the most recently applied firewall rules; use the explicit deny command when required.

## Unfinished before public CTF

1. Test two teams, two VPN peers, and cross-team denial with both IPs active; include stale Pod-IP reuse tests.
2. Replace shared/demo key previously exposed in chat and verify a revoked key can no longer connect.
3. Integrate per-device WireGuard key enrollment/revocation into CTFd (no private keys in Git or server-generated shared profiles).
4. Change CTFd's player connection info to show the VIP instead of the internal NodePort, without compromising Chall-Manager internal mapping. Implement and test via the plugin or verified scenario interface.
5. Add HTTPS public entrypoint, backups, resource quotas, audit logs and capacity/load tests. Do not expose port 31080 or Kubernetes API to VPN peers.
6. Keep the current limited VIP format (IDs <=254) or replace it with a real allocator before going beyond that range; multiport TCP works as-is, UDP needs explicit policy and NAT changes.

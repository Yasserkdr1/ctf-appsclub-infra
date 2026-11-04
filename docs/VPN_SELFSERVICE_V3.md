# AppsClub VPN self-service v3 — gateway + CTFd

**Scope:** CTFd 3.8.9, Team mode, Chall-Manager existing VIP controller v2, Azure gateway (10.60.1.10), VPN interface `wg0`. The package installs a new self-service service and plugin; it does **not** replace the proven K3s/NetworkPolicy controller or modify challenge instances. **Current VM deployment has not been performed from this sandbox.**

## Features

- CTFd navbar **My VPN** page for logged-in team players.
- Maximum **4 team members**, maximum **2 different devices** per user. Every device gets its own key pair and `10.77.0.100–254/32` address; old static demo addresses remain for migration only.
- One-time download of a WireGuard `.conf`. The private key is never stored in SQLite/Git/logs; only public-key metadata persists at `/var/lib/appsclub-vpn/peers.sqlite3`.
- Revocation by device and automatic revocation if the user leaves/changes a team or is banned. Membership is read from CTFd directly; each action and a 10-second timer verifies it.
- Dynamic peer state (`/var/lib/appsclub-vip/dynamic-peers.json`) is merged into existing Ansible-managed static registry; Ansible updates **cannot erase** live dynamic registrations.
- Reconciliation restores dynamic peers after a WireGuard interface restart; on roster outage, dynamic access is temporarily suspended (fail closed). Current VIP controller ignores dynamic roster older than 35 seconds.
- Player page lists currently deployed team VIPs from the controller. It does **not** yet modify the Chall-Manager challenge card, which may still show an internal NodePort.

## Security gates

- Generate/download only when CTFd sees an HTTPS request. The local development HTTP bypass exists in source but is **OFF** by default. Do not enable it on an internet-reachable HTTP service. Deploy HTTPS before enabling user private-key downloads for real players.
- Gateway broker binds **only** to UNIX socket `/run/appsclub-vpn/broker.sock`, mode `0660` root:GID1001, and requires a generated bearer token. CTFd container must run as UID/GID **1001**; verify before deploy, do not expose the token over HTTP.
- WireGuard dynamic IP pool `.100–.254` is RESERVED to this broker. Do not assign manual peers from this range. Limit is 155 concurrent device IPs and pilot team/challenge IDs <=254; plan larger allocator if needed.
- Discontinue the Ansible static demo keys (`10.77.0.10`, `.11`, `.20`) **after** registering and testing all users' fresh per-device profiles. Static demo keys do not support automatic team-exit revocation. One old test key was shared previously; it must be revoked before production.
- CTFd must have team-size limit **4** and secure session/cookie settings. Expose only HTTPS/80/443 and WireGuard UDP51820 as needed. Block direct CTFd port8000, Chall-Manager 31080, and K3s API from player networks. Test NodePort bypass denial.

## Safe step-by-step install

Run on WSL from repo root after unpacking:

```bash
cd ~/ctf/ctf-appsclub-infra
python3 -m unittest discover -s tests -p 'test_vpn_broker.py' -v
python3 scripts/patch_vip_controller_for_dynamic_peers.py
python3 scripts/prepare_ctfd_selfservice.py
git diff -- ansible/files/appsclub_vip_controller.py ansible/files/ctfd/Dockerfile ansible/files/ctfd/compose.yaml
```

**Preflight before Docker rebuild:**

```bash
ssh ctf-gateway 'sudo docker exec ctfd-ctfd-1 /opt/venv/bin/python -c "import CTFd,os; print(os.path.dirname(CTFd.__file__)); print(os.getuid(),os.getgid())"'
```

Expected Python package path `/opt/CTFd/CTFd`, process UID/GID `1001`. If not, **STOP** and adapt Dockerfile plugin COPY target, broker socket ownership, and token group to actual values. Dockerfile build context must contain `appsclub_vpn` directory. Confirm with `git diff` and inspect your existing `install-ctfd.yml` before running it.

Deploy broker (keeps the roster timer OFF):

```bash
cd ansible
ansible-playbook -i inventory.ini playbooks/deploy-vpn-selfservice.yml --syntax-check
ansible-playbook -i inventory.ini playbooks/deploy-vpn-selfservice.yml
ansible-playbook -i inventory.ini playbooks/deploy-vip-controller.yml
ssh ctf-gateway 'systemctl is-active appsclub-vpn-broker.service'
```

Deploy CTFd with your existing playbook **only after inspecting that its copy/build context includes the new plugin**:

```bash
ansible-playbook -i inventory.ini playbooks/install-ctfd.yml
ssh ctf-gateway 'sudo docker exec ctfd-ctfd-1 /opt/venv/bin/python -c "import CTFd.plugins.appsclub_vpn; print(\"PLUGIN_IMPORT_OK\")"'
ssh ctf-gateway 'curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/vpn'
```

Expected `/vpn`: 302 for anonymous. Internal roster endpoint: 403 without bearer token. Run the first membership sync and verify:

```bash
ssh ctf-gateway 'sudo systemctl start appsclub-vpn-reconcile.service && sudo systemctl show appsclub-vpn-reconcile.service -p Result -p ExecMainStatus'
```

Only after `Result=success, ExecMainStatus=0`:

```bash
ssh ctf-gateway 'sudo systemctl enable --now appsclub-vpn-reconcile.timer'
ssh ctf-gateway 'systemctl is-active appsclub-vpn-reconcile.timer; systemctl is-active appsclub-vip-sync.timer'
```

### CTFd player UX

- Open `/vpn` as a logged-in user who is a member of a non-banned team.
- Under HTTPS, click **Generate and download VPN**, import the `.conf` into the native WireGuard app, activate.
- Start a challenge; on My VPN see the team VIP, connect to the actual challenge TCP port. The challenge card may still show the internal NodePort until its player-facing template is updated.
- Revoke a device from `/vpn`; the next broker pass verifies bans/moves. There is no per-team VPN sharing key.

### Tests before removal of demo peers

1. Two distinct users in Team-Alpha each get a different `.100+` IP and key; both can reach Alpha VIP and neither Beta VIP.
2. Beta member gets a different key and IP, can reach Beta VIP and not Alpha VIP.
3. Revoke one Alpha device: its handshake and TCP access must fail, second Alpha device must still work.
4. Move a test player to another team or ban them: after the next reconciliation, old key must stop working. Rejoin requires a fresh profile.
5. Stop/expire a challenge: the VIP loses access automatically; restart creates a new pod mapping without changing VPN profiles.
6. Restart `wg-quick@wg0`: after broker reconcile, active `.100+` peers are restored automatically; revoked peers are not.
7. Check player-origin access to `10.60.2.10:31080`, worker API `:6443`, arbitrary NodePorts, and other team's VIP is blocked.
8. Back up the broker SQLite DB **securely** and test restore. Never put private-key config files in Git.

After every user has a working new self-service profile, use the **explicit** `scripts/cutover_remove_demo_peers.py`, inspect its Git diff, deploy `install-wireguard.yml` and `deploy-vip-controller.yml`, then confirm only the worker and `.100+` self-service peers remain. This removes the previously leaked static test key.

## Rollback

Disable only the new membership timer; existing v2 VIP controller remains:

```bash
ssh ctf-gateway 'sudo systemctl disable --now appsclub-vpn-reconcile.timer; sudo systemctl stop appsclub-vpn-broker.service'
```

For emergency access revocation, flush controller-owned firewall chains with the existing v2 runbook, not global Docker/WireGuard chains. Note that stopping the new timer **does not immediately remove existing dynamic WG peers**; use `wg set wg0 peer <public-key> remove` for individual keys, or restart WireGuard after removing dynamic entries from the registry in a controlled migration. The v2 controller will stop authorizing stale dynamic IPs after 35 seconds.

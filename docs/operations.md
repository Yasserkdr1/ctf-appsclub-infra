# AppsClub CTF — Operations runbook

_Last updated from operator observations dated 2026-11-04. Confirm host/IP values against Azure before production._

## Access and main paths

- Main checkout: `~/ctf/ctf-appsclub-infra` (WSL), SSH host aliases `ctf-gateway` and `ctf-worker`.
- Customized Chall-Manager checkout: `~/ctf/chall-manager-appsclub`, Pulumi program under `deploy/`.
- Ansible directory: `~/ctf/ctf-appsclub-infra/ansible`, inventory `inventory.ini`.
- Terraform root: `~/ctf/ctf-appsclub-infra/terraform/environments/test`.
- Public test endpoint: `https://ctf.158.158.123.197.sslip.io` (temporary hostname, to be replaced).
- Local-only CTFd port on gateway: `127.0.0.1:8000`.

## Deploy, in dependency order

1. Azure changes, from `terraform/environments/test`: run `terraform plan` first; apply only reviewed changes. Never run Terraform with local secrets/outputs included in Git.
2. VM base and K3s: `ansible-playbook -i inventory.ini playbooks/prepare.yml` / `install-k3s.yml` **only after inspecting their actual tasks**. Do not blindly rerun destructive bootstrap playbooks.
3. WireGuard: `ansible-playbook -i inventory.ini playbooks/install-wireguard.yml` (may restart `wg0`, briefly interrupting peers).
4. VIP reconciler: `ansible-playbook -i inventory.ini playbooks/deploy-vip-controller.yml`.
5. Per-user VPN broker: `ansible-playbook -i inventory.ini playbooks/deploy-vpn-selfservice.yml`.
6. CTFd container: `ansible-playbook -i inventory.ini playbooks/install-ctfd.yml` (rebuilds CTFd image; keep persistent MariaDB, Redis, uploads).
7. HTTPS proxy: `ansible-playbook -i inventory.ini playbooks/install-caddy.yml`.

Custom Chall-Manager infrastructure is not deployed by the main Ansible playbook. Reconcile it from its pinned Go/Pulumi fork and document the exact Pulumi stack/config in `docs/dependencies.md`. Never apply standalone K3s YAML over the same objects without proving ownership.

## Read-only smoke checks

```bash
ssh ctf-gateway 'sudo docker ps --format "table {{.Names}}\t{{.Status}}"'
ssh ctf-gateway 'systemctl is-active caddy appsclub-vpn-broker.service appsclub-vip-sync.timer appsclub-vpn-reconcile.timer'
ssh ctf-gateway 'sudo iptables -S FORWARD | grep -E "ACVIP_FWD|wg0.*DROP"'
ssh ctf-gateway 'sudo wg show wg0 allowed-ips'
ssh ctf-worker 'sudo k3s kubectl -n ctf-system get deployments,pods'
ssh ctf-worker 'sudo k3s kubectl -n cm-target-daunsoix get networkpolicies,deployments,services,pods'
curl --http2 -sS -o /dev/null -w 'HTTP %{http_code}; protocol %{http_version}\n' https://ctf.158.158.123.197.sslip.io/vpn
```

The order of forwarding rules matters: `-A FORWARD -i wg0 -j ACVIP_FWD` must precede `-A FORWARD -i wg0 -j DROP`. Do not disable the fallback DROP.

## VPN lifecycle validation

- Teams 2 and 3 had separate active challenge VIPs `10.78.2.13` and `10.78.3.13` for challenge 13.
- Players tested distinct profile downloads, cross-team denial, and individual revocation.
- Before a public event, repeat with a newly provisioned account, no manually seeded demo keys, and check that changing CTFd team membership revokes old access.
- Validate that profile downloads are only offered over verified HTTPS and are never logged or committed.
- Do not use client `AllowedIPs` as the access-control boundary; server WireGuard cryptokey routing and firewall/network policies are mandatory.

## Safe orphan-stack cleanup principle

An old `ctf-vibechain` stack with identity `7c65fd6e43675486` was destroyed through Pulumi after a destroy preview showed five resources, and the corresponding Deployment/Service/Pod disappeared. Preserve its history unless there is a documented retention policy. NEVER delete random Pulumi state files or `kubectl delete --all`.

## Restore and change management

- Back up source tree and any secret material in **private encrypted storage**, outside Git.
- Verify `git status` and take a known-good Git commit before invasive edits.
- Exercise a controlled reboot of gateway and worker, checking Caddy, CTFd, WireGuard, timers, broker and Kubernetes after restart.
- Changing the final DNS name requires a Caddy domain/config update and a valid new TLS certificate; it should not require changing the internal WireGuard VIP allocator.

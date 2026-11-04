# AppsClub CTF — Repository architecture

_Last reviewed from the WSL file tree supplied 2026-11-04. This is an inventory, not a substitute for the live source review._

## 1. Deployment overview

- Azure test resource group: `rg-ctf-appsclub-test`, region `spaincentral`.
- Gateway `vm-ctfd-test` (`ctf-gateway`), private `10.60.1.10`, public `158.158.123.197`.
- Worker `vm-worker-test` (`ctf-worker`), private `10.60.2.10`, K3s, no public ingress.
- CTFd 3.8.9, MariaDB 10.11, Redis 7.4, CTFd Chall-Manager plugin 0.10.1.
- Chall-Manager 0.6.6 deployed through its **separate custom Pulumi Go project** at `~/ctf/chall-manager-appsclub/deploy`.
- Caddy terminates HTTPS and provides HTTP/2 to browsers; CTFd listens on `127.0.0.1:8000`.
- WireGuard `wg0`, player CIDR `10.77.0.0/24`, VIP range `10.78.0.0/16`, worker/pod path over VPN.
- Per-team VIP currently follows `10.78.<team_id>.<challenge_id>`, which is a **temporary bounded mapping**, not a scalable IP allocator.
- Dynamic challenge instances deploy to namespace `cm-target-daunsoix`; `ctf-system` hosts Chall-Manager.

## 2. Source of truth

| Location | Purpose | Owner | Policy |
| --- | --- | --- | --- |
| `terraform/` | Azure VNet, NSGs, VMs, IP resources | Terraform | Keep declarative source; never commit local plans/state/credentials |
| `ansible/playbooks/` | VM configuration, Docker, K3s, WireGuard, Caddy, VPN service | Ansible | Keep operational playbooks; isolate legacy pilots |
| `ansible/templates/` | systemd and WireGuard/Caddy templates | Ansible | Keep; no secrets embedded |
| `ansible/files/ctfd/` | Dockerfile, Compose, AppsClub VPN plugin and CTFd Chall-Manager copy | Ansible/Docker | Keep runtime code; document fork/provenance |
| `ansible/files/k3s/` | Earlier K3s bootstrap/security/diagnostic manifests | **To be audited** | Do not delete before checking live Pulumi resources and references |
| `ansible/files/appsclub_vip_*.py` | Gateway VIP reconciler, private worker helper | Ansible/systemd | Keep with tests |
| `ansible/files/appsclub_vpn_broker.py` | Individual WireGuard device broker | Ansible/systemd | Keep with tests |
| `config/` | Currently manually maintained team and extra peer JSON | Pilot/static input | Separate local runtime data from public example files |
| `challenges/vibechain-breach/` | Pilot CTF image + scenario Pulumi source | Challenge repo | Keep; later generalize connection/port metadata |
| `tests/` | Controller and broker regression tests | Python | Keep |
| `docs/` | Architecture/operations/security | Maintainers | Keep |
| `scripts/` | Deployment diagnostics, migrations, pilot utilities | Maintainers | Keep live diagnostics; archive/remove obsolete one-time scripts after review |
| `~/ctf/chall-manager-appsclub/` | **Customized Chall-Manager upstream Go source** | Separate fork | Commit to a fork and pin its version from the main repo |

## 3. Kubernetes ownership: avoid two writers

The target namespace currently has Pulumi-generated `deny-all-*` and `dns-*` policies. Some files in `ansible/files/k3s/` appear to predate the Pulumi deployment. Do not assume they are obsolete by filename alone.

- The legacy Chall-Manager ServiceAccount and RBAC manifests have been removed. Static `ctf-system` resources are defined in `ctf-system-baseline.yaml` and deployed through `bootstrap-ctf-system.yml`; Pulumi owns the active Chall-Manager Deployment and generated ServiceAccount.
- `ctf-system-*.yaml`: inspect whether bootstrapping or Pulumi deploy still uses them.
- `ctf-test-*.yaml`: names suggest historical namespace/config. The actual challenge target is `cm-target-daunsoix`. Legacy ctf-test manifests were removed after verifying no active code references.
- `netcheck.yaml`, `network-probe.yaml`: likely network diagnostics; move to `examples/diagnostics/` or remove only after inspecting contents and references.

A static reference scan is **not proof** a manifest is unused: manual `kubectl apply`, legacy docs, and remote state may still depend on it. Maintain a small table of *bootstrap / Pulumi-owned / diagnostic / retired*.

## 4. Third-party source strategy

**Recommended:** keep `~/ctf/chall-manager-appsclub` as a Git fork of Chall-Manager, retaining its upstream license and complete build context. Commit the deployment customizations there; push to an owned remote; pin the exact fork commit SHA in `docs/dependencies.md` in this infrastructure repo. Optionally add a Git submodule after the fork is published.

Do **not** copy only selected modified Go files into the main repo: `deploy/main.go`, `deploy/services/parts/` and module/import dependencies require the original module structure. Copying scattered files would not make the system reproducible.

The CTFd Chall-Manager plugin already exists as an embedded copy under `ansible/files/ctfd/plugins/ctfd_chall_manager/`. Its AppsClub modifications affect `__init__.py`, `api/instance.py` and `utils/appsclub_connection_info.py`. Retain attribution/license. Avoid deleting its upstream material until its runtime and build dependencies are verified. Later, migrate to a separately pinned plugin fork or a documented patch process.

## 5. Tested and still open

**Tested by user:** TLS/My VPN page, Caddy navigation without former lag, separate WireGuard devices, team isolation, Start/Stop/expiration VIP revocation, post-revoke access denial, node/worker network timeouts, orphan Pulumi stack destroy and cleanup.

**Open before public CTF:** check `/events` explicitly unblocked with HTTP/2 (rather than infer from responsiveness); remove or rotate old demo WireGuard keys, including any previously exposed credentials; test VM reboot, player-team reassignment and rollback; generalize scenario VIP/port mapping; audit leaked/static flags; ensure dynamic VPN data persists across Ansible deployments. Do not treat all these as fully validated.

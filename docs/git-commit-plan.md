# AppsClub CTF — Safe reorganization and meaningful commit plan

This plan assumes the file tree and `git status` pasted on 2026-11-04. **Run audit before staging anything.** Do not manufacture commits merely for a higher count; each commit should represent one independently reviewable change.

## 0. Freeze and back up (no force push)

```bash
cd ~/ctf/ctf-appsclub-infra
mkdir -p ~/ctf/backups
chmod 700 ~/ctf/backups
# A private snapshot of worktree files, including sensitive local config. NEVER upload the archive.
umask 077
tar --exclude='./.git' --exclude='./terraform/environments/test/.terraform' \
    -czf ~/ctf/backups/ctf-appsclub-infra-before-cleanup.tar.gz -C . .
git status --short
git log -5 --oneline --decorate
# Optional safety branch: working-tree changes are NOT captured by branch creation.
git switch -c chore/repository-cleanup
```

Run the read-only audit script before making changes:

```bash
bash scripts/audit-repo.sh | tee ~/ctf/backups/repo-audit.txt
```

## 1. Sensitive and generated files

Review `.gitignore` and use exact patterns rather than broad `config/` exclusions. At minimum, prevent adding `ansible/secrets/ctfd.env`, `ansible/secrets/wireguard/`, `terraform/environments/*/terraform.tfvars`, `terraform/environments/*/backend.tfbackend`, `*.tfplan`, `*.tfstate*`, `**/.terraform/`, `**/__pycache__/`, `**/*.pyc`, `*.bak-*`, `*:Zone.Identifier`.

`config/wg-extra-peers.json` and `config/vpn-team-peers.json` represent **live/test mappings**, and may not be safe/default bootstrap config. Keep the current files locally until migration is understood. Create **sanitized** `*.example.json` files and document how to initialize them; do not commit live static peer registry as a production default. Check existing tracked-file status with `git ls-files` and inspect Git history for committed secrets.

Suggested first commit: `chore(git): ignore local credentials and generated artifacts`.

## 2. Azure and WireGuard foundation

Stage **only** the reviewed changes:

```bash
git add terraform/modules/network/main.tf \
  ansible/playbooks/install-wireguard.yml \
  ansible/templates/wg-client.conf.j2 \
  ansible/templates/wg-worker.conf.j2 \
  ansible/templates/wg0.conf.j2
git diff --cached --check
git diff --cached --stat
git commit -m 'feat(network): secure WireGuard gateway and worker routes'
```

Do not include generated private keys, `.conf` from `ansible/secrets/wireguard`, Terraform plans, or `.tfvars`.

## 3. Automated challenge VIP reconciliation

```bash
git add ansible/files/appsclub_vip_controller.py \
  ansible/files/appsclub_vip_k8s.py \
  ansible/files/appsclub_vip_ssh_dispatch.py \
  ansible/playbooks/deploy-vip-controller.yml \
  ansible/templates/appsclub-vip-sync.service.j2 \
  ansible/templates/appsclub-vip-sync.timer.j2 \
  tests/test_vip_controller.py docs/VIP_CONTROLLER_V2.md
git diff --cached --check
git diff --cached --stat
git commit -m 'feat(vip): reconcile team-scoped access to dynamic pods'
```

Keep the old pilot cleaner/playbook separate as a maintenance commit, after confirming the current production rules do not depend on them.

## 4. WireGuard self-service and membership revocation

```bash
git add ansible/files/appsclub_vpn_broker.py \
  ansible/files/ctfd/appsclub_vpn/ \
  ansible/playbooks/deploy-vpn-selfservice.yml \
  ansible/templates/appsclub-vpn-broker.service.j2 \
  ansible/templates/appsclub-vpn-reconcile.service.j2 \
  ansible/templates/appsclub-vpn-reconcile.timer.j2 \
  tests/test_vpn_broker.py docs/VPN_SELFSERVICE_V3.md
git diff --cached --check
git diff --cached --stat
git commit -m 'feat(vpn): provision and revoke per-device WireGuard peers'
```

Verify the dynamic broker roster is not overwritten by Ansible deployments; review secret handling, TLS guards, revoke behavior and changing teams.

## 5. CTFd integration / VPN-facing challenge addresses

```bash
git add ansible/files/ctfd/.dockerignore \
  ansible/files/ctfd/Dockerfile \
  ansible/files/ctfd/compose.yaml \
  ansible/files/ctfd/plugins/ctfd_chall_manager/__init__.py \
  ansible/files/ctfd/plugins/ctfd_chall_manager/api/instance.py \
  ansible/files/ctfd/plugins/ctfd_chall_manager/utils/appsclub_connection_info.py \
  ansible/playbooks/install-ctfd.yml
git diff --cached --check
git diff --cached --stat
git commit -m 'feat(ctfd): integrate VPN portal and team-facing challenge VIPs'
```

The VIP URL helper is currently specific to challenge ID 13. Mark it as a pilot, not a universal solution.

## 6. HTTPS / Caddy

```bash
git add ansible/playbooks/install-caddy.yml \
  ansible/templates/Caddyfile.j2 \
  scripts/test_https_ctfd.sh
git diff --cached --check
git diff --cached --stat
git commit -m 'feat(https): serve CTFd through Caddy with HTTP2'
```

The deployed temporary hostname uses sslip.io. Document transition to the final DNS and certificate; no domain-specific secret needed in Git.

## 7. Challenge pilot and reproducibility

Review the existing tracked state of `challenges/vibechain-breach/`. Commit actual new changes, not an empty commit. Keep hardening, Dockerfile, Pulumi scenario and relevant tests. Do not commit real challenge flags, keys or built image archives.

Suggested commit if changed: `feat(challenges): document VibeChain Pulumi deployment contract`.

## 8. Legacy/diagnostic files: *review before deletion*

Candidates, not automatic deletions:

- `ansible/files/ctfd/compose.yaml.bak-*`
- `ansible/playbooks/install-ctfd.yml.bak-*`
- `ansible/playbooks/vip-pilot.yml`
- `ansible/files/k3s/netcheck.yaml`, `network-probe.yaml`
- `ansible/files/k3s/ctf-test-*` (verify whether old namespace is still referenced)
- `scripts/patch_vip_controller_for_dynamic_peers.py`, `prepare_ctfd_selfservice.py`, `remove_legacy_wireguard_pilot.py` (one-time migration scripts; preserve in `scripts/migrations/` if still needed)
- `*:Zone.Identifier`, Python bytecode and local `.tfplan`

**Do not remove** `install-k3s.yml`, actual system NetworkPolicies, Pulumi-generated live objects, `ctf-system-*` manifests or RBAC until ownership and live dependencies are proven. For every deletion, inspect `git ls-files`, `grep -R`, the relevant playbook, and live cluster. If a tracked file is retired, use `git rm`; if untracked, remove it manually *after* a private backup.

Suggested commit after review: `chore(cleanup): retire superseded bootstrap and pilot files`.

## 9. Main README, runbooks, dependency pin

Document: architecture, deployment sequence, secrets strategy, CTFd plugin origin, current namespace ownership, known limitations, operations/rollback, test evidence and fork commit SHA.

Suggested commit: `docs: add architecture, operational checks and dependency inventory`.

## 10. Separate Chall-Manager fork

Inside `~/ctf/chall-manager-appsclub`, inspect:

```bash
cd ~/ctf/chall-manager-appsclub
git status --short
git diff --stat
git diff -- deploy
git remote -v
```

The currently customized source includes `deploy/main.go`, `deploy/appsclub-ghcr-egress.go`, and `deploy/services/parts/...`. Preserve the full upstream Go module. Remove `*.bak*` only after source comparison, compile/test (e.g. `go test ./...` as feasible), and a fork commit. Push to an owned fork after verifying the remote and history; **never force-push upstream**.

Good fork commits:

1. `feat(k8s): harden Chall-Manager service and worker RBAC`
2. `fix(network): scope egress for scenario OCI pulls`
3. `docs(deploy): describe AppsClub Pulumi stack and state backend`

Then pin the fork SHA in main repo `docs/dependencies.md`. Add a submodule only if you want reproducible *one-repo checkout* of the full fork; a plain directory copy of a few Go files is insufficient.

## 11. Verification and push

```bash
cd ~/ctf/ctf-appsclub-infra
python3 -m unittest discover -s tests -v
python3 -m compileall -q ansible/files scripts tests
git diff --check
git status --short
git log --oneline --decorate -12
git push -u origin chore/repository-cleanup
```

Open a pull request to `main` and merge after review. If your team does not use PRs, merge the branch locally after checks; never rewrite published history solely to increase commit count.

**Release safety**: a clean worktree does not prove reproducibility. Retest `terraform plan`, Ansible syntax checks and actual CTFd, broker and WireGuard health, especially after changing paths or removing static manifests.

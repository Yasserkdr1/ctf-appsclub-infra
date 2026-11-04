# AppsClub CTF — Dependency/version inventory

Values reflect versions explicitly observed during development; update when you upgrade.

| Component | Version / state | Source of truth |
| --- | --- | --- |
| CTFd | 3.8.9 | `ansible/files/ctfd/Dockerfile` |
| CTFd Chall-Manager plugin | 0.10.1 plus AppsClub modifications | `ansible/files/ctfd/plugins/ctfd_chall_manager/` |
| Chall-Manager server | v0.6.6, deployment customized | `~/ctf/chall-manager-appsclub/deploy` |
| MariaDB | 10.11 | `ansible/files/ctfd/compose.yaml` |
| Redis | 7.4 | `ansible/files/ctfd/compose.yaml` |
| Kubernetes | K3s v1.37.1+k3s1 in development | Worker deployment |
| Azure Terraform provider | 4.81.0 observed in local `.terraform/` path | Terraform lock file |
| Caddy | installed from stable package repository; verify exact installed version | `caddy version` on gateway |
| VibeChain scenario/image | v0.1.0 pilot | `challenges/vibechain-breach/` |

## Customized Chall-Manager Git pin — REQUIRED

- Fork remote: **TODO: confirm private/owned remote after reviewing `git remote -v`**
- Fork branch: **TODO**
- Fork commit SHA: **TODO: `git -C ~/ctf/chall-manager-appsclub rev-parse HEAD` after commits**
- Upstream base tag/SHA: **TODO: verify from fork history**
- Deployment stack name: `test` (verify `deploy/Pulumi.test.yaml`)
- Platform config kept in: `deploy/main.go`, `deploy/services/parts/`, `deploy/appsclub-ghcr-egress.go` (inspect actual diff)

Recommendation: maintain fork as independent Git repository, pin its exact SHA in this document, then optionally use a Git submodule. Do not import the entire fork as a second unversioned directory inside the main infra repo.

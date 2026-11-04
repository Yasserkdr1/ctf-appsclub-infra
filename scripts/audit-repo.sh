#!/usr/bin/env bash
# AppsClub read-only repository audit. Run from the infrastructure checkout.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

section() { printf '\n===== %s =====\n' "$1"; }
section 'MAIN REPOSITORY'
printf 'Root: %s\n' "$PWD"
git branch --show-current
git status --short
git log -5 --oneline --decorate
section 'TRACKED CHANGES'
git diff --stat
git diff --cached --stat
git diff --check
section 'GIT IGNORE STATUS'
if [ -f .gitignore ]; then cat .gitignore; fi
section 'POTENTIALLY TRACKED LOCAL SECRETS (FILENAMES ONLY)'
for item in \
  ansible/secrets/ctfd.env \
  ansible/secrets/wireguard/team-test.conf \
  terraform/environments/test/terraform.tfvars \
  terraform/environments/test/backend.tfbackend \
  terraform/environments/test/wg-nsg.tfplan \
  config/wg-extra-peers.json \
  config/vpn-team-peers.json; do
  if git ls-files --error-unmatch -- "$item" >/dev/null 2>&1; then
    printf 'TRACKED: %s\n' "$item"
  else
    printf 'not tracked: %s\n' "$item"
  fi
done
section 'GENERATED AND BACKUP CANDIDATES (NO DELETION)'
find ansible scripts tests terraform -type f \
  \( -name '*.pyc' -o -name '*.bak*' -o -name '*.tfplan' -o -name '*:Zone.Identifier' \) \
  -not -path '*/.terraform/*' -print | head -80
section 'K3S YAML REFERENCES IN OUR PLAYBOOKS AND SCRIPTS'
shopt -s nullglob
for manifest in ansible/files/k3s/*.yaml ansible/files/k3s/*.yml; do
  name="$(basename "$manifest")"
  printf '\n%s\n' "$manifest"
  found="$(grep -RIlF --include='*.yml' --include='*.yaml' --include='*.j2' --include='*.py' --include='*.sh' \
    -- "$name" ansible/playbooks ansible/templates scripts 2>/dev/null || true)"
  if [ -n "$found" ]; then printf '  referenced by:\n%s\n' "$found"; else printf '  no static reference found (NOT proof of non-use)\n'; fi
done
section 'MAIN REPO SUBMODULES / CHALL-MANAGER DEPENDENCY'
git submodule status || true
fork='../chall-manager-appsclub'
if [ -d "$fork" ]; then
  if git -C "$fork" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'CHALL-MANAGER checkout: %s\n' "$fork"
    git -C "$fork" branch --show-current
    git -C "$fork" status --short
    git -C "$fork" diff --stat
    printf 'Remote names only:\n'
    git -C "$fork" remote
    printf 'Deploy changes:\n'
    git -C "$fork" diff --name-only -- deploy
    printf 'Last commits:\n'
    git -C "$fork" log -3 --oneline || true
  else
    printf 'CHALL-MANAGER folder is not a Git checkout\n'
  fi
else
  printf 'CHALL-MANAGER folder not found at %s\n' "$fork"
fi
section 'ACTIVE DEPLOYMENT FILES'
for item in \
  ansible/playbooks/install-k3s.yml \
  ansible/playbooks/deploy-vip-controller.yml \
  ansible/playbooks/deploy-vpn-selfservice.yml \
  ansible/playbooks/install-ctfd.yml \
  ansible/playbooks/install-caddy.yml \
  terraform/modules/network/main.tf; do
  [ ! -f "$item" ] || printf '%s\n' "$item"
done
section 'END: AUDIT ONLY, NOTHING MODIFIED'

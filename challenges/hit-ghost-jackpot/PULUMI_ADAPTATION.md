# Pulumi / OCI scenario integration — AppsClub CTF

**Do not deploy this challenge by simply importing its ZIP in CTFd.** The ZIP is
only Flask application source. Your current platform's per-team Start/Stop,
WireGuard VIP and Kubernetes network isolation come from a separate Pulumi
scenario executed by Chall-Manager.

## Directory layout in the existing infrastructure repository

```
challenges/hit-ghost-jackpot/
  app/            # files in this prepared bundle
  pulumi/         # COPY and ADAPT from challenges/vibechain-breach/pulumi/
```

From WSL:

```bash
cd ~/ctf/ctf-appsclub-infra
mkdir -p challenges/hit-ghost-jackpot/pulumi
cp -a challenges/vibechain-breach/pulumi/. challenges/hit-ghost-jackpot/pulumi/
```

Use VibeChain's *tested and hardened* `main.go`, `hardening.go`,
`Pulumi.yaml`, `go.mod`, and `go.sum` as the baseline, not a generic
public Kubernetes example.

## Required scenario edits (review individually)

1. Change the container image to:
   `ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot:v0.1.0`.
2. Change the challenge **container port** to TCP `5000` (rather than 8000).
3. Use a unique Pulumi project name and scenario OCI reference:
   `ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot-scenario:v0.1.0`.
4. Pass an instance-specific flag into the container as the `FLAG`
   environment variable. The supplied Flask app now **requires** it.
   It is stored in SQLite by `init_db.py` at container startup.
5. Set the same instance flag in the Chall-Manager scenario response
   (`resp.Flag` or `resp.Flags`, depending on your SDK code), so CTFd verifies
   the actual flag exposed by that team's instance.
6. Supply `SECRET_KEY` as a per-instance, random session-signing key if this
   does not break the intended gameplay. The source application's default is
   predictable; challenge author should confirm whether this is intentional.
7. Preserve Kubernetes non-root/container security, network-default-deny,
   targeted ingress, egress restrictions and identity labels used by the VIP
   controller. Ensure `/tmp` is writable even if the container root FS is read-only.
8. Keep NodePort private: it is for gateway/worker forwarding, not direct player
   access. The player's connection should be displayed as the team VIP.
9. Give the new CTFd challenge its own ID. The existing AppsClub CTFd plugin's
   VIP translation supports only challenge ID 13 today. Extend that mapping
   safely (do **not** show the worker NodePort to players).
10. Test team Alpha and Beta concurrently, cross-team denial, Start/Stop and
    expiration. Confirm the dynamic per-instance flag is distinct for each team.

## Checks before packaging / pushing OCI

```bash
cd ~/ctf/ctf-appsclub-infra/challenges/hit-ghost-jackpot/pulumi
# Inspect the copied scenario: image, port, flag injection, labels, policies.
grep -RniE 'vibechain|ctf-vibechain|8000|FLAG|resp\.Flag|Image|Port' . --include='*.go' --include='*.yaml' | head -90
# Ensure current Go scenario compiles after edits.
go test ./...
```

Use your *already verified* VibeChain scenario packaging and ORAS publication
workflow to create the new OCI scenario. OCI scenario publishing is **not** the
same as `docker push` of the Flask app image. Do not invent or use a registry
reference before pushing the image and scenario successfully.

## CTFd setup

Create a **Chall-Manager / Dynamic IaC** challenge, not the standard ZIP-file
challenge. Set the Web category, scenario OCI URL, sharing=team (when using
team-mode), lifetime/timeout and visibility. First keep it hidden and validate
with test players. Record the generated challenge ID and update the AppsClub
VIP connection-info code to support it; then redeploy the CTFd plugin.

The official Chall-Manager / CTFd plugin supports instance-specific flags,
subject to correct scenario response and environment injection. Do not set a
second independent static flag in CTFd that differs from the running instance.

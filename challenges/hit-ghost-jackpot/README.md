# Hit Ghost Jackpot — AppsClub preparation

Source: the team-supplied `hit_ghost_jackpot.zip` (Flask / SQLite).
This bundle contains the hardened *challenge app* and integration instructions.
**It does not contain a tested, ready-made Pulumi scenario**: adapt your existing
`challenges/vibechain-breach/pulumi` with the checks in `PULUMI_ADAPTATION.md`.

## Corrections made to the supplied app

- Docker now includes `robots.txt` (missing in the upstream Dockerfile).
- Removed the hard-coded production flag fallback from `init_db.py`.
- Removed the hard-coded flag from the local Compose file.
- Added `/health` returning `{"status":"ok"}` for readiness checks.
- Non-root UID 10001, read-only root filesystem and a temporary `/tmp` volume
  in the local Compose configuration.
- Local Compose binds to `127.0.0.1:18001`, not the public interface.
- Kept the intended Flask login, header checks, SQL search, and hidden documents
  unchanged, subject to a challenge-author gameplay review.

**Important:** the base image is `python:3.12-slim` and the supplied package pins
Flask 3.0.3 and Gunicorn 22.0.0. Use strong cluster isolation for deliberately
vulnerable CTF workloads. The intentionally permissive application behavior is
part of the challenge and was not refactored away.

## Local test (WSL with Docker installed)

```bash
cd app
export FLAG='bwctf{local_testing_only_replace_me}'
export SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
docker compose up --build -d
curl -fsS http://127.0.0.1:18001/health
docker compose down
unset FLAG SECRET_KEY
```

The above flag is only an explicit local dummy; do not reuse it for the competition.

## Publish the challenge image (not the scenario)

```bash
cd app
docker build -t ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot:v0.1.0 .
docker push ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot:v0.1.0
```

The image is safe **from the original hardcoded flag**, but publishing still
exposes challenge source code, as is normal for a CTF container image.
Do not embed the secret contest flag in the Docker image.

## Next steps

Read `PULUMI_ADAPTATION.md`. Two independent OCI artifacts are needed:

1. **Runtime Docker image**: `ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot:v0.1.0`
2. **Pulumi scenario OCI**: `ghcr.io/yasserkdr1/ctf-hit-ghost-jackpot-scenario:v0.1.0`

Only after deploying the scenario should you create the Chall-Manager / Dynamic IaC
challenge in CTFd. The new CTFd challenge ID must be accounted for by AppsClub's
VIP connection-info integration, which currently only handles VibeChain ID 13.

# Security and gameplay validation

- [ ] Review challenge author's intended vulnerability chain; do not accidentally patch it.
- [ ] Confirm no production flag is embedded in app.py / init_db.py / Dockerfile / Compose / built image.
- [ ] Provide a fresh, per-instance FLAG and check CTFd accepts the matching response flag.
- [ ] Choose SECRET_KEY behavior intentionally; default value in app.py is predictable.
- [ ] Confirm non-root execution and writable ephemeral /tmp for SQLite.
- [ ] Confirm only TCP/5000 is exposed by the challenge Service.
- [ ] Reject direct Pod, Kubernetes NodePort, worker API and other-team VIP traffic.
- [ ] Confirm Start -> health -> Stop -> VIP timeout -> expiry cleanup.
- [ ] Confirm that public `/robots.txt` and `/secret.txt` paths retain intended challenge clues.
- [ ] Do not start this vulnerable app on the public CTFd gateway.

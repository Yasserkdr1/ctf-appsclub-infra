# AppsClub CTF — Pre-event security review

This is a checklist, not a claim that the platform has passed all production controls.

## Identity and secrets

- [ ] Confirm no `.env`, WireGuard private key, Terraform credentials, Pulumi secrets or scenario flag is tracked in Git or exposed in public history.
- [ ] Rotate the pilot WireGuard private key that was previously pasted into a conversation; remove its old **public** peer from the gateway too.
- [ ] Rotate the VibeChain demo flag: one earlier Kubernetes Deployment YAML output included a FLAG environment variable. Do not reuse that test flag for a real event.
- [ ] Audit CTFd admin accounts, session secrets, API tokens and access rights.
- [ ] Verify registration, team join/leave, disable/ban, device revoke and regenerate across new accounts.

## Network

- [ ] NSG: Internet ingress only approved ports (SSH tightly scoped if possible, WireGuard UDP 51820, HTTP 80, HTTPS 443); no public worker/NodePorts.
- [ ] Gateway: `ACVIP_FWD` before `wg0` deny-all; per-player allow rules; no residual pilot exception.
- [ ] Kubernetes: default-deny and DNS policies active; scoped exceptions created/revoked only by controller.
- [ ] Verify deliberate client routing attempts to private worker, NodePort and direct Pod IP are denied **and that packets actually traversed WireGuard during the tests**.
- [ ] Different users on same team share instances; separate teams cannot access one another; revoked user loses access without affecting teammates.
- [ ] Limit and monitor egress from challenged pods to prevent interaction with cluster/control plane/internal networks.

## HTTPS and browser behavior

- [ ] Verified HTTPS on final domain; HSTS/cookie security reviewed in context of reverse proxy.
- [ ] `/events` not blocked by Chrome DevTools during final rapid-navigation test; pages actually served over HTTP/2 or HTTP/3.
- [ ] Challenge page API never returns internal worker NodePort to players, including after Start/Renew/Restart and in instance lists.

## Reproducibility

- [ ] Main repo references exact committed/pushed customized Chall-Manager fork SHA.
- [ ] K3s manifests have explicit ownership (bootstrap vs Pulumi) and are not applied twice.
- [ ] Full bootstrap from a new checkout works using documented secret initialization.
- [ ] Timers/broker/peer roster recover after restarting the gateway; reboot test is recorded.
- [ ] Keep tests and rollback instructions up-to-date for challenge scenario versions.

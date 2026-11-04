# AppsClub CTF — HTTPS / HTTP2 via Caddy (2026-11-04)

Purpose: deploy Caddy as TLS ingress to an existing CTFd service listening on `127.0.0.1:8000`, preserve SSE `/events`, and run a real HTTP/2 navigation test.

## Files

- `ansible/playbooks/install-caddy.yml`: idempotent Ansible package/repository, TLS configuration and service
- `ansible/templates/Caddyfile.j2`: Caddy vhost for temporary sslip.io DNS
- `scripts/prepare_ctfd_https.py`: safely enables CTFd's `REVERSE_PROXY` environment setting; never disables SSE
- `scripts/test_https_ctfd.sh`: TLS, HTTP/2, logs and manual browser test instructions

## Deployment from WSL (in repository root)

First verify Azure NSG rules 80 and 443 are actually Inbound Allow TCP, and the DNS matches the gateway public IP. No Terraform edits are needed if the existing rules are correct.

```bash
python3 scripts/prepare_ctfd_https.py
cd ansible
ansible-playbook -i inventory.ini playbooks/install-ctfd.yml
ansible-playbook -i inventory.ini playbooks/install-caddy.yml --syntax-check
ansible-playbook -i inventory.ini playbooks/install-caddy.yml
cd ..
bash scripts/test_https_ctfd.sh
```

`curl` must validate the public TLS certificate (`ssl_verify_result=0`) and ideally report `http_version=2`. CTFd `/vpn` returns a 302 for unauthenticated clients. Chrome must **stop blocking `/events`** before benchmarking. HTTP/2 is expected to prevent the previous browser HTTP/1.1 connection-pool saturation; this needs measurement, it is not assumed proven.

Caddy automatically flushes `text/event-stream` (SSE); do not force `flush_interval -1` or disable `SERVER_SENT_EVENTS` preemptively.

## Security caveats

- Publishing ports 80/443 makes CTFd internet-facing. Keep the contest in TEST mode, review CTFd accounts and admin settings and avoid real user keys until validation is complete.
- Only the gateway should be internet-exposed. Never open TCP 8000, worker NodePorts or the Chall-Manager management API.
- sslip.io is a third-party shared domain; certificate issuance may be rate-limited by the issuing CA. Later replace `ctf_domain` in the playbook with your real DNS name.
- Rotate any previously exposed WireGuard client key before the public contest.
- Verify `git diff`, commit nonsecret files, and keep `ansible/secrets/ctfd.env` out of Git.
- On a failed certificate request, inspect `journalctl -u caddy`; do not use `curl -k` as a success test.

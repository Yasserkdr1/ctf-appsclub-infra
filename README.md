# AppsClub CTF Platform

Infrastructure as Code for a team-based CTF platform deployed on Microsoft Azure.

## Architecture

Internet -> Caddy (HTTPS/HTTP2) -> CTFd -> Chall-Manager
                                              |
                                        Worker K3s
                                              |
                                      Pulumi scenarios
                                              |
                                      Isolated challenges

Players connect through individual WireGuard VPN profiles.
Gateway firewall rules and Kubernetes NetworkPolicies enforce
per-team isolation.

## Technology stack

| Component | Technology |
|---|---|
| Cloud | Microsoft Azure |
| Infrastructure | Terraform |
| Configuration | Ansible |
| CTF platform | CTFd 3.8.9 |
| Challenge manager | Chall-Manager 0.6.6 |
| Container orchestration | K3s |
| Challenge deployment | Pulumi |
| VPN | WireGuard |
| HTTPS | Caddy / HTTP2 |
| Database | MariaDB |
| Cache | Redis |

## Repository layout

- terraform/ - Azure infrastructure and networking
- ansible/ - Server configuration and deployments
- ansible/files/k3s/ - Static Kubernetes security resources
- ansible/files/ctfd/ - CTFd image, Compose and plugins
- challenges/ - CTF scenarios and container images
- config/ - VPN configuration examples
- scripts/ - Operational and migration tools
- tests/ - Automated tests
- docs/ - Architecture and operational documentation
- external/chall-manager/ - Pinned custom Chall-Manager submodule

## Clone

Clone with submodules:

    git clone --recurse-submodules git@github.com:Yasserkdr1/ctf-appsclub-infra.git

For an existing clone:

    git submodule update --init --recursive

The Chall-Manager fork must be accessible to the operator.

## Infrastructure

Terraform environment: terraform/environments/test/

Create local configuration from the provided examples.
Review Azure subscription, backend, SSH keys and network settings.

Validate infrastructure:

    terraform -chdir=terraform/environments/test validate

Review Terraform plans before applying.

## Deployment with Ansible

Ansible inventory: ansible/inventory.ini

Main playbooks:

- install-docker.yml
- install-k3s.yml
- install-wireguard.yml
- bootstrap-ctf-system.yml
- install-ctfd.yml
- deploy-vip-controller.yml
- deploy-vpn-selfservice.yml
- install-caddy.yml

Some playbooks require local secrets and configuration excluded from Git.

The Kubernetes bootstrap validates manifests by default.
Actual deployment requires explicit approval.

The full fresh-install sequence still requires end-to-end verification,
including deployment of the pinned Chall-Manager fork.

## Challenge management

Chall-Manager provisions isolated Kubernetes challenge instances
using Pulumi.

Tested scenario: challenges/vibechain-breach/

Each team accesses its own instance through a virtual IP over
WireGuard. Cross-team isolation has been functionally tested.

The CTFd VIP connection-info mapping currently supports the
VibeChain challenge specifically and needs generalization.

## Self-service VPN

Authenticated CTFd users can generate, download and revoke
individual WireGuard device profiles over HTTPS.

The gateway broker manages device peers, while the VIP controller
enforces team-scoped access.

## Security

Never commit passwords, private keys, VPN profiles or tokens.
Keep the Kubernetes API and Chall-Manager management API private.
Preserve default-deny policies and firewall restrictions.

Before a public competition, complete credential rotation,
recovery testing, security review and concurrent load testing.

## Tests

Python:

    python3 -m unittest discover -s tests -p 'test_*.py' -v

Terraform:

    terraform -chdir=terraform/environments/test validate

Ansible playbooks should pass syntax checks before deployment.

## Documentation

- [Architecture](docs/repository-architecture.md)
- [Operations](docs/operations.md)
- [Security](docs/security-review.md)
- [Dependencies](docs/dependencies.md)
- [Kubernetes bootstrap](docs/KUBERNETES_BOOTSTRAP.md)
- [VIP controller](docs/VIP_CONTROLLER_V2.md)
- [VPN self-service](docs/VPN_SELFSERVICE_V3.md)
- [HTTPS and Caddy](docs/HTTPS_CADDY.md)

## Project status

Azure infrastructure, HTTPS, WireGuard self-service,
dynamic challenge deployment and team isolation have been
functionally tested.

Production readiness and a fully reproducible fresh installation
remain subject to final validation.

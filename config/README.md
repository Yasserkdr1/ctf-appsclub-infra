# AppsClub VPN configuration

## wg-extra-peers.json

Local configuration used by the Ansible WireGuard playbook.

It contains a JSON array of additional static WireGuard peers.

Each entry has:
- address: client tunnel address in CIDR notation
- public_key: WireGuard public key

An empty array (`[]`) means no additional static peers.

For a fresh deployment:

    cp config/wg-extra-peers.json.example config/wg-extra-peers.json

Do not overwrite the existing JSON on a running deployment.

The real file is excluded from Git.

## vpn-team-peers.json

Legacy/static team-to-peer mapping used by the VIP controller.

This file is also excluded from Git. Its exact schema and
remaining dependencies must be documented before cleanup.

## Security

Never commit WireGuard private keys, client profiles,
broker tokens, or real credentials.

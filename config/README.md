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

## Static VIP team roster example

The VIP controller loads `vpn-team-peers.json` during
deployment to configure static player-to-team mappings.

For a fresh installation, copy the example and adapt it:

    cp config/vpn-team-peers.json.example config/vpn-team-peers.json

The example contains no real WireGuard peer keys.

The self-service VPN broker maintains additional dynamic peers.

Do not overwrite the existing roster on a running deployment,
as doing so can interrupt player access.

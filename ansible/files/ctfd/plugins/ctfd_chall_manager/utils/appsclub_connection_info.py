"""Player-facing VPN addresses for AppsClub challenges."""

def player_vip(challenge_id, team_id, connection_info):
    # Preserve hidden or unavailable challenge information.
    if connection_info in (None, "", "hidden", "unavailable"):
        return connection_info

    # Only VibeChain is configured for this pilot mapping.
    if str(challenge_id) != "13":
        return connection_info

    try:
        team = int(team_id)
    except (TypeError, ValueError):
        return "VPN address unavailable"

    if not 1 <= team <= 254:
        return "VPN address unavailable"

    return f"http://10.78.{team}.13:8000"

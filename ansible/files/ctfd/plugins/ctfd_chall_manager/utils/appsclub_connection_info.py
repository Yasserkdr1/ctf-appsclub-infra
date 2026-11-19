"""Player-facing, fail-closed VIP display for non-shared AppsClub challenges."""
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

ACTIVE_MAP = Path("/run/appsclub-vip-public/active-vips.json")
UNAVAILABLE = "VPN address unavailable"
MAX_AGE = 60  # Gateway sync timer normally runs about every 10 seconds.


def player_vip(challenge_id, team_id, connection_info):
    if connection_info in (None, "", "hidden", "unavailable"):
        return connection_info
    try:
        team, challenge = int(team_id), int(challenge_id)
        if not (1 <= team <= 254 and 1 <= challenge <= 254):
            return UNAVAILABLE
        upstream = urlsplit(connection_info)
        if upstream.scheme != "http" or upstream.hostname != "10.60.2.10":
            return UNAVAILABLE
        upstream_port = upstream.port
        if upstream_port is None:
            return UNAVAILABLE
        with ACTIVE_MAP.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if data.get("version") != 1:
            return UNAVAILABLE
        age = time.time() - data["updated_at"]
        if not 0 <= age <= MAX_AGE:
            return UNAVAILABLE
        route = data["routes"].get(f"{team}/{challenge}")
        if not isinstance(route, dict) or route.get("node_port") != upstream_port:
            return UNAVAILABLE
        app_port = route.get("app_port")
        if type(app_port) is not int or not 1 <= app_port <= 65535:
            return UNAVAILABLE
        return f"http://10.78.{team}.{challenge}:{app_port}"
    except (TypeError, ValueError, KeyError, OSError, AttributeError):
        return UNAVAILABLE

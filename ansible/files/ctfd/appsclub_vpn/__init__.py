"""AppsClub CTFd 3.8.9 self-service WireGuard page.

This plugin never runs wg or iptables and never stores a WireGuard private
key. Privileged operations are delegated over a credentialed local UNIX socket.
"""
import hmac
import http.client
import json
import os
import socket
from pathlib import Path

from flask import Response, abort, redirect, render_template_string, request
from CTFd.models import Teams, Users
from CTFd.plugins import register_user_page_menu_bar
from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user, get_current_team

BROKER_SOCKET = "/run/appsclub-vpn/broker.sock"
TOKEN_FILE = "/run/secrets/appsclub-vpn-token"

PAGE = """
{% extends "base.html" %}
{% block content %}
<div class="container py-5">
  <h1>My VPN</h1>
  <p>One unique WireGuard profile per device. All team members can access the same active team instances.</p>
  {% if error %}<div class="alert alert-danger" role="alert">{{ error }}</div>{% endif %}
  {% if info %}<div class="alert alert-info" role="status">{{ info }}</div>{% endif %}
  {% if not team %}
    <p>Join a team before creating a VPN profile.</p>
  {% elif not status %}
    <p>VPN provisioning is temporarily unavailable. Contact an administrator.</p>
  {% else %}
    <h3>Team {{ status.team_id }}</h3>
    <h4>My devices ({{ status.devices | length }}/2)</h4>
    <table class="table"><thead><tr><th>Device</th><th>VPN IP</th><th>Action</th></tr></thead><tbody>
    {% for device in status.devices %}
    <tr><td>{{ device.label }}</td><td><code>{{ device.ip }}</code></td><td>
      <form method="post" action="/vpn/revoke">
        <input type="hidden" name="nonce" value="{{ Session.nonce }}">
        <input type="hidden" name="device_id" value="{{ device.device_id }}">
        <button class="btn btn-outline-danger btn-sm" type="submit">Revoke device</button>
      </form>
    </td></tr>
    {% else %}<tr><td colspan="3">No VPN device registered</td></tr>{% endfor %}
    </tbody></table>
    {% if secure_delivery and status.devices | length < 2 %}
      <form method="post" action="/vpn/download" class="my-3">
        <input type="hidden" name="nonce" value="{{ Session.nonce }}">
        <label for="device-name">Device name</label>
        <input class="form-control" id="device-name" name="label" maxlength="32" required value="My computer">
        <button class="btn btn-primary my-2" type="submit">Generate and download VPN</button>
      </form>
      <p class="small">The private key is delivered only once. Keep the downloaded .conf file safe.</p>
    {% elif not secure_delivery %}
      <div class="alert alert-warning">VPN profile download is locked until HTTPS is enabled.</div>
    {% endif %}
    <h4>My team's active challenge IPs</h4>
    <table class="table"><thead><tr><th>Challenge ID</th><th>Private VIP</th></tr></thead><tbody>
    {% for instance in status.instances %}
      <tr><td>{{ instance.challenge_id }}</td><td><code>{{ instance.vip }}</code></td></tr>
    {% else %}<tr><td colspan="2">No currently active instance</td></tr>{% endfor %}
    </tbody></table>
    <p></p>
  {% endif %}
</div>
{% endblock %}
"""


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str):
        super().__init__(host="localhost", port=80, timeout=8)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def broker(action: str, payload: dict) -> dict:
    token = Path(TOKEN_FILE).read_text().strip()
    if len(token) < 32:
        raise RuntimeError("Invalid broker credential")
    conn = UnixConnection(BROKER_SOCKET)
    try:
        conn.request("POST", "/v1/" + action, body=json.dumps(payload).encode(), headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        })
        result = conn.getresponse()
        body = result.read(65536)
        data = json.loads(body)
        if result.status != 200:
            raise RuntimeError(data.get("error", "VPN request rejected"))
        return data
    finally:
        conn.close()


def current_identity():
    if not is_teams_mode():
        abort(403, "Team mode required")
    user = get_current_user()
    team = get_current_team()
    if user is None or team is None or user.banned or team.banned or user.team_id != team.id or user.type != "user":
        abort(403, "Join an eligible team")
    if not 1 <= team.id <= 254:
        abort(403, "Team ID exceeds pilot VPN range")
    return user, team


def secure_delivery() -> bool:
    # Never enable local-dev bypass when CTFd is reachable unencrypted from the internet.
    if request.is_secure:
        return True
    return os.getenv("APPSCLUB_VPN_INSECURE_LOCAL_DEV", "0") == "1" and request.host.split(":")[0] in ("localhost", "127.0.0.1")


def load(app):
    register_user_page_menu_bar("My VPN", "/vpn")

    @app.route("/plugins/appsclub-vpn/internal/roster", methods=["GET"])
    def appsclub_vpn_roster():
        expected = "Bearer " + Path(TOKEN_FILE).read_text().strip()
        if not hmac.compare_digest(request.headers.get("Authorization", ""), expected):
            abort(403)
        valid_teams = {t.id for t in Teams.query.filter_by(banned=False).all() if 1 <= t.id <= 254}
        members = [{"user_id": u.id, "team_id": u.team_id}
                   for u in Users.query.filter_by(type="user", banned=False).all()
                   if u.team_id in valid_teams]
        response = Response(json.dumps({"members": members}), mimetype="application/json")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/vpn", methods=["GET"])
    @authed_only
    def appsclub_vpn_page():
        try:
            user, team = current_identity()
        except Exception:
            return render_template_string(PAGE, team=False, status=None, error=None, info=None, secure_delivery=False)
        try:
            data = broker("status", {"user_id": user.id})
            error = None
        except Exception:
            data, error = None, "VPN service unavailable"
        response = Response(render_template_string(PAGE, team=team, status=data, error=error,
                                                   info=None, secure_delivery=secure_delivery()))
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/vpn/download", methods=["POST"])
    @authed_only
    def appsclub_vpn_download():
        user, _ = current_identity()
        if not secure_delivery():
            abort(403, "HTTPS required for WireGuard private-key delivery")
        label = request.form.get("label", "My device")
        try:
            result = broker("issue", {"user_id": user.id, "label": label})
        except (RuntimeError, OSError) as exc:
            return render_template_string(PAGE, team=True, status=None, error=str(exc), info=None, secure_delivery=True), 503
        response = Response(result["config"], mimetype="application/octet-stream")
        response.headers["Content-Disposition"] = f'attachment; filename="appsclub-u{user.id}-{result["device_id"][:8]}.conf"'
        response.headers["Cache-Control"] = "no-store, no-cache, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.route("/vpn/revoke", methods=["POST"])
    @authed_only
    def appsclub_vpn_revoke():
        user, _ = current_identity()
        broker("revoke", {"user_id": user.id, "device_id": request.form.get("device_id", "")})
        return redirect("/vpn", code=303)

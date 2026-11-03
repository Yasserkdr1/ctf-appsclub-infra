import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

INTERNAL_LIB_NAME = os.environ.get("INTERNAL_LIB_NAME", "vibe_metrics_core")
OPS_JWT_SECRET = os.environ.get("OPS_JWT_SECRET", "ops-dev-secret-2026")
OPS_PROFILE = "ops-cache-jwt-v1"
INCIDENT_REF = hashlib.sha1(f"{INTERNAL_LIB_NAME}:{OPS_JWT_SECRET}".encode()).hexdigest()[:12]
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "900"))
FLAG_VALUE = os.environ.get("FLAG", "NO_FLAG")

SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", "/tmp/ops_sessions"))
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

CLEANUP_INTERVAL_SECONDS = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "60"))
CLEANUP_MAX_FILES = int(os.environ.get("CLEANUP_MAX_FILES", "2000"))
_LAST_CLEANUP_AT = 0.0

INDEX_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>VibeStart Dashboard</title>
    <style>
      :root {
        --bg0: #0b0f1a;
        --bg1: #111a2e;
        --card: rgba(255, 255, 255, 0.08);
        --stroke: rgba(255, 255, 255, 0.12);
        --text: rgba(255, 255, 255, 0.92);
        --muted: rgba(255, 255, 255, 0.62);
        --accent: #7cf6c4;
        --accent2: #6aa6ff;
      }

      * { box-sizing: border-box; }
      body {
        margin: 0;
        color: var(--text);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        background:
          radial-gradient(900px 500px at 20% 10%, rgba(122, 165, 255, 0.25), transparent 60%),
          radial-gradient(800px 500px at 80% 25%, rgba(124, 246, 196, 0.18), transparent 60%),
          linear-gradient(180deg, var(--bg0), var(--bg1));
        min-height: 100vh;
      }

      .wrap { max-width: 980px; margin: 0 auto; padding: 28px 18px 48px; }
      .top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
      .brand { font-weight: 800; letter-spacing: 0.5px; }
      .tag { color: var(--muted); font-size: 12px; }
      .grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 16px; margin-top: 18px; }
      .card {
        border: 1px solid var(--stroke);
        background: var(--card);
        backdrop-filter: blur(10px);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
      }
      h1, h2 { margin: 0 0 10px; }
      h1 { font-size: 22px; }
      h2 { font-size: 16px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
      p { margin: 8px 0; color: var(--muted); line-height: 1.45; }
      .status { display: inline-flex; align-items: center; gap: 8px; color: var(--text); }
      .dot { width: 10px; height: 10px; border-radius: 20px; background: var(--accent); box-shadow: 0 0 0 4px rgba(124, 246, 196, 0.14); }
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin-top: 10px;
        padding: 10px 14px;
        border-radius: 12px;
        border: 1px solid rgba(124, 246, 196, 0.35);
        background: linear-gradient(180deg, rgba(124, 246, 196, 0.18), rgba(124, 246, 196, 0.06));
        color: var(--text);
        text-decoration: none;
        font-weight: 700;
      }
      .btn:hover { border-color: rgba(124, 246, 196, 0.55); }
      .muted { color: var(--muted); }
      .kv { display: grid; grid-template-columns: 110px 1fr; gap: 6px 10px; margin-top: 10px; }
      .k { color: rgba(255,255,255,0.55); }
      .v { color: rgba(255,255,255,0.88); }

      @media (max-width: 860px) {
        .grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="top">
        <div class="brand">VibeStart</div>
        <div class="tag">vibe-dashboard / prod</div>
      </div>

      <div class="grid">
        <div class="card">
          <h1>Metrics Console</h1>
          <div class="status"><span class="dot"></span><span>Service online</span></div>
          <p>Viewer loads real-time vibe metrics. If you see failures, report the incident reference to on-call.</p>
          <a class="btn" href="/metrics">Open metrics viewer</a>

          <div class="kv">
            <div class="k">Component</div><div class="v">vibe-metrics</div>
            <div class="k">Pipeline</div><div class="v">VibeChain (hotfix enabled)</div>
            <div class="k">Region</div><div class="v">edge-01</div>
          </div>
        </div>

        <div class="card">
          <h2>Change Log</h2>
          <p><span class="muted">2026.02</span> Quick recovery automation shipped.</p>
          <p><span class="muted">2026.02</span> Incident responder flow integrated.</p>
          <p><span class="muted">2026.02</span> Cache acceleration profile enabled.</p>
        </div>
      </div>
    </div>
  </body>
</html>
"""

ERROR_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Vibe Failure</title>
    <style>
      :root {
        --bg0: #0b0f1a;
        --bg1: #111a2e;
        --card: rgba(255, 255, 255, 0.08);
        --stroke: rgba(255, 255, 255, 0.12);
        --text: rgba(255, 255, 255, 0.92);
        --muted: rgba(255, 255, 255, 0.62);
        --warn: #ffcf6a;
        --accent: #6aa6ff;
      }

      * { box-sizing: border-box; }
      body {
        margin: 0;
        color: var(--text);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        background:
          radial-gradient(800px 500px at 20% 10%, rgba(255, 207, 106, 0.18), transparent 60%),
          radial-gradient(900px 500px at 80% 35%, rgba(106, 166, 255, 0.22), transparent 60%),
          linear-gradient(180deg, var(--bg0), var(--bg1));
        min-height: 100vh;
      }

      .wrap { max-width: 980px; margin: 0 auto; padding: 28px 18px 48px; }
      .brand { display: inline-block; color: var(--text); text-decoration: none; font-weight: 800; letter-spacing: 0.5px; }
      .card {
        margin-top: 16px;
        border: 1px solid var(--stroke);
        background: var(--card);
        backdrop-filter: blur(10px);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
      }
      h2 { margin: 0 0 10px; font-size: 20px; }
      p { margin: 8px 0; color: var(--muted); line-height: 1.45; }
      b { color: rgba(255,255,255,0.92); }
      code { color: var(--warn); }
      .tools { margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.10); }
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 10px 14px;
        border-radius: 12px;
        border: 1px solid rgba(106, 166, 255, 0.40);
        background: linear-gradient(180deg, rgba(106, 166, 255, 0.16), rgba(106, 166, 255, 0.06));
        color: var(--text);
        text-decoration: none;
        font-weight: 700;
      }
      .btn:hover { border-color: rgba(106, 166, 255, 0.62); }
      .tiny { font-size: 12px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <a class="brand" href="/">VibeStart</a>
      <div class="card">
        <h2>Critical vibe failure</h2>
        <p>Could not load internal dependency.</p>
        <p>Incident Ref: <code>{{ incident_ref }}</code></p>
        <p>Recovery profile: {{ profile }}</p>

        <div class="tools">
          <p class="tiny">Client telemetry:</p>
          <p class="tiny">Incident pipeline: <code id="pipe">queued</code></p>
          <p class="tiny">The dashboard client attempts to notify on-call automatically.</p>
        </div>
      </div>
    </div>

    <script>
      (function () {
        var pipe = document.getElementById("pipe");
        var ref = "{{ incident_ref }}";
        var prefix = atob("L2FwaS9vcHMvcmVwb3J0Lw==");
        var url = prefix + ref + "?v=" + String(Date.now());

        setTimeout(function () {
          fetch(url, { credentials: "same-origin" })
            .then(function (r) {
              if (pipe) { pipe.textContent = r.ok ? "sent" : ("error " + r.status); }
              return r.text();
            })
            .catch(function () {
              if (pipe) { pipe.textContent = "offline"; }
            });
        }, 250);
      })();
    </script>
  </body>
</html>
"""


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def extract_bearer_token(raw_auth_header: str) -> str:
    value = raw_auth_header.strip()
    if not value.startswith("Bearer "):
        return ""
    return value.split(" ", 1)[1].strip()


def extract_scopes(raw_scope) -> list[str]:
    if isinstance(raw_scope, str):
        return [raw_scope]
    if isinstance(raw_scope, list):
        return [str(item) for item in raw_scope]
    return []


def session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def is_valid_session_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-f0-9]{32}", value))


def issue_ops_ticket(incident_ref: str, module_name: str, session_id: str) -> str:
    header = {"typ": "JWT", "alg": "HS256"}
    now = int(time.time())
    payload = {
        "sub": "ops-reader",
        "scope": ["cache:read"],
        "incident_ref": incident_ref,
        "module": module_name,
        "jti": session_id,
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }

    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    to_sign = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(OPS_JWT_SECRET.encode("utf-8"), to_sign, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{b64url_encode(signature)}"


def verify_ops_ticket(ticket: str):
    parts = ticket.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token format")

    header_raw, payload_raw, signature_raw = parts
    try:
        header = json.loads(b64url_decode(header_raw).decode("utf-8"))
        payload = json.loads(b64url_decode(payload_raw).decode("utf-8"))
    except Exception as err:
        raise ValueError("malformed token") from err

    alg = str(header.get("alg", ""))
    signing_input = f"{header_raw}.{payload_raw}".encode("ascii")

    # Intentional vulnerability: "alg:none" bypass accepts unsigned payload.
    if alg == "none":
        pass
    elif alg == "HS256":
        expected_signature = hmac.new(
            OPS_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        provided_signature = b64url_decode(signature_raw)
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise ValueError("invalid signature")
    else:
        raise ValueError("unsupported alg")

    exp = int(payload.get("exp", 0))
    if exp < int(time.time()):
        raise ValueError("token expired")

    return payload


def create_session(session_id: str) -> None:
    now = time.time()
    payload = {"expires": now + float(SESSION_TTL_SECONDS)}
    session_path(session_id).write_text(json.dumps(payload), encoding="utf-8")


def read_session_expires(session_id: str) -> float:
    raw = session_path(session_id).read_text(encoding="utf-8")
    obj = json.loads(raw)
    return float(obj.get("expires", 0.0))


def consume_session(session_id: str) -> bool:
    src = session_path(session_id)
    dst = SESSIONS_DIR / f"{session_id}.used"
    try:
        os.replace(src, dst)
    except FileNotFoundError:
        return False
    except Exception:
        return False

    try:
        dst.unlink(missing_ok=True)
    except Exception:
        pass
    return True


def cleanup_expired_sessions() -> None:
    global _LAST_CLEANUP_AT

    now = time.time()
    if (now - _LAST_CLEANUP_AT) < float(CLEANUP_INTERVAL_SECONDS):
        return
    _LAST_CLEANUP_AT = now

    try:
        scanned = 0
        for path in SESSIONS_DIR.glob("*.json"):
            if scanned >= CLEANUP_MAX_FILES:
                break
            scanned += 1
            try:
                raw = path.read_text(encoding="utf-8")
                obj = json.loads(raw)
                if float(obj.get("expires", 0.0)) < now:
                    path.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        return


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.get("/")
def index():
    return render_template_string(INDEX_TEMPLATE)


@app.get("/metrics")
def metrics():
    return (
        render_template_string(
            ERROR_TEMPLATE,
            incident_ref=INCIDENT_REF,
            profile=OPS_PROFILE,
        ),
        500,
    )


@app.get("/api/ops/report/<incident_ref>")
def ops_report(incident_ref: str):
    if incident_ref != INCIDENT_REF:
        return jsonify({"error": "incident not found"}), 404

    cleanup_expired_sessions()

    session_id = uuid4().hex
    create_session(session_id)
    ticket = issue_ops_ticket(incident_ref, INTERNAL_LIB_NAME, session_id)
    return (
        jsonify(
            {
                "incident_ref": incident_ref,
                "profile": OPS_PROFILE,
                "upload_path": "/api/ops/cache/upload",
                "token_type": "JWT",
                "auth_scheme": "Bearer",
                "ticket": ticket,
            }
        ),
        200,
    )


@app.post("/api/ops/cache/upload")
def ops_cache_upload():
    ticket = extract_bearer_token(request.headers.get("Authorization", ""))
    if not ticket:
        return jsonify({"error": "bearer token required"}), 401

    cleanup_expired_sessions()

    try:
        claims = verify_ops_ticket(ticket)
    except Exception as err:
        return jsonify({"error": f"invalid ticket: {err}"}), 403

    if str(claims.get("incident_ref", "")) != INCIDENT_REF:
        return jsonify({"error": "incident mismatch"}), 403

    if str(claims.get("module", "")) != INTERNAL_LIB_NAME:
        return jsonify({"error": "module mismatch"}), 403

    session_id = str(claims.get("jti", "")).strip()
    if not is_valid_session_id(session_id):
        return jsonify({"error": "invalid session id"}), 403

    try:
        expires = read_session_expires(session_id)
    except FileNotFoundError:
        return jsonify({"error": "session expired or not found"}), 403
    except Exception:
        return jsonify({"error": "session read failed"}), 500

    if expires < time.time():
        try:
            session_path(session_id).unlink(missing_ok=True)
        except Exception:
            pass
        return jsonify({"error": "session expired or not found"}), 403

    scopes = extract_scopes(claims.get("scope", []))
    if "cache:write" not in scopes:
        return jsonify({"error": "scope required: cache:write"}), 403

    uploaded = request.files.get("package")
    if uploaded is None or uploaded.filename == "":
        return jsonify({"error": "file field 'package' is required"}), 400

    filename = uploaded.filename.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}\.py", filename):
        return jsonify({"error": "invalid module filename"}), 400

    expected_filename = f"{INTERNAL_LIB_NAME}.py"
    if filename != expected_filename:
        return jsonify({"error": "unexpected module name", "expected": expected_filename}), 400

    payload = uploaded.read()
    if len(payload) > 4096:
        return jsonify({"error": "file is too large"}), 400

    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"error": "use UTF-8 encoded source"}), 400

    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", decoded):
        return jsonify({"error": "invalid control characters"}), 400

    if "def calculate_score" not in decoded:
        return jsonify({"error": "hotfix must define calculate_score()"}), 400

    # One-shot: only the first valid upload per session returns the flag.
    if not consume_session(session_id):
        return jsonify({"error": "session expired or not found"}), 403

    return jsonify({"status": "applied", "flag": FLAG_VALUE}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

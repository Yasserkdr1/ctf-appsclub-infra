import hashlib
import os
import sqlite3

from flask import Flask, Response, jsonify, make_response, request, session

DB_PATH = os.environ.get("DB_PATH", "/tmp/portal.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "acme-portal-dev-key")

BASE = os.path.dirname(os.path.abspath(__file__))


def read_or(filename, fallback):
    try:
        with open(os.path.join(BASE, filename), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return fallback


LOGIN_PAGE = read_or("login.html", "<h1>Acme Corp</h1><p>login page missing</p>")
INDEX_PAGE = read_or("index.html", "<h1>Acme Corp</h1><p>portal page missing</p>")
ROBOTS = read_or("robots.txt", "User-agent: *\nDisallow: /secret.txt\nDisallow: /admin\n")
SECRET = read_or("secret.txt", "try hard\n")


def db():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


@app.after_request
def add_headers(resp):
    resp.headers["Server"] = "AcmeGateway/2.3"
    return resp


@app.route("/")
def index():
    if "user" not in session:
        return make_response(LOGIN_PAGE)
    return make_response(INDEX_PAGE)


@app.route("/robots.txt")
def robots_txt():
    return Response(ROBOTS, mimetype="text/plain")


@app.route("/secret.txt")
def secret_txt():
    return Response(SECRET, mimetype="text/plain")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if data is None:
        data = request.form
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    if not username or not password:
        return jsonify(error="missing username or password"), 400

    row = db().execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return jsonify(error="there is no user named " + username), 401
    if row["password_hash"] != hashlib.md5(password.encode()).hexdigest():
        return jsonify(error="wrong pass for " + username), 401

    session.clear()
    session["user"] = row["username"]
    session["role"] = row["role"]
    return jsonify(ok=True, username=row["username"], role=row["role"])


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(ok=True)


@app.route("/api/me")
def me():
    if "user" not in session:
        return jsonify(error="unauthorized"), 401
    return jsonify(username=session["user"], role=session.get("role"))


def check_access():
    if "user" not in session:
        return jsonify(error="unauthorized", detail="sign in first"), 401
    if request.headers.get("X-Internal-User") != "hackari":
        return jsonify(error="forbidden", detail="internal users only"), 403
    return None


@app.route("/api/products")
def products():
    denied = check_access()
    if denied:
        return denied
    rows = db().execute(
        "SELECT id, name, description, price, category FROM products ORDER BY id"
    ).fetchall()
    return jsonify(count=len(rows), results=[dict(r) for r in rows])


@app.route("/api/categories")
def categories():
    denied = check_access()
    if denied:
        return denied
    rows = db().execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return jsonify(categories=[r["category"] for r in rows])


@app.route("/api/search")
def search():
    denied = check_access()
    if denied:
        return denied

    q = request.args.get("q", "")
    category = request.args.get("category", "")
    if category:
        sql = (
            "SELECT id, name, description, price, category FROM products "
            f"WHERE category = '{category}' AND name LIKE '%{q}%'"
        )
    else:
        sql = (
            "SELECT id, name, description, price, category FROM products "
            f"WHERE name LIKE '%{q}%'"
        )
    try:
        rows = db().execute(sql).fetchall()
    except sqlite3.Error as e:
        return jsonify(error="database error", detail=str(e)), 500
    return jsonify(count=len(rows), results=[dict(r) for r in rows])


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.errorhandler(404)
def nf(_):
    return jsonify(error="not found"), 404

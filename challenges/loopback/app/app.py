import os
from flask import Flask, request, jsonify, make_response

HERE = os.path.dirname(os.path.abspath(__file__))
FLAG = os.environ["FLAG"]

app = Flask(__name__, static_folder=None)

# Public order data -- tracking works for everyone, no auth, just flavor.
ORDERS = {
    "ORD-1000": {"customer": "John Smith",   "status": "In transit", "eta": "2026-11-08"},
    "ORD-1017": {"customer": "Maria Lopez",  "status": "Delivered",  "eta": "2026-11-02"},
    "ORD-1042": {"customer": "Alice Nguyen", "status": "Delivered",  "eta": "2026-11-01"},
    "ORD-1055": {"customer": "David Cohen",  "status": "Processing", "eta": "2026-11-12"},
}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


INDEX = read("index.html")
DISPATCH_PAGE = read("dispatch.html")
ROBOTS_TXT = read("robots.txt")


@app.route("/style.css")
def stylesheet():
    response = make_response(read("style.css"))
    response.headers["Content-Type"] = "text/css; charset=utf-8"
    return response


@app.route("/")
def index():
    return make_response(INDEX)


@app.route("/dispatch")
def dispatch_page():
    return make_response(DISPATCH_PAGE)


@app.route("/api/whoami")
def whoami():
    # Reflects whatever the server sees as the caller's address. The
    # dispatch page uses this to fill X-Source-IP on its own request --
    # it's just telling the truth about who's asking, nothing malicious.
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return jsonify(ip=ip)


@app.route("/robots.txt")
def robots():
    resp = make_response(ROBOTS_TXT)
    resp.headers["Content-Type"] = "text/plain"
    return resp


@app.route("/api/track")
def track():
    order_id = request.args.get("order", "").strip().upper()
    order = ORDERS.get(order_id)
    if order is None:
        return jsonify(error="not found", detail="no order with that number"), 404
    return jsonify(order=order_id, **order)


@app.route("/api/dispatch")
def dispatch():
    # Step 1: a required header is missing entirely.
    if request.headers.get("X-Is-staff", "").lower() != "true":
        return jsonify(error="forbidden", detail="sorry you are not staff"), 400

    # Step 2: present but the request isn't "from" the internal network.
    # The backend trusts whatever IP the client claims here -- it never
    # checks the real source of the request.
    source_ip = request.headers.get("X-Source-IP")
    if source_ip is None:
        return jsonify(error="forbidden", detail="missing X-Source-IP header"), 400
    if source_ip != "127.0.0.1":
        return jsonify(error="forbidden", detail="request must come from the internal network"), 403

    return jsonify(status="ok", board="internal dispatch", notes=FLAG)


@app.errorhandler(404)
def nf(_):
    return jsonify(error="not found"), 404

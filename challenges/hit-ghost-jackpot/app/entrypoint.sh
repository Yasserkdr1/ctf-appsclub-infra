#!/bin/sh
set -eu

# Generate a fresh signing key once per container start unless supplied by
# the operator. All Gunicorn workers inherit the same key.
if [ -z "${SECRET_KEY:-}" ]; then
    SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
    export SECRET_KEY
fi

python init_db.py
exec gunicorn -w 2 -b 0.0.0.0:5000 app:app

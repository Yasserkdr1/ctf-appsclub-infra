# Stage 1: Install Python dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install \
       --no-cache-dir \
       --disable-pip-version-check \
       -r requirements.txt


# Stage 2: Minimal runtime
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

RUN groupadd --gid 10001 ctf \
    && useradd --uid 10001 --gid 10001 \
       --no-create-home --shell /usr/sbin/nologin ctf

COPY --chown=10001:10001 \
    app.py init_db.py index.html login.html \
    secret.txt robots.txt entrypoint.sh ./

RUN chmod 0755 /app/entrypoint.sh

USER 10001:10001

EXPOSE 5000

HEALTHCHECK --interval=5s \
            --timeout=2s \
            --start-period=15s \
            --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=1).close()" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

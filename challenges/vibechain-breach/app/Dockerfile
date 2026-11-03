FROM python:3.11.8-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CACHE_DIR=/tmp/package_cache \
    INTERNAL_LIB_NAME=vibe_metrics_core

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN useradd -m -u 10001 ctf

COPY --chown=10001:10001 --chmod=0644 app.py /app/app.py

USER ctf

EXPOSE 8000

ENV GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=8 \
    GUNICORN_TIMEOUT=10

CMD ["sh", "-c", "gunicorn -w ${GUNICORN_WORKERS} -k gthread --threads ${GUNICORN_THREADS} --timeout ${GUNICORN_TIMEOUT} -b 0.0.0.0:8000 app:app"]

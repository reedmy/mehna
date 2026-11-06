#!/bin/sh
set -e

echo "→ Applying database migrations…"
flask --app wsgi.py db upgrade

echo "→ Starting gunicorn on :8000"
exec gunicorn \
  --workers "${WEB_CONCURRENCY:-3}" \
  --threads 4 \
  --timeout 60 \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  wsgi:app

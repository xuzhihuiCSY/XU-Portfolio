#!/bin/sh
set -e

if [ "${DB_ENGINE:-sqlite}" = "postgres" ] || [ "${DB_ENGINE:-sqlite}" = "postgresql" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
  python - <<'PY'
import os
import time
import psycopg

host = os.getenv("POSTGRES_HOST", "db")
port = int(os.getenv("POSTGRES_PORT", "5432"))
user = os.getenv("POSTGRES_USER", "xu_portfolio")
password = os.getenv("POSTGRES_PASSWORD", "change-me")
dbname = os.getenv("POSTGRES_DB", "xu_portfolio")

for i in range(60):
    try:
        conn = psycopg.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        conn.close()
        print("PostgreSQL is ready")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("PostgreSQL did not become ready in time")
PY
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers ${GUNICORN_WORKERS:-2} \
  --timeout ${GUNICORN_TIMEOUT:-120}

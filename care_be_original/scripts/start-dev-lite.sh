#!/usr/bin/env bash
printf "api" > /tmp/container-role

set -euo pipefail

./scripts/wait_for_db.sh

# Skip wait_for_redis.sh — dev-lite mode uses in-memory cache

echo "running migrations..."
python manage.py migrate --noinput
python manage.py compilemessages -v 0
python manage.py sync_permissions_roles || true
python manage.py sync_valueset || true

echo "running collectstatic..."
python manage.py collectstatic --noinput

echo "starting server (dev-lite mode — no Redis, no Celery)..."
if [[ "${ATTACH_DEBUGGER}" == "true" ]]; then
  echo "waiting for debugger..."
  python -m debugpy --wait-for-client --listen 0.0.0.0:9876 manage.py runserver_plus 0.0.0.0:9000 --print-sql
else
  python manage.py runserver_plus 0.0.0.0:9000 --print-sql
fi

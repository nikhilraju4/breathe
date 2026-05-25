#!/bin/sh
set -e
cd /app/backend
echo "Running migrations..."
python manage.py migrate --noinput
echo "Seeding demo data (skipped if already present)..."
python manage.py seed_demo
echo "Starting gunicorn on port ${PORT:-8000}..."
exec gunicorn config.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120

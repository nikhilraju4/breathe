#!/usr/bin/env bash
set -e
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build
cd ../backend
python manage.py collectstatic --noinput
python manage.py migrate --noinput

#!/bin/bash
set -e

echo "Starting Celery worker..."
celery -A playto worker -l info --detach

echo "Starting Celery beat..."
celery -A playto beat -l info --detach

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn server..."
exec gunicorn playto.wsgi:application --bind 0.0.0.0:8000 --workers 2

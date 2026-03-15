#!/bin/bash
set -e

echo "Running migrations..."
uv run python app/manage.py migrate --noinput

echo "Starting development server..."
exec uv run python app/manage.py runserver 0.0.0.0:8000
#!/bin/bash
# Container entrypoint: serve.
#
# The schema is brought up to date by the compose `migrate` service, which every
# database-touching service waits on, so by the time this runs the database is
# already current. Keeping it out of here means a plain `docker compose up -d`
# still migrates even when this container is left running untouched, and that
# two backend containers cannot race each other applying the same migration.
set -eo pipefail

if [ "${DEBUG:-False}" = "True" ]; then
    python manage.py runserver 0.0.0.0:8080
else
    python -m uvicorn backend.asgi:application --host 0.0.0.0 --port 8080
fi

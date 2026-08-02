#!/bin/bash
# Container entrypoint: bring the schema up to date, then serve.
#
# -e so a failed migration stops the container instead of letting it serve
# traffic against a schema that does not match the code. A crash-looping
# container is a loud, obvious failure; a silently un-migrated one is not.
set -eo pipefail

echo "Waiting for the database..."
while ! nc -z db 5432; do
    sleep 10
done

echo "Applying migrations..."
python manage.py migrate --noinput

# Not fatal: the app runs fine without a superuser, and failing here would block
# startup over something that is only a convenience.
python manage.py ensure_superuser || echo "ensure_superuser failed; continuing."

if [ "${DEBUG:-False}" = "True" ]; then
    python manage.py runserver 0.0.0.0:8080
else
    python -m uvicorn backend.asgi:application --host 0.0.0.0 --port 8080
fi

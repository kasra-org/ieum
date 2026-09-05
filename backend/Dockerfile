FROM python:3.13-slim

# netcat-openbsd: start.sh waits for the DB with it.
# postgresql-client-13: pg_dump/psql for the admin backup/restore. The client
# MUST match the server major version (the db service is postgres:13) - a newer
# pg_dump emits settings an older server rejects, e.g. transaction_timeout from
# v17 on a v13 server. Installed from the PostgreSQL APT repository, since Debian
# trixie ships only v17. If the database is upgraded, bump this to match.
RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-13 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# collectstatic only needs the settings module to import; it never signs
# anything. The key is scoped to this one RUN rather than set as ENV, so it is
# not baked into the image and the container still refuses to start unless a
# real SECRET_KEY is supplied at runtime.
RUN SECRET_KEY=build-time-only-never-used-at-runtime \
    python manage.py collectstatic --noinput

CMD ["bash", "scripts/start.sh"]
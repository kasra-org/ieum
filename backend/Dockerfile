FROM python:3.13-slim

RUN apt-get update && apt-get install -y netcat-openbsd
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
# IEUM

> IEUM - an open-source conference management system for scientific meetings

## Overview

IEUM is an open-source platform for organizing scientific conferences. It manages abstract submissions, event registrations, and offers customizable workflows for event organizers.

## Features

- **Multi-conference support**
- **Abstract submission & review** with voting system
- **Custom registration forms**
- **Role-based access control**
- **Speaker and attendee management**

## Tech Stack

- **Backend**: Python/Django Ninja/Allauth
- **Frontend**: SvelteKit
- **Database**: PostgreSQL
- **Containerization**: Docker

## Quick Start

1. Clone repository.
```bash
# Clone repository
git clone https://github.com/ieum-org/ieum.git
cd ieum
```
2. Create a .env file. Define all variables in `compose.yml` (production) or
   `compose-dev.yml` (development).
3. Run IEUM via Docker Compose
```bash
# Development, on port 9080
docker compose -f compose-dev.yml up -d
# or production, on port 9090
docker compose up -d
```
   Database migrations are applied automatically: a one-shot `migrate` service
   runs on every `up`, and everything that touches the database waits for it to
   finish. Nothing needs to be run by hand.

   After changing code or dependencies, add `--build`. The production images
   carry the source rather than mounting it, so without a rebuild the containers
   keep serving the old code:
```bash
docker compose up -d --build
```
4. The superuser is created from the `DJANGO_SUPERUSER_*` variables in your .env,
   also by the `migrate` service. To create another one by hand:
```bash
docker compose exec backend python manage.py createsuperuser
```
5. Login via Django Admin at http://127.0.0.1:9080/[DJANGO_ADMIN_PAGE_NAME]
6. Access admin page at http://127.0.0.1:9080/[ADMIN_PAGE_NAME]
7. Create a conference
8. Configure event settings

## Documentation
TBA

## License
GNU AGPL 3. See LICENCE.

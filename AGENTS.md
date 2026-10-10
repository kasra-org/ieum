# IEUM - Conference Management System Architecture

## Overview

**IEUM** is an open-source conference management system designed for organizing scientific conferences with seamless integration with existing static websites. It manages abstract submissions, event registrations, and provides customizable workflows for event organizers.

**Architectural Philosophy**: Multi-tenant conference platform that acts as a headless backend for registration and abstract management.

---

## Development Notes

### Package Manager
**IMPORTANT**: Use `pnpm` for all package management operations in the frontend directory. Do not use `npm`.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Client Layer                               │
│  Frontend (SvelteKit) + Static Website Integration                  │
└──────────────────────────────────────────────────────────────────────┘
                                │
                        (HTTPS/JSON API)
                                │
┌──────────────────────────────────────────────────────────────────────┐
│                       Service Layer                                   │
│                    (Caddy Reverse Proxy)                             │
└──────────────────────────────────────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
┌────────▼────────┐  ┌─────────▼────────┐   ┌────────▼────────┐
│   Backend       │  │  Frontend        │   │  Static Files   │
│   (Django)      │  │  (Node/SvelteKit)│   │  (Media/Static) │
│   Port 8080     │  │  Port 3000       │   │  (Caddy Serve)  │
└────────┬────────┘  └──────────────────┘   └─────────────────┘
         │
    ┌────┴─────────────────────────────────┐
    │         Backend Ecosystem              │
    │                                        │
    │  ┌──────────────┐  ┌──────────────┐   │
    │  │ Django Ninja │  │ Allauth      │   │
    │  │ REST API     │  │ Auth Service │   │
    │  └──────────────┘  └──────────────┘   │
    │         │                              │
    │  ┌──────▼──────────┐                   │
    │  │ Message Queue   │                   │
    │  │ (RabbitMQ)      │                   │
    │  └────────┬────────┘                   │
    │           │                             │
    │  ┌────────▼─────────┐                  │
    │  │ Celery Worker    │                  │
    │  │ (Async Tasks)    │                  │
    │  └──────────────────┘                  │
    └────────────────────────────────────────┘
         │
    ┌────▼────────────────────────┐
    │   Data Layer                  │
    │                              │
    │  ┌────────────────────────┐  │
    │  │  PostgreSQL Database   │  │
    │  │  (Primary Data Store)  │  │
    │  └────────────────────────┘  │
    └────────────────────────────────┘
```

---

## Docker Services (Agents)

### 1. Database Service (`db`)
- **Image**: PostgreSQL 13
- **Purpose**: Primary data persistence layer
- **Volume**: `postgres_data` (persistent storage)
- **Environment Variables**:
  - `POSTGRES_DB`: Database name
  - `POSTGRES_USER`: Database user
  - `POSTGRES_PASSWORD`: Database password
- **Access**: Internal only (no external port exposure)

### 2. Backend Service (`backend`)
- **Build**: Custom Docker image from `/backend` directory
- **Purpose**: REST API server, business logic layer
- **Internal Port**: 8080
- **Framework**: Django 5.1 with Django Ninja (REST API)
- **Key Responsibilities**:
  - User authentication and authorization
  - Event management
  - Abstract submission and review
  - Registration processing
  - Email template management
- **Dependencies**:
  - PostgreSQL (database)
  - RabbitMQ (message broker)
- **Configuration**: 10+ environment variables (see Environment Variables section)

### 3. Frontend Service (`frontend`)
- **Build**: Custom Docker image from `/frontend` directory
- **Purpose**: Web UI server
- **Internal Port**: 3000
- **Framework**: SvelteKit (SSR-capable Svelte framework)
- **Key Responsibilities**:
  - User interface rendering
  - Client-side routing
  - API communication
  - Form handling and validation
- **Configuration**:
  - `ADMIN_PAGE_NAME`: Frontend admin page route
  - `NODE_ENV`: Production/development mode
  - `DEBUG`: Debug flag

### 4. RabbitMQ Service (`rabbitmq`)
- **Image**: RabbitMQ 3
- **Purpose**: Message broker for Celery task queue
- **Default Credentials**: `guest:guest` (configurable via environment)
- **Key Responsibilities**:
  - Queue management for async tasks
  - Message routing between backend and celery
- **Logging**:
  - Driver: json-file
  - Max size: 50MB
  - Max files: 4

### 5. Celery Worker Service (`celery`)
- **Build**: Custom Docker image from `/backend` directory
- **Command**: `celery -A backend worker -l info`
- **Purpose**: Process asynchronous tasks
- **Key Responsibilities**:
  - Email sending (`send_mail.delay()`)
  - Background job processing
- **Dependencies**:
  - RabbitMQ (broker)
  - PostgreSQL (database access)
- **Environment**: Same email and database configuration as backend
- **Logging**:
  - Driver: json-file
  - Max size: 50MB
  - Max files: 4

### 6. Caddy Service (`caddy`)
- **Image**: Caddy 2.8.4
- **Purpose**: Reverse proxy and static file server
- **External Port**: 9090:80 (production), 9080:80 (development)
- **Key Responsibilities**:
  - HTTP/HTTPS routing
  - SSL/TLS termination
  - Static file serving (`/www/static`, `/www/media`)
  - Request routing to backend and frontend services
- **Volumes**:
  - `caddy_data`: Caddy data directory
  - `caddy_config`: Caddy configuration
  - `static_data`: Django static files
  - `media_data`: User-uploaded media files

---

## Technology Stack

### Backend Technologies
- **Framework**: Django 5.1
- **API Framework**: Django Ninja (async-capable REST API)
- **Authentication**: Django Allauth (account management + OAuth2)
- **Social Auth**: ORCID OAuth provider
- **ORM**: Django ORM
- **Task Queue**: Celery
- **Message Broker**: RabbitMQ
- **Database**: PostgreSQL 13
- **File Processing**: python-docx, odfpy (DOCX/ODT to HTML conversion)

### Frontend Technologies
- **Framework**: SvelteKit
- **Component Library**: Flowbite Svelte
- **Styling**: Tailwind CSS
- **Form Validation**: Felte + Yup
- **Icons**: Flowbite Svelte Icons, Academicons
- **PDF Generation**: jsPDF
- **Build Tool**: Vite

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Web Server**: Caddy
- **Process Management**: Docker's built-in restart policies

---

## Data Models

### User Model (extends Django AbstractUser)
Custom user model with conference-specific fields:
- Standard fields: username, email, password, is_staff, is_active
- Custom fields: middle_initial, nationality, job_title, institute, department, disability, dietary

### Core Event Models

#### Event
Conference/event definition with:
- Basic info: name, dates, venue, organizers
- Registration: capacity, deadline
- Abstract submission: accepts_abstract, abstract_deadline, capacity_abstract
- Relationships: attendees (M2M), reviewers (M2M), admins (M2M)
- Email templates: registration, abstract submission

#### Attendee
Event registration record:
- Links: user (FK), event (FK)
- Personal data: name, nationality, institute, department, job_title
- Special needs: disability, dietary

#### OnSiteAttendee
Walk-in registration (no account required):
- Event-specific (FK)
- Basic info: name, institute, job_title

#### Speaker
Speaker/presenter records:
- Event-specific (FK)
- Info: name, email, affiliation, is_domestic
- Type: keynote, invited, contributed, short, poster

### Abstract & Review Models

#### Abstract
Abstract submission:
- Links: attendee (FK), event (FK)
- Content: title, file_path
- Status: is_oral, is_accepted

#### AbstractVote
Reviewer voting tracking:
- Links: reviewer (FK → Attendee)
- Votes: voted_abstracts (M2M → Abstract)

### Form & Communication Models

#### CustomQuestion
Event-specific registration questions:
- JSONField schema: {type, question, detail, options}
- Supports: text, textarea, radio, checkbox question types

#### CustomAnswer
User responses to custom questions:
- Links: reference (FK → CustomQuestion), attendee (FK)
- Data: question (text copy), answer (text)

#### EmailTemplate
Customizable email templates:
- Fields: subject, body
- Supports Django template variables: `{{ event }}`, `{{ attendee }}`, `{{ abstract }}`

---

## API Endpoints

All endpoints use base URL `/api/` with CSRF protection enabled.

**Pagination**: the admin lists that can grow large answer a page at a time as `{items, total, offset, limit}` (plus `counts`/`summary` computed over the whole list, before search), taking `offset`, `limit` (max 200), `search` and `field` (which column group to search; `all` searches every one). Each event list also has an unpaged `.../export` twin with the same filters for whole-list actions (CSV, email to all, certificates, a selection spanning pages; `ids=` fetches a selection). Django is not reachable from the browser - Caddy sends `/api/*` to SvelteKit - so the admin tables fetch these through per-endpoint relay routes under `frontend/src/routes/api/` (no catch-all), via `$lib/pagedList.svelte.js`; pickers search through `RemoteSearchList.svelte`.

### Authentication & User Management
- `GET /api/me` - Get authenticated user profile
- `POST /api/me` - Update user profile
- `GET /api/csrftoken` - Get CSRF token (public)

### Event Management
- `GET /api/events` - List all events (public)
- `GET /api/event/{event_id}` - Get event details (public)
- `GET /api/admin/events` - Events, paginated; `search`/`field` (name, venue, id), `archived=true` to include archived (staff only)
- `GET /api/admin/users` - Accounts, paginated and searchable; `not_registered_for`/`not_admin_of=<event id>` for pickers (staff only - event admins only get exact-email lookup)
- `GET /api/admin/institutions` - Institutions, paginated (staff only)
- `POST /api/admin/event/add` - Create event (staff only)
- `POST /api/admin/event/{event_id}/delete` - Delete event (staff only)
- `GET /api/admin/event/{event_id}` - Get admin event details
- `POST /api/event/{event_id}/update` - Update event (event admin)
- `GET /api/event/{event_id}/stats` - Event statistics

### Event Registration
- `POST /api/event/{event_id}/register` - Register for event
- `GET /api/event/{event_id}/registered` - Check registration status
- `POST /api/event/{event_id}/attendee/{attendee_id}/deregister` - Deregister
- `GET /api/event/{event_id}/attendees` - Registrations, paginated; `status` = registered (roster, default) / unpaid / all, picker exclusions `has_user`, `has_abstract`, `has_completed_payment`, `not_speaker`, `not_admin`; `counts` = {registered, unpaid} (event admin)
- `GET /api/event/{event_id}/attendees/export` - Same filters, unpaged (event admin)
- `GET /api/event/{event_id}/payments` - Payments, paginated, newest first; `summary` = event-wide counts and sums by status (event admin); `.../payments/export` unpaged
- `POST /api/event/{event_id}/attendee/{attendee_id}/update` - Update attendee
- `POST /api/event/{event_id}/attendee/{attendee_id}/answers` - Update custom answers

### Custom Questions
- `GET /api/event/{event_id}/questions` - Get custom questions
- `POST /api/event/{event_id}/questions` - Update questions (event admin)

### Abstract Management
- `POST /api/event/{event_id}/abstract` - Submit abstract
- `GET /api/event/{event_id}/abstracts` - Abstracts with full author registration, paginated; `type` filter, `counts` per presentation type (event admin); `.../abstracts/export` unpaged
- `GET /api/event/{event_id}/review/abstracts` - List reviewable abstracts, author name/affiliation only (reviewer)
- `GET /api/event/{event_id}/abstract` - Get user's abstract
- `GET /api/event/{event_id}/abstract/{abstract_id}` - Get abstract body for review (reviewer/event admin; no file link)
- `GET /api/media-auth/abstract` - Caddy forward_auth check for `/media/abstracts/*` (author or event admin only)
- `POST /api/event/{event_id}/abstract/{abstract_id}/update` - Update abstract
- `POST /api/event/{event_id}/abstract/{abstract_id}/delete` - Delete abstract

### Review System
- `GET /api/event/{event_id}/reviewer` - Check reviewer status
- `GET /api/event/{event_id}/reviewers` - List reviewers (event admin)
- `POST /api/event/{event_id}/reviewer/add` - Add reviewer (event admin)
- `POST /api/event/{event_id}/reviewer/{reviewer_id}/delete` - Remove reviewer
- `GET /api/event/{event_id}/reviewer/vote` - Get reviewer votes
- `POST /api/event/{event_id}/reviewer/vote` - Submit votes

### Speaker Management
- `GET /api/event/{event_id}/speakers` - List speakers (public: no email/payment fields, hidden for draft/archived events)
- `GET /api/event/{event_id}/admin/speakers` - List speakers with email and payment state (event admin)
- `POST /api/event/{event_id}/speaker/add` - Add speaker
- `POST /api/event/{event_id}/speaker/{speaker_id}/update` - Update speaker
- `POST /api/event/{event_id}/speaker/{speaker_id}/delete` - Delete speaker

### On-Site Registration
- `POST /api/event/{event_id}/onsite` - Register on-site (public)
- `GET /api/event/{event_id}/onsite` - On-site attendees, paginated (event admin); `.../onsite/export` unpaged
- `POST /api/event/{event_id}/onsite/{onsite_id}/update` - Update on-site attendee
- `POST /api/event/{event_id}/onsite/{onsite_id}/delete` - Delete on-site attendee

### Email System
- `POST /api/event/{event_id}/emailtemplates` - Update email templates
- `GET /api/event/{event_id}/email_templates` - Get email templates
- `POST /api/event/{event_id}/send_emails` - Send bulk emails

### Event Admin Management
- `GET /api/event/{event_id}/eventadmins` - List event admins
- `POST /api/event/{event_id}/eventadmin/add` - Add event admin
- `POST /api/event/{event_id}/eventadmin/{admin_id}/delete` - Remove event admin

### Allauth Routes
- `/accounts/*` - Allauth account management URLs
- `/_allauth/*` - Headless allauth API endpoints

---

## Authorization & Access Control

### Role-Based Access Control (RBAC)

#### 1. Django Staff Users (`user.is_staff`)
- **Decorator**: `@ensure_staff`
- **Permissions**:
  - Full system access
  - Manage all events
  - Manage all users
  - Access Django admin interface

#### 2. Event Admins
- **Mechanism**: Added to `Event.admins` M2M field
- **Decorator**: `@ensure_event_staff`
- **Permissions**:
  - Manage event-specific data
  - View and edit attendees
  - Manage abstracts and reviews
  - Add/remove speakers
  - Configure custom questions
  - Manage email templates
  - Add/remove other event admins
  - Cannot access other events

#### 3. Reviewers
- **Mechanism**: Added to `Event.reviewers` M2M field
- **Permissions**:
  - View abstracts for assigned event
  - Submit votes for abstracts
  - AbstractVote object automatically created

#### 4. Regular Users
- **Permissions**:
  - Register for events
  - Submit abstracts (if event accepts)
  - View own registration data
  - Update own profile

#### 5. Anonymous Users
- **Permissions**:
  - View public event information
  - Access on-site registration

### Authentication Mechanisms

#### Primary Authentication
- **Backend**: Django ModelBackend + Allauth AuthenticationBackend
- **Session**: Cookie-based session management
- **CSRF**: Token-based protection (X-CSRFToken header)

#### Email Verification
- **Requirement**: Mandatory (`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`)
- **Flow**:
  1. User registers
  2. Verification email sent via Celery
  3. User clicks link to activate account
  4. Account activated

#### Social Authentication (ORCID)
- **Provider**: ORCID OAuth
- **Mode**: Headless OAuth flow
- **Configuration**:
  - Production: `https://orcid.org`
  - Development: `https://sandbox.orcid.org`

---

## Key Workflows

### Event Registration Workflow
1. User navigates to `/event/[slug]/register`
2. Frontend loads custom questions via `GET /api/event/{event_id}/questions`
3. User fills form with personal data + custom question responses
4. Frontend sends `POST /api/event/{event_id}/register`
5. Backend validates:
   - Registration deadline not passed
   - Event capacity not reached
   - User not already registered
   - All mandatory fields provided
6. Backend creates:
   - Attendee record
   - CustomAnswer records for each question
7. Celery sends confirmation email asynchronously

### Abstract Submission Workflow
1. Registered user navigates to `/event/[slug]/abstract`
2. User uploads file (DOCX/ODT) + fills metadata
3. Frontend sends `POST /api/event/{event_id}/abstract`
4. Backend validates:
   - Abstract submission deadline not passed
   - Abstract capacity not reached
   - User hasn't already submitted
   - User is registered for event
5. Backend:
   - Stores file in media storage (`abstracts/{uuid}/{filename}`)
   - Creates Abstract record
   - Triggers confirmation email via Celery

### Abstract Review Workflow
1. Event admin adds reviewers via `POST /api/event/{event_id}/reviewer/add`
2. Backend creates AbstractVote object for each reviewer
3. After abstract deadline, reviewers access review interface
4. Reviewers vote: `POST /api/event/{event_id}/reviewer/vote`
5. Backend tracks votes in AbstractVote.voted_abstracts M2M
6. Event admin views voting results and makes decisions

### On-Site Registration Workflow
1. No authentication required
2. Staff member fills on-site form at `/event/[slug]/onsite`
3. Frontend sends `POST /api/event/{event_id}/onsite`
4. Backend creates OnSiteAttendee record
5. Returns attendee ID for check-in tracking

---

## Environment Variables

### Django Settings
- `SECRET_KEY` - Django secret key (required)
- `DEBUG` - Debug mode (True/False)
- `HOST` - Allowed host domain/IP
- `DJANGO_ADMIN_PAGE_NAME` - Admin URL path (security via obscurity)

### Database Configuration
- `DB_NAME` - PostgreSQL database name
- `DB_USER` - PostgreSQL user
- `DB_PASSWORD` - PostgreSQL password
- `DB_PORT` - PostgreSQL port (default: 5432)

### Email Configuration
- `EMAIL_PREFIX` - Email subject prefix
- `EMAIL_FROM` - Sender email address
- `EMAIL_HOST` - SMTP server hostname
- `EMAIL_HOST_USER` - SMTP username
- `EMAIL_HOST_PASSWORD` - SMTP password
- `EMAIL_PORT` - SMTP port (465 for SSL, 587 for TLS)

### OAuth Configuration
- `ORCID_BASE_DOMAIN` - ORCID domain (production or sandbox)

### RabbitMQ Configuration
- `RABBITMQ_DEFAULT_USER` - RabbitMQ username
- `RABBITMQ_DEFAULT_PASS` - RabbitMQ password

### Frontend Configuration
- `HEADLESS_URL_ROOT` - Frontend URL root for callbacks
- `ACCOUNT_DEFAULT_HTTP_PROTOCOL` - HTTP or HTTPS
- `ADMIN_PAGE_NAME` - Frontend admin page route

---

## Deployment Configurations

### Development Mode (`compose-dev.yml`)
- **Caddy Port**: 9080
- **Backend**:
  - Volume mount: `./backend:/app` (live code reload)
  - Debug: True
  - ORCID: Sandbox mode
  - Protocol: HTTP
  - Logs: `/dev/null`
- **Frontend**:
  - Volume mount: `./frontend:/app` (live code reload)
  - Debug: True
- **Celery**:
  - Volume mount: `./backend:/app` (live code reload)

### Production Mode (`compose.yml`)
- **Caddy Port**: 9090
- **Backend**:
  - No volume mounts (code baked into image)
  - Debug: False
  - ORCID: Production mode
  - Protocol: HTTPS
  - Logs: `/app/backend.log`
- **Frontend**:
  - No volume mounts
  - NODE_ENV: production
  - Debug: False
- **Celery**:
  - No volume mounts
  - Production logging configuration

---

## File Processing

### Abstract File Support
- **Supported Formats**: DOCX, ODT
- **Storage Path**: `media/abstracts/{uuid}/{filename}`
- **Conversion**: Files converted to HTML for preview

### Document Conversion Utilities
- `docx_to_html()` - Converts DOCX to HTML
  - Preserves: bold, italic, underline, super/subscript
  - Handles: alignment, paragraph styles
- `odt_to_html()` - Converts ODT to HTML
  - Full style resolution from content.xml

---

## Security Features

### Application Security
- **CSRF Protection**: Enabled globally with token validation
- **Email Verification**: Mandatory before account activation
- **Password Security**: Django's PBKDF2 hashing
- **Session Security**: HttpOnly cookies
- **Admin URL Obscurity**: Configurable admin path

### Infrastructure Security
- **SSL/TLS**: Caddy handles automatic HTTPS
- **Database**: Internal network only (no external exposure)
- **RabbitMQ**: Internal network only
- **Environment Secrets**: Stored in .env (gitignored)

### API Security
- **Authentication**: Required for most endpoints
- **Authorization**: Role-based access control
- **Input Validation**: Pydantic schemas via Django Ninja
- **SQL Injection**: Protected by Django ORM

---

## Monitoring & Logging

### Container Logs
- **RabbitMQ**: JSON file driver, 50MB max, 4 files
- **Celery**: JSON file driver, 50MB max, 4 files
- **Django**: Configurable via LOG_FILE environment variable

### Django Logging
- **Handler**: File + Console
- **Level**: INFO (configurable)
- **Propagation**: Enabled

---

## Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Debug Mode | True | False |
| Volume Mounts | Yes (live reload) | No (image-baked) |
| Caddy Port | 9080 | 9090 |
| ORCID Domain | sandbox.orcid.org | orcid.org |
| Protocol | HTTP | HTTPS |
| Logs | /dev/null | /app/backend.log |
| NODE_ENV | development | production |

---

## Service Communication

### Internal Network
All services communicate via Docker's internal network:
- Backend → Database: `db:5432`
- Backend → RabbitMQ: `rabbitmq:5672`
- Celery → Database: `db:5432`
- Celery → RabbitMQ: `rabbitmq:5672`
- Frontend → Backend: `backend:8080` (via Caddy proxy)

### External Access
- User → Caddy: Port 9090 (production) or 9080 (development)
- Caddy → Backend: Internal routing to `backend:8080`
- Caddy → Frontend: Internal routing to `frontend:3000`

---

## Key Components Summary

### Services/Agents Count: 6
1. PostgreSQL (Database)
2. Django Backend (API Server)
3. SvelteKit Frontend (Web UI)
4. RabbitMQ (Message Broker)
5. Celery Worker (Task Processor)
6. Caddy (Reverse Proxy)

### API Endpoints: 64+
- Authentication: 3
- Event Management: 8
- Registration: 7
- Custom Questions: 2
- Abstracts: 7
- Review System: 5
- Speakers: 4
- On-Site: 4
- Email: 3
- Admin Management: 3

### Data Models: 9
- User (custom)
- Event
- Attendee
- OnSiteAttendee
- Speaker
- Abstract
- AbstractVote
- CustomQuestion
- CustomAnswer
- EmailTemplate

### Frontend Routes: 20+
- Authentication routes (registration, login, password reset, email verification)
- Profile management
- Event-specific routes (registration, abstract submission, review, admin)
- On-site registration

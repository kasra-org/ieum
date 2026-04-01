import json
import base64
import uuid
import requests
from functools import wraps

from datetime import datetime, timedelta
from typing import List
from django.utils import timezone

from ninja import NinjaAPI
from ninja.security import django_auth

from django.middleware.csrf import get_token
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template import Template, Context
from django.db import IntegrityError
from django.db.models import Max

from django.conf import settings
import logging

logger = logging.getLogger(__name__)

from main.models import Event, EmailTemplate, Attendee, CustomQuestion, CustomAnswer, Abstract, AbstractVote, OnSiteAttendee, Institution, PaymentHistory, BusinessSettings, ExchangeRate, ManualTransaction, AccountSettings, PrivacyPolicy, TermsOfService, Organizer, SiteSettings
from main.schema import *
from main.utils import validate_abstract_file, sanitize_filename, rate_limit, sanitize_email_header, validate_email_format, validate_editor_file, generate_onsite_code

from .tasks import send_mail, send_mail_with_attachment

api = NinjaAPI(csrf=True, auth=django_auth)

def ensure_staff(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        request = args[0]
        user = request.user
        if not user.is_staff:
            return api.create_response(
                request,
                {"code": "permission_denied", "message": "Permission denied"},
                status=403,
            )
        return func(*args, **kwargs)
    return wrapper

def ensure_event_staff(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        request = args[0]
        event_id = kwargs["event_id"]
        user = request.user
        if not (user.is_staff or user in Event.objects.get(id=event_id).admins.all()):
            return api.create_response(
                request,
                {"code": "permission_denied", "message": "Permission denied"},
                status=403,
            )
        return func(*args, **kwargs)
    return wrapper

@api.get("/me", response=UserSchema)
def get_user(request):
    # Clean up any verification keys for this user's email when they successfully authenticate
    from main.models import EmailVerificationKey
    EmailVerificationKey.objects.filter(email=request.user.email).delete()

    return request.user

@api.post("/me", response=UserSchema)
def update_user(request):
    data = json.loads(request.body)
    # check if mandatory fields are filled (English name required for all)
    if not data["first_name"] or not data["last_name"] or not data["nationality"] or not data["institute"]:
        return api.create_response(
            request,
            {"errors": [{"message": "Required fields are not filled", "code": "invalid"}]},
            status=400,
        )

    # Korean nationals (nationality == 1) must also provide korean_name
    nationality = int(data["nationality"])
    if nationality == 1 and not data.get("korean_name", "").strip():
        return api.create_response(
            request,
            {"errors": [{"message": "Korean name is required for Korean nationals", "code": "invalid"}]},
            status=400,
        )

    user = request.user

    # Fix username to match email if mismatched (can happen with social signups)
    # Only allow setting username to the user's own verified email for security
    if user.username != user.email:
        user.username = user.email

    user.first_name = data["first_name"]
    user.last_name = data["last_name"]
    user.middle_initial = data.get("middle_initial", "")
    user.korean_name = data.get("korean_name", "")
    user.nationality = nationality
    user.job_title = data.get("job_title", "")
    user.department = data.get("department", "")

    # Assign institution by ID
    institute_id = data.get("institute")
    if institute_id:
        try:
            institution = Institution.objects.get(id=int(institute_id))
            user.institute = institution
        except (Institution.DoesNotExist, ValueError):
            return api.create_response(
                request,
                {"error": "Invalid institution"},
                status=400,
            )
    else:
        user.institute = None

    user.disability = data.get("disability", "")
    user.dietary = data.get("dietary", "")
    user.save()
    return user

@api.post("/me/delete")
def delete_user(request):
    data = json.loads(request.body)
    password = data.get("password", "")

    user = request.user

    # Verify password
    if not user.check_password(password):
        return api.create_response(
            request,
            {"error": {"message": "Incorrect password", "code": "invalid_password"}},
            status=400,
        )

    # Delete the user account
    user.delete()

    return api.create_response(
        request,
        {"success": True, "message": "Account deleted successfully"},
        status=200,
    )

@api.get("/me/payment-history", response=List[PaymentHistorySchema])
def get_payment_history(request):
    """
    Get the payment history for the current user.
    Uses copied fields from PaymentHistory for data preservation.
    """
    user = request.user
    payments = PaymentHistory.objects.filter(attendee__user=user).select_related('event')

    payment_history = []
    for payment in payments:
        payment_history.append({
            'number': payment.toss_order_id or str(payment.id),
            'checkout_date': payment.created_at.strftime('%Y-%m-%d'),
            'amount': payment.amount,
            'event_id': payment.event.id if payment.event else None,
            'event_name': payment.event_name,
            'start_date': payment.event_start_date.strftime('%Y-%m-%d') if payment.event_start_date else '',
            'end_date': payment.event_end_date.strftime('%Y-%m-%d') if payment.event_end_date else '',
            'venue': payment.event_venue,
            'venue_ko': payment.event_venue_ko,
            'organizers_en': payment.event_organizers_en,
            'organizers_ko': payment.event_organizers_ko,
            'status': payment.status,
            'payment_type': payment.payment_type,
            'attendee_name': payment.attendee_name,
            'attendee_name_ko': payment.attendee_korean_name,
            'attendee_institute': payment.attendee_institute,
            'attendee_institute_ko': payment.attendee_institute_ko,
        })

    return payment_history

@api.get("/me/payment/{order_id}", response=PaymentHistorySchema)
def get_payment_by_id(request, order_id: str):
    """
    Get a single payment by order ID for the current user.
    Uses copied fields from PaymentHistory for data preservation.
    """
    user = request.user
    try:
        payment = PaymentHistory.objects.select_related('event').get(toss_order_id=order_id, attendee__user=user)
    except PaymentHistory.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Payment not found"},
            status=404,
        )

    return {
        'number': payment.toss_order_id or str(payment.id),
        'checkout_date': payment.created_at.strftime('%Y-%m-%d'),
        'amount': payment.amount,
        'event_id': payment.event.id if payment.event else None,
        'event_name': payment.event_name,
        'start_date': payment.event_start_date.strftime('%Y-%m-%d') if payment.event_start_date else '',
        'end_date': payment.event_end_date.strftime('%Y-%m-%d') if payment.event_end_date else '',
        'venue': payment.event_venue,
        'venue_ko': payment.event_venue_ko,
        'organizers_en': payment.event_organizers_en,
        'organizers_ko': payment.event_organizers_ko,
        'status': payment.status,
        'payment_type': payment.payment_type,
        'attendee_name': payment.attendee_name,
        'attendee_name_ko': payment.attendee_korean_name,
        'attendee_institute': payment.attendee_institute,
        'attendee_institute_ko': payment.attendee_institute_ko,
    }

@api.get("/me/registration-history", response=List[RegistrationHistorySchema])
def get_registration_history(request):
    """
    Get the registration history for the current user.
    """
    user = request.user
    attendees = Attendee.objects.filter(user=user).select_related('event')

    registration_history = []
    for attendee in attendees:
        event = attendee.event

        # Construct attendee name
        name_parts = [attendee.first_name or '']
        if attendee.middle_initial:
            name_parts.append(attendee.middle_initial)
        name_parts.append(attendee.last_name or '')
        attendee_name = ' '.join(filter(None, name_parts))
        if attendee.korean_name:
            attendee_name = f"{attendee_name} ({attendee.korean_name})" if attendee_name else attendee.korean_name
        attendee_institute = attendee.institute or ''

        # Determine payment status
        registration_fee = event.registration_fee or 0
        if registration_fee == 0:
            payment_status = 'free'
        else:
            # Check if there's a completed payment for this attendee
            if PaymentHistory.objects.filter(attendee=attendee, status='completed').exists():
                payment_status = 'completed'
            else:
                payment_status = 'pending'

        registration_history.append({
            'id': attendee.id,
            'registration_date': event.start_date.strftime('%Y-%m-%d'),  # Use event start date as fallback
            'event_id': event.id,
            'event_name': event.name,
            'start_date': event.start_date.strftime('%Y-%m-%d'),
            'end_date': event.end_date.strftime('%Y-%m-%d'),
            'venue': event.venue,
            'venue_ko': event.venue_ko,
            'organizers_en': event.organizers_en,
            'organizers_ko': event.organizers_ko,
            'attendee_name': attendee_name,
            'attendee_institute': attendee_institute,
            'registration_fee': registration_fee,
            'payment_status': payment_status,
            'is_attended': attendee.is_attended
        })

    # Sort by event start date descending
    registration_history.sort(key=lambda x: x['start_date'], reverse=True)

    return registration_history

@api.get("/csrftoken", auth=None)
def get_csrf_token(request):
    token = get_token(request)
    return {"csrftoken": token}

@api.get("/institutions", response=List[InstitutionSchema], auth=None)
def search_institutions(request, search: str = ""):
    from django.db.models import Q

    institutions = Institution.objects.all()

    if search:
        institutions = institutions.filter(
            Q(name_en__icontains=search) | Q(name_ko__icontains=search)
        )

    return list(institutions[:50])  # Limit to 50 results

@api.get("/institutions/{institution_id}", response=InstitutionSchema, auth=None)
def get_institution(request, institution_id: int):
    try:
        institution = Institution.objects.get(id=institution_id)
        return institution
    except Institution.DoesNotExist:
        return api.create_response(request, {"error": "Institution not found"}, status=404)

@api.post("/institutions", response=InstitutionSchema, auth=None)
@rate_limit(max_requests=10, window_seconds=60)
def create_institution(request, data: InstitutionCreateSchema):

    # Check if institution already exists
    existing = Institution.objects.filter(name_en=data.name_en).first()
    if existing:
        return existing

    institution = Institution.objects.create(
        name_en=data.name_en,
        name_ko=data.name_ko
    )
    return institution

@api.get("/admin/institutions", response=List[InstitutionSchema])
@ensure_staff
def get_admin_institutions(request, offset: int = 0, limit: int = 100, search: str = ""):
    from django.db.models import Q

    institutions = Institution.objects.all()

    if search:
        institutions = institutions.filter(
            Q(name_en__icontains=search) | Q(name_ko__icontains=search)
        )

    institutions = institutions.order_by('name_en')
    total = institutions.count()
    institutions = institutions[offset:offset + limit]

    return list(institutions)

@api.get("/admin/institution/{institution_id}", response=InstitutionSchema)
@ensure_staff
def get_admin_institution(request, institution_id: int):

    try:
        institution = Institution.objects.get(id=institution_id)
        return institution
    except Institution.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Institution not found"},
            status=404,
        )

@api.post("/admin/institution/{institution_id}/update", response=InstitutionSchema)
@ensure_staff
def update_institution(request, institution_id: int, data: InstitutionCreateSchema):

    try:
        institution = Institution.objects.get(id=institution_id)
        institution.name_en = data.name_en
        institution.name_ko = data.name_ko
        institution.save()
        return institution
    except Institution.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Institution not found"},
            status=404,
        )
    except IntegrityError:
        return api.create_response(
            request,
            {"code": "duplicate", "message": "An institution with this name already exists"},
            status=400,
        )

@api.post("/admin/institution/{institution_id}/delete", response=MessageSchema)
@ensure_staff
def delete_institution(request, institution_id: int):

    try:
        institution = Institution.objects.get(id=institution_id)
        institution.delete()
        return {"code": "success", "message": "Institution deleted successfully"}
    except Institution.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Institution not found"},
            status=404,
        )

@api.get("/admin/events", response=List[EventAdminSchema])
@ensure_staff
def get_admin_events(request):
    events = Event.objects.all()
    return events

@api.get("/events", response=PaginatedEventsSchema, auth=None)
def get_events(request, offset: int = 0, limit: int = 20, year: str = None, search: str = None, showOnlyOpen: bool = False):
    from django.db.models import Q

    events = Event.objects.all()

    # Exclude archived events from public listing
    events = events.filter(is_archived=False)

    # Apply visibility filters
    if request.user.is_authenticated:
        if not request.user.is_superuser:
            events = events.filter(Q(published=True) | Q(admins=request.user))
    else:
        events = events.filter(published=True)

    # Apply search and filter criteria
    if year and year != 'all':
        events = events.filter(start_date__year=int(year))

    if search:
        events = events.filter(
            Q(name__icontains=search) |
            Q(venue__icontains=search) |
            Q(organizers_en__icontains=search) |
            Q(organizers_ko__icontains=search)
        )

    if showOnlyOpen:
        from datetime import datetime
        today = datetime.now().date()
        events = events.filter(Q(registration_deadline__isnull=True) | Q(registration_deadline__gte=today))

    # Sort, deduplicate, and get total count
    events = events.order_by('-start_date').distinct()
    total = events.count()

    # Apply pagination and prefetch organizers to prevent N+1 queries
    events = events[offset:offset + limit].prefetch_related('organizer_set')

    return {
        "events": list(events),
        "total": total,
        "offset": offset,
        "limit": limit
    }

@api.post("/admin/event/add", response=MessageSchema)
@ensure_staff
def add_event(request):
    data = json.loads(request.body)
    if not data["name"] or not data["venue"] or not data["start_date"] or not data["end_date"] or not data["capacity"]:
        return api.create_response(
            request,
            {"code": "missing_fields", "message": "Please fill all required fields."},
            status=400,
        )

    # Parse and validate main_languages
    main_languages_value = data.get("main_languages", [])
    if isinstance(main_languages_value, str):
        main_languages = json.loads(main_languages_value) if main_languages_value else []
    else:
        main_languages = main_languages_value

    # Set default to English if not provided
    if not main_languages:
        main_languages = ['en']
    email_template_registration = EmailTemplate.objects.create(
        subject=settings.ACCOUNT_EMAIL_SUBJECT_PREFIX+"Registration Confirmation for {{ event.name }}",
        body="Dear {{ attendee.first_name }},\n\n"
            "Thank you for registering for {{ event.name }}! Your registration has been confirmed.\n\n"
            "Event Details:\n"
            " - Dates: {{ event.start_date|date:'F d, Y' }} - {{ event.end_date|date:'F d, Y' }}\n"
            " - Venue: {{ event.venue }}\n"
            " - Official Website: {{ event.link_info }}\n"
            " - Registration: " + settings.HEADLESS_URL_ROOT + "/event/{{ event.id }}/register\n\n"
            "If you have any questions, please contact us at: " + settings.EMAIL_FROM + "\n\n"
            "We look forward to seeing you at the event!\n\n"
            "Warm regards,\n"
            "{{ event.organizers_en }}"
    )
    email_template_abstract_submission = EmailTemplate.objects.create(
        subject=settings.ACCOUNT_EMAIL_SUBJECT_PREFIX+"Abstract Submission Confirmation for {{ event.name }}",
        body="Dear {{ attendee.first_name }},\n\n"
            "Thank you for submitting your abstract for {{ event.name }}! Your submission has been confirmed.\n\n"
            "Abstract Details:\n"
            " - Title: {{ abstract.title }}\n"
            " - Presentation Type: {% if abstract.is_oral %}Oral Presentation{% else %}Poster Presentation{% endif %}\n\n"
            "If you need to make any changes to your submission, please contact us at: " + settings.EMAIL_FROM + "\n\n"
            "Thank you for your contribution to {{ event.name }}. We appreciate your participation.\n\n"
            "Warm regards,\n"
            "{{ event.organizers_en }}"
    )
    email_template_certificate = EmailTemplate.objects.create(
        subject=settings.ACCOUNT_EMAIL_SUBJECT_PREFIX+"Certificate of Attendance for {{ event.name }}",
        body="Dear {{ attendee.first_name }},\n\n"
            "Please find attached your certificate of attendance for {{ event.name }}.\n\n"
            "Thank you for your participation.\n\n"
            "Best regards,\n"
            "{{ event.organizers_en }}"
    )

    # Use provided link_info or default to empty (will be set after event creation)
    link_info = data.get("link_info", "").strip()

        # Default registration_deadline to day before start_date if not provided
    registration_deadline = data.get("registration_deadline")
    if not registration_deadline:
        from datetime import timedelta
        start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        registration_deadline = start_date - timedelta(days=1)

    event = Event.objects.create(
        name=data["name"],
        description=data.get("description", ""),
        category=data.get("category", "conference"),
        link_info=link_info if link_info else "temp",  # Temporary value
        start_date=data["start_date"],
        end_date=data["end_date"],
        venue=data["venue"],
        venue_ko=data.get("venue_ko", ""),
        venue_address=data.get("venue_address", ""),
        venue_address_ko=data.get("venue_address_ko", ""),
        venue_latitude=float(data["venue_latitude"]) if data.get("venue_latitude") else None,
        venue_longitude=float(data["venue_longitude"]) if data.get("venue_longitude") else None,
        main_languages=main_languages,
        registration_deadline=registration_deadline,
        capacity=data["capacity"],
        accepts_abstract=data["accepts_abstract"] == "true",
        abstract_submission_type=data.get("abstract_submission_type", "internal"),
        external_abstract_url=data.get("external_abstract_url", ""),
        email_template_registration=email_template_registration,
        email_template_abstract_submission=email_template_abstract_submission,
        email_template_certificate=email_template_certificate,
        onsite_code=generate_onsite_code(),
    )

    # Add organizers from provided data
    organizers_data = data.get("organizers", [])
    if isinstance(organizers_data, str):
        organizers_data = json.loads(organizers_data) if organizers_data else []
    for org in organizers_data:
        Organizer.objects.create(
            event=event,
            name=org.get("name", ""),
            korean_name=org.get("korean_name", ""),
            email=org.get("email", ""),
            affiliation=org.get("affiliation", ""),
            affiliation_ko=org.get("affiliation_ko", ""),
            order=org.get("order", 0),
        )

    # Set default link_info if not provided
    if not link_info:
        event.link_info = f"{settings.HEADLESS_URL_ROOT}/event/{event.id}"
        event.save()

    if data["accepts_abstract"] == "true" and data.get("abstract_submission_type", "internal") == "internal":
        event.abstract_deadline = data["abstract_deadline"]
        event.capacity_abstract = data["capacity_abstract"]
        event.max_votes = data["max_votes"]
        event.save()

    return {"code": "success", "message": "Event added."}

@api.get("/event/{event_id}", response=EventSchema, auth=None)
def get_event(request, event_id: int):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Event not found."},
            status=404,
        )

    # Archived events are not accessible (except to global admins)
    if event.is_archived:
        user = request.user
        if not user.is_authenticated or not (user.is_superuser or user.is_staff):
            return api.create_response(
                request,
                {"code": "not_found", "message": "Event not found."},
                status=404,
            )

    # Draft events are only accessible to event admins
    if not event.published:
        user = request.user
        if not user.is_authenticated:
            return api.create_response(
                request,
                {"code": "not_found", "message": "Event not found."},
                status=404,
            )
        # Check if user is superuser, staff, or event admin
        is_admin = user.is_superuser or user.is_staff or event.admins.filter(id=user.id).exists()
        if not is_admin:
            return api.create_response(
                request,
                {"code": "not_found", "message": "Event not found."},
                status=404,
            )

    return event

@api.get("/admin/event/{event_id}", response=EventAdminSchema)
@ensure_event_staff
def get_admin_event(request, event_id: int):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {},
            status=404,
        )
    return event

@api.post("/event/{event_id}/update", response=MessageSchema)
@ensure_event_staff
def update_event(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)
    event.name = data["name"]
    event.description = data.get("description", "")
    event.category = data.get("category", "conference")
    # Set default link_info if not provided or empty
    link_info = data.get("link_info", "").strip()
    event.link_info = link_info if link_info else f"{settings.HEADLESS_URL_ROOT}/event/{event.id}"
    event.start_date = data["start_date"]
    event.end_date = data["end_date"]
    event.venue = data["venue"]
    event.venue_ko = data.get("venue_ko", "")
    event.venue_address = data.get("venue_address", "")
    event.venue_address_ko = data.get("venue_address_ko", "")
    event.venue_latitude = float(data["venue_latitude"]) if data.get("venue_latitude") else None
    event.venue_longitude = float(data["venue_longitude"]) if data.get("venue_longitude") else None
    # Parse main_languages if it's a JSON string, otherwise use the array directly
    main_languages_value = data.get("main_languages", [])
    if isinstance(main_languages_value, str):
        main_languages = json.loads(main_languages_value) if main_languages_value else []
    else:
        main_languages = main_languages_value
    # Set default to English if empty
    event.main_languages = main_languages if main_languages else ['en']
        # Default registration_deadline to day before start_date if not provided
    if data.get("registration_deadline"):
        event.registration_deadline = data["registration_deadline"]
    else:
        from datetime import timedelta
        start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        event.registration_deadline = start_date - timedelta(days=1)
    event.capacity = data["capacity"]
    event.registration_fee = int(data["registration_fee"]) if data.get("registration_fee") not in [None, ""] else None
    event.accepts_abstract = data["accepts_abstract"] == "true"
    event.abstract_submission_type = data.get("abstract_submission_type", "internal")
    event.external_abstract_url = data.get("external_abstract_url", "")
    if "published" in data:
        event.published = data["published"] == "true"
    event.invitation_code = data.get("invitation_code", "").strip().upper()
    event.save()
    if event.accepts_abstract and event.abstract_submission_type == "internal":
        event.abstract_deadline = data["abstract_deadline"] if data["abstract_deadline"] else None
        event.capacity_abstract = int(data["capacity_abstract"]) if data.get("capacity_abstract") not in [None, ""] else 0
        event.max_votes = int(data["max_votes"]) if data.get("max_votes") not in [None, ""] else 2
        event.save()

    return {"code": "success", "message": "Event updated."}

@api.post("/event/{event_id}/toggle_published", response=MessageSchema)
@ensure_event_staff
def toggle_published(request, event_id: int):
    event = Event.objects.get(id=event_id)
    event.published = not event.published
    event.save()
    return {"code": "success", "message": "Event published status updated."}

@api.post("/admin/event/{event_id}/archive", response=MessageSchema)
@ensure_staff
def archive_event(request, event_id: int):
    try:
        event = Event.objects.get(id=event_id)
        event.is_archived = not event.is_archived
        event.save()
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Event not found."},
            status=404,
        )
    return {"code": "success", "message": "Event archived." if event.is_archived else "Event unarchived."}

@api.post("/event/{event_id}/nametag_settings", response=MessageSchema)
@ensure_event_staff
def update_nametag_settings(request, event_id: int):
    """Update nametag paper size and orientation settings for an event"""
    data = json.loads(request.body)
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Event not found."},
            status=404,
        )

    if "nametag_paper_width" in data:
        event.nametag_paper_width = float(data["nametag_paper_width"])
    if "nametag_paper_height" in data:
        event.nametag_paper_height = float(data["nametag_paper_height"])
    if "nametag_orientation" in data:
        event.nametag_orientation = data["nametag_orientation"]

    event.save()
    return {"code": "success", "message": "Nametag settings updated."}

@api.post("/event/{event_id}/emailtemplates", response=MessageSchema)
@ensure_event_staff
def update_event_emailtemplates(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)
    event.email_template_registration.subject = data["email_template_registration_subject"]
    event.email_template_registration.body = data["email_template_registration_body"]
    event.email_template_registration.save()
    event.email_template_abstract_submission.subject = data["email_template_abstract_submission_subject"]
    event.email_template_abstract_submission.body = data["email_template_abstract_submission_body"]
    event.email_template_abstract_submission.save()
    # Handle certificate template (may not exist for older events)
    if event.email_template_certificate:
        event.email_template_certificate.subject = data["email_template_certificate_subject"]
        event.email_template_certificate.body = data["email_template_certificate_body"]
        event.email_template_certificate.save()
    else:
        # Create certificate template if it doesn't exist
        event.email_template_certificate = EmailTemplate.objects.create(
            subject=data["email_template_certificate_subject"],
            body=data["email_template_certificate_body"]
        )
        event.save()
    return {"code": "success", "message": "Email templates updated."}

@api.get("/event/{event_id}/registered", response=RegistrationStatusSchema)
def check_registration_status(request, event_id: int):
    user = request.user
    event = Event.objects.get(id=event_id)
    attendee = event.attendees.filter(user__id=user.id).first()

    if not attendee:
        return {"registered": False, "payment_status": None}

    # Check payment status if event has a fee
    # A registration is considered paid if there's at least one completed payment
    payment_status = None
    if event.registration_fee and event.registration_fee > 0:
        payments = PaymentHistory.objects.filter(attendee=attendee)
        if payments.filter(status='completed').exists():
            payment_status = 'completed'
        else:
            # No completed payments - show as pending (even if there are cancelled payments)
            payment_status = 'pending'

    return {"registered": True, "payment_status": payment_status}

@api.get("/event/{event_id}/questions", response=List[QuestionSchema])
def get_event_questions(request, event_id: int):
    event = Event.objects.get(id=event_id)
    questions = event.custom_questions.all()
    return questions

@api.post("/event/{event_id}/questions", response=MessageSchema)
@ensure_event_staff
def update_event_questions(request, event_id: int):
    event = Event.objects.get(id=event_id)
    data = json.loads(request.body)
    for q in event.custom_questions.all():
        if not any(q.id == q2.get("id") for q2 in data["questions"]):
            q.delete()
    for idx, q in enumerate(data["questions"]):
        if q.get("id") == -1:
            cq = CustomQuestion.objects.create(
                event=event,
                question=q["question"],
                order=idx
            )
        else:
            # Validate question belongs to this event to prevent cross-event modification
            cq = CustomQuestion.objects.get(id=q["id"], event=event)
            cq.question = q["question"]
            cq.order = idx
            cq.save()
            for ca in CustomAnswer.objects.filter(reference=cq):
                ca.question = q["question"]["question"]
                ca.save()
    return {"code": "success", "message": "Questions updated."}

@api.get("/event/{event_id}/stats", response=StatsSchema)
@ensure_event_staff
def get_event_stats(request, event_id: int):
    event = Event.objects.get(id=event_id)
    return {
        "registered": event.attendees.count(),
        "abstracts": event.abstracts.count(),
    }

@api.get("/event/{event_id}/attendees", response=List[AttendeeSchema])
@ensure_event_staff
def get_event_attendees(request, event_id: int, all: bool = False):
    event = Event.objects.get(id=event_id)
    attendees = event.attendees.all()

    # If event has a registration fee, filter to only those with completed payments
    # Unless all=True is passed (for admin use like manual payment creation)
    if not all and event.registration_fee and event.registration_fee > 0:
        attendees = attendees.filter(payments__status='completed').distinct()

    return attendees

@api.get("/event/{event_id}/registration", response=AttendeeSchema)
def get_my_registration(request, event_id: int):
    user = request.user
    event = Event.objects.get(id=event_id)
    try:
        attendee = event.attendees.get(user__id=user.id)
        return attendee
    except:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Registration not found"},
            status=404,
        )

@api.get("/event/{event_id}/registration/payment", response=PaymentHistorySchema)
def get_my_registration_payment(request, event_id: int):
    user = request.user
    event = Event.objects.get(id=event_id)
    try:
        attendee = event.attendees.get(user__id=user.id)
        # Get the latest completed payment, or latest payment if none completed
        payment = PaymentHistory.objects.filter(attendee=attendee, status='completed').order_by('-created_at').first()
        if not payment:
            payment = PaymentHistory.objects.filter(attendee=attendee).order_by('-created_at').first()
        if not payment:
            raise PaymentHistory.DoesNotExist()

        # Construct attendee name
        name_parts = [attendee.first_name or '']
        if attendee.middle_initial:
            name_parts.append(attendee.middle_initial)
        name_parts.append(attendee.last_name or '')
        attendee_name = ' '.join(filter(None, name_parts))
        if attendee.korean_name:
            attendee_name = f"{attendee_name} ({attendee.korean_name})" if attendee_name else attendee.korean_name

        return {
            'number': payment.toss_order_id or str(payment.id),
            'checkout_date': payment.created_at.strftime('%Y-%m-%d'),
            'amount': payment.amount,
            'event_id': event.id,
            'event_name': event.name,
            'start_date': event.start_date.strftime('%Y-%m-%d'),
            'end_date': event.end_date.strftime('%Y-%m-%d'),
            'venue': event.venue,
            'venue_ko': event.venue_ko,
            'organizers_en': event.organizers_en,
            'organizers_ko': event.organizers_ko,
            'status': payment.status,
            'payment_type': payment.payment_type,
            'attendee_name': attendee_name,
            'attendee_name_ko': attendee.korean_name or '',
            'attendee_institute': attendee.institute or '',
            'attendee_institute_ko': attendee.institute_ko or '',
        }
    except PaymentHistory.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Payment not found"},
            status=404,
        )
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Registration not found"},
            status=404,
        )

@api.post("/event/{event_id}/attendee/{attendee_id}/update", response=MessageSchema)
@ensure_event_staff
def update_attendee(request, event_id: int, attendee_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)
    attendee = Attendee.objects.get(id=attendee_id, event=event)

    if "is_attended" in data:
        attendee.is_attended = data.get("is_attended", False)

    if "first_name" in data or "nationality" in data:
        attendee.first_name = data.get("first_name", "")
        attendee.middle_initial = data.get("middle_initial", "")
        attendee.last_name = data.get("last_name", "")
        attendee.korean_name = data.get("korean_name", "")
        attendee.nationality = data["nationality"]

        # Update institution - accept either an integer ID or a string name
        institute_val = data.get("institute")
        if institute_val:
            try:
                institution = Institution.objects.get(id=int(institute_val))
                attendee.institute = institution.name_en
                attendee.institute_ko = institution.name_ko
            except (ValueError, TypeError):
                # String name passed directly (e.g. from attendee edit modal)
                attendee.institute = str(institute_val)
            except Institution.DoesNotExist:
                return api.create_response(
                    request,
                    {"code": "invalid_institution", "message": "Invalid institution"},
                    status=400,
                )

        attendee.department = data.get("department", "")
        attendee.job_title = data.get("job_title", "")
        attendee.disability = data.get("disability", "")
        attendee.dietary = data.get("dietary", "")

    attendee.save()
    return {"code": "success", "message": "Successfully updated."}

@api.post("/event/{event_id}/attendee/{attendee_id}/answers", response=MessageSchema)
@ensure_event_staff
def update_event_answers(request, event_id: int, attendee_id: int):
    data = json.loads(request.body)
    answers = data.get("answers", [])
    references = [a["reference_id"] for a in answers if a["reference_id"] is not None]
    if len(references) != len(set(references)):
        return api.create_response(
            request,
            {"code": "duplicated_references", "message": "Duplicated references found."},
            status=400,
        )
    event = Event.objects.get(id=event_id)
    attendee = Attendee.objects.get(id=attendee_id, event=event)
    custom_answer = CustomAnswer.objects.filter(attendee=attendee)
    custom_answer.delete()
    for a in answers:
        # Validate reference belongs to this event to prevent cross-event data leakage
        reference_question = CustomQuestion.objects.get(id=a["reference_id"], event=event) if not (a["reference_id"] == -1 or a["reference_id"] is None) else None
        CustomAnswer.objects.create(
            reference=reference_question,
            attendee=attendee,
            question=reference_question.question["question"] if reference_question else a["question"],
            answer=a["answer"]
        )
    return {"code": "success", "message": "Answers updated."}

@api.post("/event/{event_id}/verify_invitation_code", response=MessageSchema)
def verify_invitation_code(request, event_id: int):
    """Verify invitation code for an event"""
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Event not found."},
            status=404,
        )
    if not event.invitation_code:
        return {"code": "success", "message": "No invitation code required."}
    data = json.loads(request.body)
    submitted_code = data.get("invitation_code", "").strip().upper()
    if submitted_code != event.invitation_code:
        return api.create_response(
            request,
            {"code": "invalid_invitation_code", "message": "Invalid invitation code. Please check and try again."},
            status=400,
        )
    return {"code": "success", "message": "Valid invitation code."}

@api.post("/event/{event_id}/register", response=MessageSchema)
def register_event(request, event_id: int):
    # get the deadline for registration
    user = request.user
    event = Event.objects.get(id=event_id)
    if event.registration_deadline is not None and datetime.now().date() > event.registration_deadline:
            return api.create_response(
                request,
                {"code": "deadline_passed", "message": "Sorry, registration deadline has passed."},
                status=400,
            )
    if event.capacity > 0 and event.capacity <= event.attendees.count():
        return api.create_response(
            request,
            {"code": "event_full", "message": "Sorry, event is full."},
            status=400,
        )

    if event.attendees.filter(user=user).exists():
        return api.create_response(
            request,
            {"code": "already_registered", "message": "You are already registered."},
            status=400,
        )

    data = json.loads(request.body)

    # Validate invitation code if event is invitation-only
    if event.invitation_code:
        submitted_code = data.get("invitation_code", "").strip().upper()
        if submitted_code != event.invitation_code:
            return api.create_response(
                request,
                {"code": "invalid_invitation_code", "message": "Invalid invitation code. Please check and try again."},
                status=400,
            )
    for q in event.custom_questions.all():
        if q.question["type"] == "select":
            for oidx, option in enumerate(q.question["options"]):
                if not data.get(f"{q.id}"):
                    return api.create_response(
                        request,
                        {"code": "missing_answer", "message": "Please select an option for the question: "+ q.question['question']},
                        status=400,
                    )

    # Get institution by ID to retrieve both English and Korean names
    institute_id = data.get("institute")
    if institute_id:
        try:
            institution = Institution.objects.get(id=int(institute_id))
            institute_name_en = institution.name_en
            institute_name_ko = institution.name_ko
        except (Institution.DoesNotExist, ValueError):
            return api.create_response(
                request,
                {"code": "invalid_institution", "message": "Invalid institution"},
                status=400,
            )
    else:
        return api.create_response(
            request,
            {"code": "missing_institute", "message": "Institute is required"},
            status=400,
        )

    attendee = Attendee.objects.create(
        user=user,
        event=event,
        first_name=data.get("first_name", ""),
        middle_initial=data.get("middle_initial", ""),
        last_name=data.get("last_name", ""),
        korean_name=data.get("korean_name", ""),
        nationality=data["nationality"],
        institute=institute_name_en,
        institute_ko=institute_name_ko,
        department=data.get("department", ""),
        job_title=data.get("job_title", ""),
        disability=data.get("disability", ""),
        dietary=data.get("dietary", "")
    )

    for q in event.custom_questions.all():
        if q.question["type"] == "checkbox":
            answer = '\n'.join([f"- {option}: {data.get(f"{q.id}_{oidx}")}" for oidx, option in enumerate(q.question["options"])])
        else:
            answer = data.get(f"{q.id}")
        CustomAnswer.objects.create(
            reference=q,
            attendee=attendee,
            question=q.question["question"],
            answer=answer
        )

    event.attendees.add(attendee)

    send_mail.delay(
        Template(event.email_template_registration.subject).render(Context({"event": event, "attendee": attendee}, autoescape=False)),
        Template(event.email_template_registration.body).render(Context({"event": event, "attendee": attendee}, autoescape=False)),
        user.email
    )

    return {"code": "success", "message": "Successfully registered."}

@api.post("/event/{event_id}/attendee/{attendee_id}/deregister", response=MessageSchema)
@ensure_event_staff
def deregister_event(request, event_id: int, attendee_id: int):
    event = Event.objects.get(id=event_id)
    Attendee.objects.get(id=attendee_id, event=event).delete()
    return {"code": "success", "message": "Successfully deregistered!"}

@api.post("/event/{event_id}/change-request", response=MessageSchema)
def request_change(request, event_id: int):
    user = request.user
    event = Event.objects.get(id=event_id)

    # Verify user is registered for this event
    try:
        attendee = Attendee.objects.get(user=user, event=event)
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_registered", "message": "You are not registered for this event."},
            status=400,
        )

    data = json.loads(request.body)
    message = data.get("message", "").strip()

    if not message:
        return api.create_response(
            request,
            {"code": "empty_message", "message": "Please provide a message."},
            status=400,
        )

    # Send email to all event admins
    admin_emails = list(event.admins.values_list('email', flat=True))

    if not admin_emails:
        return api.create_response(
            request,
            {"code": "no_admins", "message": "No administrators configured for this event."},
            status=400,
        )

    # Build attendee name
    attendee_name = f"{attendee.first_name} {attendee.last_name}"
    if attendee.korean_name:
        attendee_name += f" ({attendee.korean_name})"

    subject = f"[KASRA Events] Registration Change Request from {attendee_name}"
    body = f"""A registration change/cancellation request has been received.

Event: {event.name}
Attendee: {attendee_name}
Email: {user.email}
Institute: {attendee.institute}

Request Message:
{message}

Please review and respond to this request.
"""

    for admin_email in admin_emails:
        send_mail.delay(subject, body, admin_email)

    return {"code": "success", "message": "Your request has been submitted."}

@api.post("/event/{event_id}/abstract", response=MessageSchema)
def submit_abstract(request, event_id: int):
    event = Event.objects.get(id=event_id)
    if not event.accepts_abstract:
        return api.create_response(
            request,
            {"code": "not_accepted", "message": "This event does not accept abstracts."},
            status=400,
        )
    if event.abstract_submission_type == 'external':
        return api.create_response(
            request,
            {"code": "external_abstract", "message": "This event uses an external abstract submission system."},
            status=400,
        )

    attendee = Attendee.objects.get(user=request.user, event=event)
    if attendee.abstracts.filter(event_id=event_id).exists():
        return api.create_response(
            request,
            {"code": "already_submitted", "message": "You have already submitted an abstract."},
            status=400,
        )

    data = json.loads(request.body)
    if event.abstract_deadline is not None and datetime.now().date() > event.abstract_deadline:
        return api.create_response(
            request,
            {"code": "deadline_passed", "message": "Sorry, abstract submission deadline has passed."},
            status=400,
        )
    
    if event.capacity_abstract > 0 and event.capacity_abstract <= event.abstracts.count():
        return api.create_response(
            request,
            {"code": "event_full", "message": "Sorry, abstract submission limit reached."},
            status=400,
        )

    # create the abstract with the post json data
    data = json.loads(request.body)
    file_name = data["file_name"]
    try:
        file_content = base64.b64decode(data["file_content"].split(",")[1])
    except (ValueError, IndexError):
        return api.create_response(
            request,
            {"code": "invalid_file", "message": "Invalid file content encoding."},
            status=400,
        )

    # Validate file upload for security
    is_valid, error_message = validate_abstract_file(file_name, file_content)
    if not is_valid:
        return api.create_response(
            request,
            {"code": "invalid_file", "message": error_message},
            status=400,
        )

    # Use sanitized filename
    safe_filename = sanitize_filename(file_name)
    file_path = f"abstracts/{uuid.uuid4()}/{safe_filename}"
    file = ContentFile(file_content)
    default_storage.save(file_path, file)

    abstract_type = data.get("type", "poster")
    wants_short_talk = data.get("wants_short_talk", "false") == "true"

    Abstract.objects.create(
        attendee=attendee,
        event=event,
        title=data["title"],
        type=abstract_type,
        wants_short_talk=wants_short_talk if abstract_type == "poster" else False,
        file_path=file_path,
    )

    send_mail.delay(
        Template(event.email_template_abstract_submission.subject).render(Context({"event": event, "abstract": Abstract.objects.get(attendee=attendee, event=event)}, autoescape=False)),
        Template(event.email_template_abstract_submission.body).render(Context({"attendee": attendee, "event": event, "abstract": Abstract.objects.get(attendee=attendee, event=event)}, autoescape=False)),
        attendee.user.email
    )

    return {"code": "success", "message": "Successfully submitted!"}

@api.get("/event/{event_id}/speakers", response=List[SpeakerSchema], auth=None)
def get_speakers(request, event_id: int):
    event = Event.objects.get(id=event_id)
    return event.speakers.all()

@api.post("/event/{event_id}/speaker/add", response=MessageSchema)
@ensure_event_staff
def add_speaker(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)

    if not data.get("name") or not data.get("email") or not data.get("affiliation") or data.get("is_domestic") is None or not data.get("type"):
        return api.create_response(
            request,
            {"code": "missing_fields", "message": "Please fill all fields."},
            status=400,
        )

    speaker = event.speakers.create(
        name=data["name"],
        korean_name=data.get("korean_name", ""),
        email=data["email"],
        affiliation=data["affiliation"],
        affiliation_ko=data.get("affiliation_ko", ""),
        is_domestic=data["is_domestic"],
        type=data["type"],
    )
    return {"code": "success", "message": "Speaker added."}

@api.post("/event/{event_id}/speaker/{speaker_id}/update", response=MessageSchema)
@ensure_event_staff
def update_speaker(request, event_id: int, speaker_id: int):
    event = Event.objects.get(id=event_id)
    speaker = event.speakers.get(id=speaker_id)
    data = json.loads(request.body)
    speaker.name = data["name"]
    speaker.korean_name = data.get("korean_name", "")
    speaker.email = data["email"]
    speaker.affiliation = data["affiliation"]
    speaker.affiliation_ko = data.get("affiliation_ko", "")
    speaker.is_domestic = data["is_domestic"]
    speaker.type = data["type"]
    speaker.save()
    return {"code": "success", "message": "Speaker updated."}

@api.post("/event/{event_id}/speaker/{speaker_id}/delete", response=MessageSchema)
@ensure_event_staff
def delete_speaker(request, event_id: int, speaker_id: int):
    event = Event.objects.get(id=event_id)
    speaker = event.speakers.get(id=speaker_id)
    speaker.delete()
    return {"code": "success", "message": "Speaker deleted."}

@api.post("/event/{event_id}/send_emails", response=MessageSchema)
@ensure_event_staff
def send_emails(request, event_id: int):
    data = json.loads(request.body)

    # Sanitize subject to prevent email header injection
    subject = sanitize_email_header(data.get('subject', ''))
    body = data.get('body', '')

    if not subject:
        return api.create_response(
            request,
            {"code": "invalid_subject", "message": "Subject is required."},
            status=400,
        )

    recipients = data["to"].split("; ")
    valid_recipients = []

    for recipient in recipients:
        recipient = recipient.strip()
        if validate_email_format(recipient):
            valid_recipients.append(recipient)

    if not valid_recipients:
        return api.create_response(
            request,
            {"code": "invalid_recipients", "message": "No valid email addresses provided."},
            status=400,
        )

    for recipient in valid_recipients:
        send_mail.delay(subject, body, recipient)

    return {"code": "success", "message": f"Emails sent to {len(valid_recipients)} recipients."}

@api.post("/event/{event_id}/send_certificate", response=MessageSchema)
@ensure_event_staff
def send_certificate(request, event_id: int):
    """Send a certificate PDF to an email address."""
    data = json.loads(request.body)
    email = data.get("email")
    pdf_base64 = data.get("pdf_base64")
    attendee_id = data.get("attendee_id")
    attendee_type = data.get("attendee_type", "attendee")  # "attendee" or "onsite"

    if not email or not pdf_base64:
        return api.create_response(
            request,
            {"code": "missing_data", "message": "Email and PDF data are required."},
            status=400,
        )

    event = Event.objects.get(id=event_id)

    # Look up the actual attendee
    attendee = None
    if attendee_id:
        if attendee_type == "onsite":
            try:
                attendee = OnSiteAttendee.objects.get(id=attendee_id, event=event)
            except OnSiteAttendee.DoesNotExist:
                pass
        else:
            try:
                attendee = Attendee.objects.get(id=attendee_id, event=event)
            except Attendee.DoesNotExist:
                pass

    if attendee is None:
        return api.create_response(
            request,
            {"code": "attendee_not_found", "message": "Attendee not found."},
            status=404,
        )

    context = Context({"event": event, "attendee": attendee}, autoescape=False)
    subject = Template(event.email_template_certificate.subject).render(context)
    body = Template(event.email_template_certificate.body).render(context)

    send_mail_with_attachment.delay(
        subject,
        body,
        email,
        f"Certificate_{attendee.first_name.replace(' ', '_')}.pdf",
        pdf_base64
    )
    return {"code": "success", "message": "Certificate sent."}

@api.get("/event/{event_id}/reviewers", response=List[AttendeeSchema])
@ensure_event_staff
def get_reviewers(request, event_id: int):
    event = Event.objects.get(id=event_id)
    return event.reviewers.all()

@api.post("/event/{event_id}/reviewer/add", response=MessageSchema)
@ensure_event_staff
def add_reviewer(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)
    attendee = Attendee.objects.get(event=event, id=data["id"])
    # check if the user is already a reviewer
    if attendee in event.reviewers.all():
        return api.create_response(
            request,
            {"code": "already_reviewer", "message": "User is already a reviewer."},
            status=400,
        )
    event.reviewers.add(attendee)
    AbstractVote.objects.create(reviewer=attendee)
    return {"code": "success", "message": "Reviewer added."}

@api.post("/event/{event_id}/reviewer/{reviewer_id}/delete", response=MessageSchema)
@ensure_event_staff
def delete_reviewer(request, event_id: int, reviewer_id: int):
    event = Event.objects.get(id=event_id)
    attendee = Attendee.objects.get(event=event, id=reviewer_id)
    event.reviewers.remove(attendee)
    AbstractVote.objects.get(reviewer=attendee).delete()
    return {"code": "success", "message": "Reviewer deleted."}

@api.get("/event/{event_id}/abstracts", response=List[AbstractShortSchema])
def get_abstracts(request, event_id: int):
    user = request.user
    if not (user.is_staff or
            user in Event.objects.get(id=event_id).admins.all() or
            user in Event.objects.get(id=event_id).reviewers.all()):
        return api.create_response(
            request,
            {"code": "permission_denied", "message": "Permission denied"},
            status=403,
        )
    event = Event.objects.get(id=event_id)
    abstracts = event.abstracts.all()
    return abstracts

@api.get("/event/{event_id}/abstract", response=AbstractUserSchema)
def get_user_abstract(request, event_id: int):
    user = request.user
    event = Event.objects.get(id=event_id)
    try:
        attendee = Attendee.objects.get(user=user, event=event)
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_registered", "message": "You are not registered for this event."},
            status=404,
        )
    try:
        abstract = attendee.abstracts.get(event_id=event_id)
    except Abstract.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Abstract not found."},
            status=404,
        )
    return abstract

@api.get("/event/{event_id}/abstract/{abstract_id}", response=AbstractSchema)
def get_abstract(request, event_id: int, abstract_id: int):
    user = request.user
    if not (user.is_staff or
            user in Event.objects.get(id=event_id).admins.all() or
            user in Event.objects.get(id=event_id).reviewers.all()):
        return api.create_response(
            request,
            {"code": "permission_denied", "message": "Permission denied"},
            status=403,
        )
    event = Event.objects.get(id=event_id)
    abstract = event.abstracts.get(id=abstract_id)
    return abstract

@api.post("/event/{event_id}/abstract/{abstract_id}/update", response=MessageSchema)
@ensure_event_staff
def update_abstract(request, event_id: int, abstract_id: int):
    event = Event.objects.get(id=event_id)
    abstract = event.abstracts.get(id=abstract_id)
    data = json.loads(request.body)
    abstract.title = data["title"]
    abstract.type = data.get("type", "poster")
    abstract.wants_short_talk = data.get("wants_short_talk", False) if abstract.type == "poster" else False
    abstract.save()
    return {"code": "success", "message": "Abstract updated."}

@api.post("/event/{event_id}/abstract/{abstract_id}/delete", response=MessageSchema)
@ensure_event_staff
def delete_abstract(request, event_id: int, abstract_id: int):
    event = Event.objects.get(id=event_id)
    abstract = event.abstracts.get(id=abstract_id)
    abstract.delete()
    return {"code": "success", "message": "Abstract deleted."}

@api.get("/event/{event_id}/reviewer", response=bool)
def is_reviewer(request, event_id: int):
    event = Event.objects.get(id=event_id)
    if not event.accepts_abstract:
        return False # Event does not accept abstracts
    user = request.user
    try:
        attendee = Attendee.objects.get(user=user, event_id=event_id)
    except Attendee.DoesNotExist:
        return False # User is not registered to the event
    return attendee in Event.objects.get(id=event_id).reviewers.all()

@api.get("/event/{event_id}/reviewer/vote", response=AbstractVoteSchema)
def get_reviewer_votes(request, event_id: int):
    event = Event.objects.get(id=event_id)
    if not event.accepts_abstract:
        return api.create_response(
            request,
            {"code": "not_accepted", "message": "This event does not accept abstracts."},
            status=400,
        )
    if event.abstract_deadline is not None and datetime.now().date() < event.abstract_deadline:
        return api.create_response(
            request,
            {"code": "deadline_not_passed", "message": "Abstract submission deadline has not passed."},
            status=400,
        )
    user = request.user
    if not (user.is_staff or
            user in Event.objects.get(id=event_id).admins.all() or
            user in Event.objects.get(id=event_id).reviewers.all()):
        return api.create_response(
            request,
            {"code": "permission_denied", "message": "Permission denied"},
            status=403,
        )
    event = Event.objects.get(id=event_id)
    reviewer = Attendee.objects.get(user=user, event=event)
    votes = AbstractVote.objects.get(reviewer=reviewer)
    return votes

@api.post("/event/{event_id}/reviewer/vote", response=MessageSchema)
def vote_abstract(request, event_id: int):
    event = Event.objects.get(id=event_id)
    if not event.accepts_abstract:
        return api.create_response(
            request,
            {"code": "not_accepted", "message": "This event does not accept abstracts."},
            status=400,
        )
    if event.abstract_deadline is not None and datetime.now().date() < event.abstract_deadline:
        return api.create_response(
            request,
            {"code": "deadline_not_passed", "message": "Abstract submission deadline has not passed."},
            status=400,
        )
    user = request.user
    event = Event.objects.get(id=event_id)
    reviewer = Attendee.objects.get(user=user, event=event)
    data = json.loads(request.body)
    vote = AbstractVote.objects.get(reviewer=reviewer)
    for abstract_id in data["voted_abstracts"]:
        # Validate abstract belongs to this event to prevent cross-event voting
        vote.voted_abstracts.add(Abstract.objects.get(id=abstract_id, event=event))
    return {"code": "success", "message": "Votes submitted."}

@api.get("/admin/users", response=List[UserSchema])
@ensure_staff
def get_all_users(request):
    return User.objects.all().order_by('-date_joined')

@api.post("/admin/user/{user_id}/toggle-active", response=MessageSchema)
@ensure_staff
def toggle_user_active(request, user_id: int):
    # Prevent users from deactivating themselves
    if request.user.id == user_id:
        return api.create_response(
            request,
            {"code": "self_action_denied", "message": "You cannot deactivate yourself."},
            status=400,
        )

    try:
        user = User.objects.get(id=user_id)
        user.is_active = not user.is_active
        user.save()
        status = "activated" if user.is_active else "deactivated"
        return {"code": "success", "message": f"User {status} successfully."}
    except User.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "User not found."},
            status=404,
        )

@api.post("/admin/user/{user_id}/toggle-verified", response=MessageSchema)
@ensure_staff
def toggle_user_verified(request, user_id: int):
    from allauth.account.models import EmailAddress
    try:
        user = User.objects.get(id=user_id)
        email_address = EmailAddress.objects.filter(user=user, primary=True).first()
        if email_address:
            email_address.verified = not email_address.verified
            email_address.save()
            status = "verified" if email_address.verified else "unverified"
            return {"code": "success", "message": f"User email {status} successfully."}
        else:
            return api.create_response(
                request,
                {"code": "not_found", "message": "Email address not found."},
                status=404,
            )
    except User.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "User not found."},
            status=404,
        )

@api.post("/admin/user/{user_id}/update", response=UserSchema)
@ensure_staff
def update_user_by_admin(request, user_id: int):
    try:
        user = User.objects.get(id=user_id)
        data = json.loads(request.body)

        # Update user fields
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "middle_initial" in data:
            user.middle_initial = data["middle_initial"]
        if "korean_name" in data:
            user.korean_name = data["korean_name"]
        if "nationality" in data:
            user.nationality = int(data["nationality"])
        if "institute" in data:
            institute_id = int(data["institute"]) if data["institute"] else None
            user.institute_id = institute_id
        if "department" in data:
            user.department = data["department"]
        if "job_title" in data:
            user.job_title = data["job_title"]
        if "disability" in data:
            user.disability = data["disability"]
        if "dietary" in data:
            user.dietary = data["dietary"]

        user.save()
        return user
    except User.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "User not found."},
            status=404,
        )

@api.post("/generate-verification-key", response=VerificationKeyResponseSchema, auth=None)
def generate_verification_key(request, data: GenerateVerificationKeySchema):
    import secrets
    from datetime import timedelta
    from django.utils import timezone
    from allauth.account.models import EmailAddress
    from main.models import EmailVerificationKey

    email = data.email

    try:
        user = User.objects.get(email__iexact=email)
        email_address = EmailAddress.objects.filter(user=user, email__iexact=email).first()

        # If not found, try getting the primary email
        if not email_address:
            email_address = EmailAddress.objects.filter(user=user, primary=True).first()

        if email_address and not email_address.verified:
            # Generate random alphanumeric key
            verification_key = secrets.token_urlsafe(32)

            # Delete any existing keys for this email older than 1 hour
            one_hour_ago = timezone.now() - timedelta(hours=1)
            EmailVerificationKey.objects.filter(email=email, created_at__lt=one_hour_ago).delete()

            # Delete any existing keys for this email to prevent duplicates
            EmailVerificationKey.objects.filter(email=email).delete()

            # Store in database
            EmailVerificationKey.objects.create(
                email=email,
                verification_key=verification_key
            )

            return {"key": verification_key}
        else:
            # Email is verified or not found, return empty key
            return {"key": ""}
    except User.DoesNotExist:
        return {"key": ""}

@api.post("/resend-verification", response=MessageSchema, auth=None)
def resend_verification_email(request, data: ResendVerificationSchema):
    from datetime import timedelta
    from django.utils import timezone
    from allauth.account.models import EmailAddress
    from allauth.account.utils import send_email_confirmation
    from main.models import EmailVerificationKey

    email = data.email
    verification_key = data.verification_key

    # Verify the key from database
    try:
        # Keys older than 1 hour are considered expired
        one_hour_ago = timezone.now() - timedelta(hours=1)
        key_record = EmailVerificationKey.objects.filter(
            email=email,
            verification_key=verification_key,
            created_at__gte=one_hour_ago
        ).first()

        if not key_record:
            return api.create_response(
                request,
                {"code": "invalid_key", "message": "Invalid or expired verification key."},
                status=401,
            )

        user = User.objects.get(email=email)
        email_address = EmailAddress.objects.filter(user=user, email=email).first()

        if email_address and not email_address.verified:
            # Use allauth's internal function to send verification email
            send_email_confirmation(request, user)

            # Delete the used key
            key_record.delete()

            return {"code": "success", "message": "Verification email sent successfully."}
        elif email_address and email_address.verified:
            # Clean up the key
            key_record.delete()
            return api.create_response(
                request,
                {"code": "already_verified", "message": "Email is already verified."},
                status=400,
            )
        else:
            return api.create_response(
                request,
                {"code": "not_found", "message": "Email address not found."},
                status=404,
            )
    except User.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "User not found."},
            status=404,
        )

@api.get("/users", response=List[UserSchema])
@ensure_staff
def get_users(request):
    return User.objects.all()

@api.get("/event/{event_id}/eventadmins", response=List[UserSchema])
@ensure_event_staff
def get_event_admins(request, event_id: int):
    event = Event.objects.get(id=event_id)
    return event.admins.all()

@api.post("/event/{event_id}/eventadmin/add", response=MessageSchema)
@ensure_event_staff
def add_event_admin(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)
    user = User.objects.get(id=data["id"])
    if user in event.admins.all():
        return api.create_response(
            request,
            {"code": "already_admin", "message": "User is already an admin."},
            status=400,
        )
    event.admins.add(user)
    return {"code": "success", "message": "Admin added."}

@api.post("/event/{event_id}/eventadmin/{admin_id}/delete", response=MessageSchema)
@ensure_event_staff
def delete_event_admin(request, event_id: int, admin_id: int):
    event = Event.objects.get(id=event_id)
    user = User.objects.get(id=admin_id)
    event.admins.remove(user)
    return {"code": "success", "message": "Admin deleted."}

@api.get("/event/{event_id}/organizers", response=List[OrganizerSchema])
@ensure_event_staff
def get_organizers(request, event_id: int):
    event = Event.objects.get(id=event_id)
    return event.organizer_set.all()

@api.post("/event/{event_id}/organizer/add", response=MessageSchema)
@ensure_event_staff
def add_organizer(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)

    if not data.get("name"):
        return api.create_response(
            request,
            {"code": "missing_fields", "message": "Name is required."},
            status=400,
        )

    max_order = event.organizer_set.aggregate(Max('order'))['order__max'] or -1
    Organizer.objects.create(
        event=event,
        name=data["name"],
        korean_name=data.get("korean_name", ""),
        email=data.get("email", ""),
        affiliation=data.get("affiliation", ""),
        affiliation_ko=data.get("affiliation_ko", ""),
        order=max_order + 1,
    )
    return {"code": "success", "message": "Organizer added."}

@api.post("/event/{event_id}/organizer/{organizer_id}/update", response=MessageSchema)
@ensure_event_staff
def update_organizer(request, event_id: int, organizer_id: int):
    event = Event.objects.get(id=event_id)
    organizer = event.organizer_set.get(id=organizer_id)
    data = json.loads(request.body)
    organizer.name = data["name"]
    organizer.korean_name = data.get("korean_name", "")
    organizer.email = data.get("email", "")
    organizer.affiliation = data.get("affiliation", "")
    organizer.affiliation_ko = data.get("affiliation_ko", "")
    organizer.save()
    return {"code": "success", "message": "Organizer updated."}

@api.post("/event/{event_id}/organizer/{organizer_id}/delete", response=MessageSchema)
@ensure_event_staff
def delete_organizer(request, event_id: int, organizer_id: int):
    event = Event.objects.get(id=event_id)
    organizer = event.organizer_set.get(id=organizer_id)
    organizer.delete()
    return {"code": "success", "message": "Organizer deleted."}

@api.post("/event/{event_id}/organizers/reorder", response=MessageSchema)
@ensure_event_staff
def reorder_organizers(request, event_id: int):
    data = json.loads(request.body)
    event = Event.objects.get(id=event_id)
    order = data.get("order", [])
    for idx, org_id in enumerate(order):
        event.organizer_set.filter(id=org_id).update(order=idx)
    return {"code": "success", "message": "Organizers order updated."}

@api.get("/event/{event_id}/email_templates", response=dict[str, EmailTemplateSchema | None])
@ensure_event_staff
def get_email_templates(request, event_id: int):
    event = Event.objects.get(id=event_id)
    rtn = {
        "registration": event.email_template_registration,
        "abstract": event.email_template_abstract_submission,
        "certificate": event.email_template_certificate
    }
    return rtn

@api.get("/event/{event_id}/onsite/verify", auth=None)
def verify_onsite_code(request, event_id: int, code: str = ""):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api.create_response(request, {"code": "not_found", "message": "Event not found."}, status=404)
    if not event.onsite_code or code.strip().upper() != event.onsite_code:
        return api.create_response(request, {"code": "invalid_code", "message": "Invalid code."}, status=403)
    return {"code": "success", "message": "Valid code."}

@api.post("/event/{event_id}/onsite", auth=None)
@rate_limit(max_requests=20, window_seconds=60)
def register_on_site(request, event_id: int):
    from zoneinfo import ZoneInfo
    event = Event.objects.get(id=event_id)

    tz = ZoneInfo(BusinessSettings.get_instance().timezone)
    today = datetime.now(tz).date()
    if today < event.start_date or today > event.end_date:
        return api.create_response(
            request,
            {"code": "not_available", "message": "On-site registration is only available during the event."},
            status=400,
        )

    data = json.loads(request.body)

    # Validate onsite code
    code = data.get("code", "").strip().upper()
    if not event.onsite_code or code != event.onsite_code:
        return api.create_response(
            request,
            {"code": "invalid_code", "message": "Invalid onsite registration code."},
            status=403,
        )

    email = data.get("email", "").strip()
    if not email:
        return api.create_response(
            request,
            {"code": "email_required", "message": "Email is required."},
            status=400,
        )

    oa = OnSiteAttendee.objects.create(
        event=event,
        name=data.get("name"),
        email=email,
        institute=data.get("institute", ""),
        job_title=data.get("job_title", "")
    )
    return {"code": "success", "message": "Successfully registered on-site.", "id": oa.id, "onsiteattendee_nametag_id": oa.onsiteattendee_nametag_id}

@api.get("/event/{event_id}/onsite", response=List[OnSiteAttendeeSchema])
@ensure_event_staff
def get_on_site_attendees(request, event_id: int):
    event = Event.objects.get(id=event_id)
    return event.onsite_attendees.all()

@api.post("/event/{event_id}/onsite/{onsite_id}/delete", response=MessageSchema)
@ensure_event_staff
def delete_on_site_attendee(request, event_id: int, onsite_id: int):
    event = Event.objects.get(id=event_id)
    oa = OnSiteAttendee.objects.get(id=onsite_id, event=event)
    oa.delete()
    return {"code": "success", "message": "On-site attendee deleted."}

@api.post("/event/{event_id}/onsite/{onsite_id}/update", response=MessageSchema)
@ensure_event_staff
def update_on_site_attendee(request, event_id: int, onsite_id: int):
    event = Event.objects.get(id=event_id)
    oa = OnSiteAttendee.objects.get(id=onsite_id, event=event)
    data = json.loads(request.body)

    if "is_confirmed" in data:
        oa.is_confirmed = data.get("is_confirmed", False)

    if "name" in data or "email" in data or "institute" in data or "job_title" in data:
        email = data.get("email", "").strip()
        if not email:
            return api.create_response(
                request,
                {"code": "email_required", "message": "Email is required."},
                status=400,
            )
        oa.name = data.get("name")
        oa.email = email

        # Auto-create institution if it doesn't exist
        institute_name = data.get("institute", "")
        if institute_name:
            institution, _ = Institution.objects.get_or_create(
                name_en=institute_name,
                defaults={'name_ko': ''}
            )
            oa.institute = institution.name_en
        else:
            oa.institute = institute_name

        oa.job_title = data.get("job_title")

    oa.save()
    return {"code": "success", "message": "On-site attendee updated."}

@api.get("/business-settings", response=BusinessSettingsSchema, auth=None)
def get_business_settings(request):
    """Get business settings for receipts (public endpoint)."""
    settings = BusinessSettings.get_instance()
    return {
        'business_name': settings.business_name,
        'business_registration_number': settings.business_registration_number,
        'address': settings.address,
        'representative': settings.representative,
        'phone': settings.phone,
        'email': settings.email,
        'timezone': settings.timezone,
    }

@api.post("/admin/business-settings", response=BusinessSettingsSchema)
@ensure_staff
def update_business_settings(request, data: BusinessSettingsUpdateSchema):
    """Update business settings (admin only)."""
    settings = BusinessSettings.get_instance()
    settings.business_name = data.business_name
    settings.business_registration_number = data.business_registration_number
    settings.address = data.address
    settings.representative = data.representative
    settings.phone = data.phone
    settings.email = data.email
    settings.timezone = data.timezone
    settings.save()
    return {
        'business_name': settings.business_name,
        'business_registration_number': settings.business_registration_number,
        'address': settings.address,
        'representative': settings.representative,
        'phone': settings.phone,
        'email': settings.email,
        'timezone': settings.timezone,
    }


# ===== Account Settings (Global Admin) =====

@api.get("/admin/account-settings", response=AccountSettingsSchema)
@ensure_staff
def get_account_settings(request):
    """Get account and data retention settings (admin only)."""
    account_settings = AccountSettings.get_instance()
    return {
        'account_deletion_period': account_settings.account_deletion_period,
        'account_warning_period': account_settings.account_warning_period,
        'attendee_retention_years': account_settings.attendee_retention_years,
        'payment_retention_years': account_settings.payment_retention_years,
        'minimum_retention_years': AccountSettings.MINIMUM_RETENTION_YEARS,
    }


@api.post("/admin/account-settings", response=AccountSettingsSchema)
@ensure_staff
def update_account_settings(request, data: AccountSettingsUpdateSchema):
    """Update account and data retention settings (admin only)."""
    account_settings = AccountSettings.get_instance()
    account_settings.account_deletion_period = data.account_deletion_period
    account_settings.account_warning_period = data.account_warning_period
    account_settings.attendee_retention_years = data.attendee_retention_years
    account_settings.payment_retention_years = data.payment_retention_years
    account_settings.save()  # save() enforces minimum retention years
    return {
        'account_deletion_period': account_settings.account_deletion_period,
        'account_warning_period': account_settings.account_warning_period,
        'attendee_retention_years': account_settings.attendee_retention_years,
        'payment_retention_years': account_settings.payment_retention_years,
        'minimum_retention_years': AccountSettings.MINIMUM_RETENTION_YEARS,
    }


# ===== Site Settings (Global Admin) =====

@api.get("/site-settings", response=SiteSettingsSchema, auth=None)
def get_site_settings(request):
    """Get site settings for meta tags (public endpoint)."""
    settings = SiteSettings.get_instance()
    return {
        'site_name': settings.site_name,
        'site_description': settings.site_description,
        'site_keywords': settings.site_keywords,
    }


@api.post("/admin/site-settings", response=SiteSettingsSchema)
@ensure_staff
def update_site_settings(request, data: SiteSettingsUpdateSchema):
    """Update site settings (admin only)."""
    settings = SiteSettings.get_instance()
    settings.site_name = data.site_name
    settings.site_description = data.site_description
    settings.site_keywords = data.site_keywords
    settings.save()
    return {
        'site_name': settings.site_name,
        'site_description': settings.site_description,
        'site_keywords': settings.site_keywords,
    }


# ===== Event Payment Management (Event Admin) =====

@api.get("/event/{event_id}/payments", response=List[EventPaymentSchema])
@ensure_event_staff
def get_event_payments(request, event_id: int):
    """Get all payments for an event (event admin only)."""
    event = Event.objects.get(id=event_id)
    payments = PaymentHistory.objects.filter(event=event).select_related('manual_transaction')

    payment_list = []
    for payment in payments:
        # Get manual transaction details if exists
        manual_payment_type = ''
        supply_amount = 0
        vat = 0
        card_type = ''
        card_number = ''
        approval_number = ''
        installment = ''
        transaction_datetime = ''
        transaction_description = ''

        if hasattr(payment, 'manual_transaction') and payment.manual_transaction:
            mt = payment.manual_transaction
            manual_payment_type = mt.payment_type
            supply_amount = mt.supply_amount
            vat = mt.vat
            card_type = mt.card_type
            card_number = mt.card_number
            approval_number = mt.approval_number
            installment = mt.installment
            if mt.transaction_datetime:
                transaction_datetime = mt.transaction_datetime.strftime('%Y-%m-%d %H:%M:%S')
            transaction_description = mt.transaction_description

        payment_list.append({
            'id': payment.id,
            'number': payment.toss_order_id or str(payment.id),
            'checkout_date': payment.created_at.strftime('%Y-%m-%d'),
            'amount': payment.amount,
            'status': payment.status,
            'payment_type': payment.payment_type,
            'manual_payment_type': manual_payment_type,
            'note': payment.note,
            'attendee_id': payment.attendee_id,
            'attendee_name': payment.attendee_name,
            'attendee_name_ko': payment.attendee_korean_name or '',
            'attendee_email': payment.attendee_email or '',
            'attendee_institute': payment.attendee_institute or '',
            'attendee_institute_ko': payment.attendee_institute_ko or '',
            'supply_amount': supply_amount,
            'vat': vat,
            'card_type': card_type,
            'card_number': card_number,
            'approval_number': approval_number,
            'installment': installment,
            'transaction_datetime': transaction_datetime,
            'transaction_description': transaction_description,
        })

    return payment_list


@api.post("/event/{event_id}/payment/add", response=MessageSchema)
@ensure_event_staff
def create_event_payment(request, event_id: int, data: PaymentCreateSchema):
    """Create a new payment for an attendee (event admin only)."""
    event = Event.objects.get(id=event_id)

    # Validate attendee exists and belongs to this event
    try:
        attendee = Attendee.objects.get(id=data.attendee_id, event=event)
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "attendee_not_found", "message": "Attendee not found."},
            status=404,
        )

    # Check if attendee already has a completed payment
    if PaymentHistory.objects.filter(attendee=attendee, status='completed').exists():
        return api.create_response(
            request,
            {"code": "payment_exists", "message": "This attendee already has a completed payment."},
            status=400,
        )

    # Validate payment type
    if data.payment_type not in ['card', 'transfer', 'cash']:
        return api.create_response(
            request,
            {"code": "invalid_payment_type", "message": "Invalid payment type."},
            status=400,
        )

    # Create payment with "직접입력" as the main payment type
    payment = PaymentHistory(
        attendee=attendee,
        event=event,
        amount=data.amount,
        status='completed',
        payment_type='직접입력',
        note=data.note,
        toss_order_id=data.order_id,
    )
    payment.copy_attendee_info(attendee)
    payment.copy_event_info(event)
    payment.save()

    # Create ManualTransaction with actual payment details
    manual_tx = ManualTransaction(
        payment=payment,
        payment_type=data.payment_type,
        supply_amount=data.supply_amount,
        vat=data.vat,
    )
    if data.payment_type == 'card':
        manual_tx.card_type = data.card_type
        manual_tx.card_number = data.card_number
        manual_tx.approval_number = data.approval_number
        manual_tx.installment = data.installment
    elif data.payment_type == 'transfer':
        if data.transaction_datetime:
            manual_tx.transaction_datetime = datetime.fromisoformat(data.transaction_datetime.replace('Z', '+00:00'))
        manual_tx.transaction_description = data.transaction_description
    manual_tx.save()

    return {"code": "success", "message": "Payment created successfully."}


@api.post("/event/{event_id}/payment/{payment_id}/cancel", response=MessageSchema)
@ensure_event_staff
def cancel_event_payment(request, event_id: int, payment_id: int, data: PaymentCancelSchema):
    """Cancel a payment (event admin only). If paid via Toss, cancels with Toss API."""
    event = Event.objects.get(id=event_id)

    try:
        payment = PaymentHistory.objects.get(id=payment_id, event=event)
    except PaymentHistory.DoesNotExist:
        return api.create_response(
            request,
            {"code": "payment_not_found", "message": "Payment not found."},
            status=404,
        )

    if payment.status == 'cancelled':
        return api.create_response(
            request,
            {"code": "already_cancelled", "message": "Payment is already cancelled."},
            status=400,
        )

    # If payment was made via Toss, call Toss API to cancel
    if payment.toss_payment_key:
        if not settings.TOSS_SECRET_KEY:
            return api.create_response(
                request,
                {"code": "config_error", "message": "Payment service is not configured."},
                status=500,
            )

        auth_string = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()

        try:
            response = requests.post(
                f"{settings.TOSS_API_URL}/payments/{payment.toss_payment_key}/cancel",
                headers={
                    "Authorization": f"Basic {auth_string}",
                    "Content-Type": "application/json",
                },
                json={"cancelReason": data.cancel_reason},
                timeout=30,
            )
        except requests.RequestException as e:
            logger.error(f"Toss API request failed: {e}")
            return api.create_response(
                request,
                {"code": "api_error", "message": "Failed to connect to payment service."},
                status=500,
            )

        if not response.ok:
            error_data = response.json()
            logger.error(f"Toss payment cancellation failed: {error_data}")
            return api.create_response(
                request,
                {
                    "code": error_data.get("code", "cancel_failed"),
                    "message": error_data.get("message", "Payment cancellation failed."),
                },
                status=400,
            )

        # Toss cancellation successful
        toss_response = response.json()
        logger.info(f"Toss payment cancelled: payment_key={payment.toss_payment_key}, status={toss_response.get('status')}")

    payment.status = 'cancelled'
    payment.save()

    return {"code": "success", "message": "Payment cancelled successfully."}


@api.post("/event/{event_id}/payment/{payment_id}/note", response=MessageSchema)
@ensure_event_staff
def update_payment_note(request, event_id: int, payment_id: int, data: PaymentNoteUpdateSchema):
    """Update payment note (event admin only)."""
    event = Event.objects.get(id=event_id)

    try:
        payment = PaymentHistory.objects.get(id=payment_id, event=event)
    except PaymentHistory.DoesNotExist:
        return api.create_response(
            request,
            {"code": "payment_not_found", "message": "Payment not found."},
            status=404,
        )

    payment.note = data.note
    payment.save()

    return {"code": "success", "message": "Payment note updated successfully."}


@api.post("/payment/confirm")
def confirm_toss_payment(request, data: TossPaymentConfirmSchema):
    """
    Confirm a Toss payment after successful authorization.
    Called from the payment success callback page.
    The attendee should already be registered with pending payment status.
    """
    # Validate secret key is configured
    if not settings.TOSS_SECRET_KEY:
        logger.error("TOSS_SECRET_KEY is not configured")
        return api.create_response(
            request,
            {"code": "config_error", "message": "Payment service is not configured."},
            status=500,
        )

    # Get event by ID
    try:
        event = Event.objects.get(id=data.eventId)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "event_not_found", "message": "Event not found."},
            status=404,
        )

    user = request.user

    # User must already be registered (attendee created in step 2)
    try:
        attendee = Attendee.objects.get(event=event, user=user)
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_registered", "message": "You are not registered for this event."},
            status=400,
        )

    # Check if a completed payment already exists for this attendee
    if PaymentHistory.objects.filter(attendee=attendee, status='completed').exists():
        return api.create_response(
            request,
            {"code": "already_paid", "message": "Payment already completed."},
            status=400,
        )

    # Verify amount matches event registration fee
    if data.amount != event.registration_fee:
        logger.warning(f"Amount mismatch: expected {event.registration_fee}, got {data.amount}")
        return api.create_response(
            request,
            {"code": "amount_mismatch", "message": "Payment amount does not match registration fee."},
            status=400,
        )

    # Call Toss Payments confirm API
    # Authorization: Basic base64(secretKey:)
    auth_string = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()

    try:
        response = requests.post(
            f"{settings.TOSS_API_URL}/payments/confirm",
            headers={
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": data.paymentKey,
                "orderId": data.orderId,
                "amount": data.amount,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error(f"Toss API request failed: {e}")
        return api.create_response(
            request,
            {"code": "api_error", "message": "Failed to connect to payment service."},
            status=500,
        )

    if not response.ok:
        error_data = response.json()
        logger.error(f"Toss payment confirmation failed: {error_data}")
        return api.create_response(
            request,
            {
                "code": error_data.get("code", "payment_failed"),
                "message": error_data.get("message", "Payment confirmation failed."),
            },
            status=400,
        )

    # Parse successful response
    toss_payment = response.json()

    # Always create a new payment record (don't update cancelled ones)
    payment = PaymentHistory(
        attendee=attendee,
        event=event,
        amount=data.amount,
        status='completed',
        payment_type=toss_payment.get('method', 'card'),
        toss_order_id=data.orderId,
        toss_payment_key=data.paymentKey,
    )
    payment.copy_attendee_info(attendee)
    payment.copy_event_info(event)
    payment.save()

    logger.info(f"Payment confirmed: user={user.id}, event={event.id}, amount={data.amount}")

    return {
        "code": "success",
        "message": "Payment confirmed successfully.",
        "number": payment.toss_order_id or str(payment.id),
        "amount": payment.amount,
        "event_id": event.id,
        "event_name": event.name,
    }


@api.get("/payment/{order_id}/card-receipt")
def get_card_receipt(request, order_id: str):
    """
    Get Toss receipt URL for a card payment.
    Returns the URL to redirect to Toss's receipt page.
    """
    user = request.user

    # Find payment by order_id
    try:
        payment = PaymentHistory.objects.get(toss_order_id=order_id, attendee__user=user)
    except PaymentHistory.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_found", "message": "Payment not found."},
            status=404,
        )

    # Check if payment type is card
    if payment.payment_type != '카드':
        return api.create_response(
            request,
            {"code": "not_card", "message": "This payment is not a card payment."},
            status=400,
        )

    # Validate secret key is configured
    if not settings.TOSS_SECRET_KEY:
        return api.create_response(
            request,
            {"code": "config_error", "message": "Payment service is not configured."},
            status=500,
        )

    # Call Toss Payments API to get payment details
    auth_string = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()

    try:
        response = requests.get(
            f"{settings.TOSS_API_URL}/payments/orders/{order_id}",
            headers={
                "Authorization": f"Basic {auth_string}",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error(f"Toss API request failed: {e}")
        return api.create_response(
            request,
            {"code": "api_error", "message": "Failed to connect to payment service."},
            status=500,
        )

    if not response.ok:
        error_data = response.json()
        logger.error(f"Toss API error: {error_data}")
        return api.create_response(
            request,
            {
                "code": error_data.get("code", "api_error"),
                "message": error_data.get("message", "Failed to get payment details."),
            },
            status=400,
        )

    toss_data = response.json()
    receipt_url = toss_data.get("receipt", {}).get("url", "")

    if not receipt_url:
        return api.create_response(
            request,
            {"code": "no_receipt", "message": "Receipt URL not available."},
            status=404,
        )

    return {"code": "success", "receipt_url": receipt_url}


def get_paypal_access_token():
    """Get PayPal OAuth2 access token."""
    auth = base64.b64encode(f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_SECRET_KEY}".encode()).decode()
    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if response.ok:
        return response.json().get("access_token")
    logger.error(f"Failed to get PayPal access token: {response.text}")
    return None


@api.post("/payment/paypal/create-order")
def create_paypal_order(request, data: PayPalCreateOrderSchema):
    """
    Create a PayPal order for event registration payment.
    Returns the PayPal order ID for client-side approval.
    """
    logger.info(f"PayPal create order request: eventId={data.eventId}, amount={data.amount}, user={request.user}")

    # Check if user is authenticated
    if not request.user.is_authenticated:
        return api.create_response(
            request,
            {"code": "auth_required", "message": "Authentication required."},
            status=401,
        )

    # Validate PayPal is configured
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET_KEY:
        logger.error("PayPal credentials are not configured")
        return api.create_response(
            request,
            {"code": "config_error", "message": "PayPal is not configured."},
            status=500,
        )

    # Get event by ID
    try:
        event = Event.objects.get(id=data.eventId)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "event_not_found", "message": "Event not found."},
            status=404,
        )

    user = request.user

    # User must already be registered
    try:
        attendee = Attendee.objects.get(event=event, user=user)
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_registered", "message": "You are not registered for this event."},
            status=400,
        )

    # Check if payment already completed
    if PaymentHistory.objects.filter(attendee=attendee, status='completed').exists():
        return api.create_response(
            request,
            {"code": "already_paid", "message": "Payment already completed."},
            status=400,
        )

    # Verify amount matches event registration fee
    if data.amount != event.registration_fee:
        return api.create_response(
            request,
            {"code": "amount_mismatch", "message": "Payment amount does not match registration fee."},
            status=400,
        )

    # Get PayPal access token
    access_token = get_paypal_access_token()
    if not access_token:
        return api.create_response(
            request,
            {"code": "auth_error", "message": "Failed to authenticate with PayPal."},
            status=500,
        )

    # Convert KRW to USD (PayPal doesn't support KRW)
    # Use cached exchange rate from DB (updated once per day)
    krw_to_usd_rate = None
    one_day_ago = timezone.now() - timedelta(days=1)

    # Check for cached rate
    try:
        cached_rate = ExchangeRate.objects.filter(
            currency_from='KRW',
            currency_to='USD',
            updated_at__gte=one_day_ago
        ).first()
        if cached_rate:
            krw_to_usd_rate = float(cached_rate.rate)
            logger.info(f"Using cached exchange rate: 1 KRW = {krw_to_usd_rate} USD (updated: {cached_rate.updated_at})")
    except Exception as e:
        logger.warning(f"Failed to read cached exchange rate: {e}")

    # Fetch fresh rate if no valid cache
    if krw_to_usd_rate is None:
        if not settings.OPENEXCHANGERATES_APP_ID:
            logger.error("OPENEXCHANGERATES_APP_ID is not configured")
            return api.create_response(
                request,
                {"code": "config_error", "message": "Exchange rate service is not configured."},
                status=500,
            )

        try:
            rate_response = requests.get(
                f"https://openexchangerates.org/api/latest.json?app_id={settings.OPENEXCHANGERATES_APP_ID}",
                timeout=10,
            )
            if not rate_response.ok:
                logger.error(f"Exchange rate API returned status {rate_response.status_code}")
                return api.create_response(
                    request,
                    {"code": "exchange_rate_error", "message": "Failed to fetch exchange rate."},
                    status=500,
                )
            rate_data = rate_response.json()
            krw_rate = rate_data.get("rates", {}).get("KRW")
            if not krw_rate:
                logger.error("KRW rate not found in exchange rate response")
                return api.create_response(
                    request,
                    {"code": "exchange_rate_error", "message": "KRW exchange rate not available."},
                    status=500,
                )
            krw_to_usd_rate = 1 / krw_rate
            logger.info(f"Fetched live exchange rate: 1 USD = {krw_rate} KRW")

            # Save to DB (delete existing first)
            ExchangeRate.objects.filter(currency_from='KRW', currency_to='USD').delete()
            ExchangeRate.objects.create(
                currency_from='KRW',
                currency_to='USD',
                rate=krw_to_usd_rate
            )
        except Exception as e:
            logger.error(f"Failed to fetch exchange rate: {e}")
            return api.create_response(
                request,
                {"code": "exchange_rate_error", "message": "Failed to fetch exchange rate."},
                status=500,
            )

    amount_usd = round(data.amount * krw_to_usd_rate, 2)
    amount_str = f"{amount_usd:.2f}"

    logger.info(f"Converting {data.amount} KRW to {amount_str} USD (rate: {krw_to_usd_rate})")

    # Create PayPal order
    try:
        response = requests.post(
            f"{settings.PAYPAL_API_URL}/v2/checkout/orders",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": amount_str,
                    },
                    "description": f"Registration for {event.name}",
                }],
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error(f"PayPal API request failed: {e}")
        return api.create_response(
            request,
            {"code": "api_error", "message": "Failed to connect to PayPal."},
            status=500,
        )

    if not response.ok:
        error_data = response.json()
        logger.error(f"PayPal order creation failed: {error_data}")
        return api.create_response(
            request,
            {"code": "paypal_error", "message": "Failed to create PayPal order."},
            status=400,
        )

    paypal_order = response.json()
    order_id = paypal_order.get("id")

    logger.info(f"PayPal order created: {order_id} for user={user.id}, event={event.id}")

    return {
        "code": "success",
        "orderId": order_id,
    }


@api.post("/payment/paypal/capture-order")
def capture_paypal_order(request, data: PayPalCaptureOrderSchema):
    """
    Capture a PayPal order after user approval.
    Creates a PaymentHistory record on success.
    """
    logger.info(f"PayPal capture order request: orderId={data.orderId}, eventId={data.eventId}, user={request.user}")

    # Check if user is authenticated
    if not request.user.is_authenticated:
        return api.create_response(
            request,
            {"code": "auth_required", "message": "Authentication required."},
            status=401,
        )

    # Validate PayPal is configured
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET_KEY:
        return api.create_response(
            request,
            {"code": "config_error", "message": "PayPal is not configured."},
            status=500,
        )

    # Get event by ID
    try:
        event = Event.objects.get(id=data.eventId)
    except Event.DoesNotExist:
        return api.create_response(
            request,
            {"code": "event_not_found", "message": "Event not found."},
            status=404,
        )

    user = request.user

    # User must already be registered
    try:
        attendee = Attendee.objects.get(event=event, user=user)
    except Attendee.DoesNotExist:
        return api.create_response(
            request,
            {"code": "not_registered", "message": "You are not registered for this event."},
            status=400,
        )

    # Check if payment already completed
    if PaymentHistory.objects.filter(attendee=attendee, status='completed').exists():
        return api.create_response(
            request,
            {"code": "already_paid", "message": "Payment already completed."},
            status=400,
        )

    # Get PayPal access token
    access_token = get_paypal_access_token()
    if not access_token:
        return api.create_response(
            request,
            {"code": "auth_error", "message": "Failed to authenticate with PayPal."},
            status=500,
        )

    # Capture PayPal order
    try:
        response = requests.post(
            f"{settings.PAYPAL_API_URL}/v2/checkout/orders/{data.orderId}/capture",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error(f"PayPal capture request failed: {e}")
        return api.create_response(
            request,
            {"code": "api_error", "message": "Failed to connect to PayPal."},
            status=500,
        )

    if not response.ok:
        error_data = response.json()
        logger.error(f"PayPal capture failed: {error_data}")
        return api.create_response(
            request,
            {"code": "paypal_error", "message": "Failed to capture PayPal payment."},
            status=400,
        )

    paypal_capture = response.json()

    # Verify capture was successful
    if paypal_capture.get("status") != "COMPLETED":
        return api.create_response(
            request,
            {"code": "capture_incomplete", "message": "Payment was not completed."},
            status=400,
        )

    # Extract payment amount from the capture response
    capture_data = paypal_capture.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])[0]
    amount = int(float(capture_data.get("amount", {}).get("value", 0)))

    # Create PaymentHistory record
    payment = PaymentHistory(
        attendee=attendee,
        event=event,
        amount=amount,
        status='completed',
        payment_type='PayPal',
        toss_order_id=data.orderId,  # Store PayPal order ID in toss_order_id field
        toss_payment_key=capture_data.get("id", ""),  # Store PayPal capture ID
    )
    payment.copy_attendee_info(attendee)
    payment.copy_event_info(event)
    payment.save()

    logger.info(f"PayPal payment captured: user={user.id}, event={event.id}, amount={amount}")

    return {
        "code": "success",
        "message": "Payment confirmed successfully.",
        "number": payment.toss_order_id or str(payment.id),
        "amount": payment.amount,
        "event_id": event.id,
        "event_name": event.name,
    }


# ===== Privacy Policy =====

@api.get("/privacy-policy", response=PrivacyPolicySchema, auth=None)
def get_privacy_policy(request):
    """Get rendered privacy policy content (public endpoint)."""
    policy = PrivacyPolicy.get_instance()
    return {
        'content_en': policy.render_content('en'),
        'content_ko': policy.render_content('ko'),
        'updated_at': policy.updated_at.isoformat() if policy.updated_at else '',
    }


@api.get("/admin/privacy-policy", response=PrivacyPolicyAdminSchema)
@ensure_staff
def get_privacy_policy_admin(request):
    """Get raw privacy policy content for editing (admin only)."""
    policy = PrivacyPolicy.get_instance()
    return {
        'content_en': policy.content_en,
        'content_ko': policy.content_ko,
        'updated_at': policy.updated_at.isoformat() if policy.updated_at else '',
    }


@api.post("/admin/privacy-policy", response=PrivacyPolicyAdminSchema)
@ensure_staff
def update_privacy_policy(request, data: PrivacyPolicyUpdateSchema):
    """Update privacy policy content (admin only)."""
    policy = PrivacyPolicy.get_instance()
    policy.content_en = data.content_en
    policy.content_ko = data.content_ko
    policy.save()
    return {
        'content_en': policy.content_en,
        'content_ko': policy.content_ko,
        'updated_at': policy.updated_at.isoformat() if policy.updated_at else '',
    }


# ===== Terms of Service =====

@api.get("/terms-of-service", response=TermsOfServiceSchema, auth=None)
def get_terms_of_service(request):
    """Get rendered terms of service content (public endpoint)."""
    terms = TermsOfService.get_instance()
    return {
        'content_en': terms.render_content('en'),
        'content_ko': terms.render_content('ko'),
        'updated_at': terms.updated_at.isoformat() if terms.updated_at else '',
    }


@api.get("/admin/terms-of-service", response=TermsOfServiceAdminSchema)
@ensure_staff
def get_terms_of_service_admin(request):
    """Get raw terms of service content for editing (admin only)."""
    terms = TermsOfService.get_instance()
    return {
        'content_en': terms.content_en,
        'content_ko': terms.content_ko,
        'updated_at': terms.updated_at.isoformat() if terms.updated_at else '',
    }


@api.post("/admin/terms-of-service", response=TermsOfServiceAdminSchema)
@ensure_staff
def update_terms_of_service(request, data: TermsOfServiceUpdateSchema):
    """Update terms of service content (admin only)."""
    terms = TermsOfService.get_instance()
    terms.content_en = data.content_en
    terms.content_ko = data.content_ko
    terms.save()
    return {
        'content_en': terms.content_en,
        'content_ko': terms.content_ko,
        'updated_at': terms.updated_at.isoformat() if terms.updated_at else '',
    }


# ===== Editor File Upload =====

@api.post("/upload/editor-file")
@ensure_staff
def upload_editor_file(request):
    """
    Upload a file for the rich text editor (staff only).
    Accepts images and attachments via base64 encoding.
    Returns the URL of the uploaded file.
    """
    data = json.loads(request.body)
    file_name = data.get("file_name", "")
    file_content_b64 = data.get("file_content", "")
    file_type = data.get("file_type", "image")  # 'image' or 'attachment'

    if not file_name or not file_content_b64:
        return api.create_response(
            request,
            {"code": "missing_fields", "message": "File name and content are required."},
            status=400,
        )

    # Decode base64 content
    try:
        # Handle data URL format (e.g., "data:image/png;base64,...")
        if "," in file_content_b64:
            file_content = base64.b64decode(file_content_b64.split(",")[1])
        else:
            file_content = base64.b64decode(file_content_b64)
    except (ValueError, IndexError):
        return api.create_response(
            request,
            {"code": "invalid_file", "message": "Invalid file content encoding."},
            status=400,
        )

    # Validate file
    is_valid, error_message = validate_editor_file(file_name, file_content, file_type)
    if not is_valid:
        return api.create_response(
            request,
            {"code": "invalid_file", "message": error_message},
            status=400,
        )

    # Sanitize filename and create unique path
    safe_filename = sanitize_filename(file_name)
    folder = "editor/images" if file_type == "image" else "editor/attachments"
    file_path = f"{folder}/{uuid.uuid4()}/{safe_filename}"

    # Save file
    file = ContentFile(file_content)
    saved_path = default_storage.save(file_path, file)

    # Return the URL
    file_url = f"/media/{saved_path}"

    return {
        "code": "success",
        "url": file_url,
        "filename": safe_filename,
    }
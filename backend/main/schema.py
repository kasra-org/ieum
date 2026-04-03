
from ninja import Schema

from typing import List, Union, Optional
from datetime import date

from main.models import User, Attendee, Abstract, OnSiteAttendee, Institution
from main.utils import docx_to_html, odt_to_html

class LoginSchema(Schema):
    email: str
    password: str

class ResendVerificationSchema(Schema):
    email: str
    verification_key: str

class GenerateVerificationKeySchema(Schema):
    email: str

class VerificationKeyResponseSchema(Schema):
    key: str

class MessageSchema(Schema):
    code: str
    message: str = ""

class InstitutionSchema(Schema):
    id: int
    name_en: str
    name_ko: str

class InstitutionCreateSchema(Schema):
    name_en: str
    name_ko: str = ""

class UserSchema(Schema):
    id: int
    username: str
    email: str
    first_name: str
    middle_initial: str
    korean_name: str
    last_name: str
    name: str
    orcid: str
    google: str
    nationality: int
    job_title: str
    department: str
    institute: Optional[int]
    institute_en: str
    institute_ko: str
    disability: str
    dietary: str
    is_staff: bool
    is_active: bool
    date_joined: str
    email_verified: bool

    @staticmethod
    def resolve_institute(user: User) -> Optional[int]:
        if user.institute:
            return user.institute.id
        return None

    @staticmethod
    def resolve_institute_en(user: User) -> str:
        if user.institute:
            return user.institute.name_en
        return ""

    @staticmethod
    def resolve_institute_ko(user: User) -> str:
        if user.institute:
            return user.institute.name_ko
        return ""

    @staticmethod
    def resolve_orcid(user: User) -> str:
        linked_accounts = user.socialaccount_set.filter(provider='orcid')
        if linked_accounts.count() > 0:
            return linked_accounts[0].uid
        return ""

    @staticmethod
    def resolve_google(user: User) -> str:
        linked_accounts = user.socialaccount_set.filter(provider='google')
        if linked_accounts.count() > 0:
            # Return the Gmail address from extra_data if available
            extra_data = linked_accounts[0].extra_data
            if extra_data and 'email' in extra_data:
                return extra_data['email']
            return linked_accounts[0].uid
        return ""

    @staticmethod
    def resolve_name(user: User) -> str:
        name = user.first_name
        if user.middle_initial:
            name += " " + user.middle_initial
        name += " " + user.last_name
        return name

    @staticmethod
    def resolve_date_joined(user: User) -> str:
        return user.date_joined.isoformat()

    @staticmethod
    def resolve_email_verified(user: User) -> bool:
        from allauth.account.models import EmailAddress
        email_address = EmailAddress.objects.filter(user=user, primary=True).first()
        if email_address:
            return email_address.verified
        return False


class PublicUserSchema(Schema):
    """
    A restricted user schema for public-facing endpoints.
    Excludes sensitive fields like is_staff, disability, dietary, etc.
    """
    id: int
    first_name: str
    middle_initial: str
    korean_name: str
    last_name: str
    name: str
    job_title: str
    institute_en: str
    institute_ko: str

    @staticmethod
    def resolve_institute_en(user: User) -> str:
        if user.institute:
            return user.institute.name_en
        return ""

    @staticmethod
    def resolve_institute_ko(user: User) -> str:
        if user.institute:
            return user.institute.name_ko
        return ""

    @staticmethod
    def resolve_name(user: User) -> str:
        name = user.first_name
        if user.middle_initial:
            name += " " + user.middle_initial
        name += " " + user.last_name
        return name


class OrganizerSchema(Schema):
    id: int
    name: str
    korean_name: str
    email: str
    affiliation: str
    affiliation_ko: str
    order: int


class EventSchema(Schema):
    id: int
    name: str
    description: str
    category: str
    link_info: str
    start_date: date
    end_date: date
    venue: str
    venue_ko: str
    venue_address: str
    venue_address_ko: str
    venue_latitude: Union[float, None]
    venue_longitude: Union[float, None]
    organizers: List[OrganizerSchema]
    organizers_en: str
    organizers_ko: str
    main_languages: List[str]
    registration_deadline: Union[date, None]
    registration_fee: Union[int, None]
    accepts_abstract: bool
    abstract_submission_type: str
    external_abstract_url: str
    abstract_deadline: Union[date, None]
    published: bool
    is_invitation_only: bool

    @staticmethod
    def resolve_is_invitation_only(obj):
        return bool(obj.invitation_code)

    @staticmethod
    def resolve_organizers(obj):
        return obj.organizer_set.all()

class PaginatedEventsSchema(Schema):
    events: List[EventSchema]
    total: int
    offset: int
    limit: int
    
class VenueSchema(Schema):
    short_name: str
    long_name: str

class EmailTemplateSchema(Schema):
    subject: str
    body: str

class EventAdminSchema(Schema):
    id: int
    name: str
    description: str
    category: str
    link_info: str
    start_date: date
    end_date: date
    venue: str
    venue_ko: str
    venue_address: str
    venue_address_ko: str
    venue_latitude: Union[float, None]
    venue_longitude: Union[float, None]
    organizers: List[OrganizerSchema]
    organizers_en: str
    organizers_ko: str
    main_languages: List[str]
    registration_deadline: Union[date, None]
    capacity: int
    registration_fee: Union[int, None]
    accepts_abstract: bool
    abstract_submission_type: str
    external_abstract_url: str
    abstract_deadline: Union[date, None]
    capacity_abstract: Union[int, None]
    max_votes: Union[int, None]
    email_template_registration: Union[EmailTemplateSchema, None]
    email_template_abstract_submission: Union[EmailTemplateSchema, None]
    email_template_certificate: Union[EmailTemplateSchema, None]
    invitation_code: str
    onsite_code: str
    published: bool
    is_archived: bool
    main_admin_id: Union[int, None]
    nametag_paper_width: float
    nametag_paper_height: float
    nametag_orientation: str

    @staticmethod
    def resolve_organizers(obj):
        return obj.organizer_set.all()

class RegistrationStatusSchema(Schema):
    registered: bool
    payment_status: Union[str, None] = None  # 'pending', 'completed', or None (free event/not registered)

class QuestionSchema(Schema):
    id: int
    question: dict

class AnswerSchema(Schema):
    id: int
    reference: Optional[QuestionSchema] = None
    question: str
    answer: Union[str, int]

class StatsSchema(Schema):
    registered: int
    abstracts: int

class AttendeeSchema(Schema):
    id: int
    attendee_nametag_id: int
    user: Optional[UserSchema] = None
    first_name: str
    middle_initial: str
    last_name: str
    korean_name: str
    name: str
    nationality: int
    institute: str
    institute_ko: str
    department: str
    job_title: str
    disability: str
    dietary: str
    user_email: str
    is_attended: bool
    custom_answers: List[AnswerSchema]

    @staticmethod
    def resolve_name(da: Attendee) -> str:
        name = da.first_name
        if da.middle_initial:
            name += " " + da.middle_initial
        name += " " + da.last_name
        return name

class SpeakerSchema(Schema):
    id: int
    name: str
    korean_name: str
    email: str
    affiliation: str
    affiliation_ko: str
    is_domestic: bool
    type: str

class AbstractShortSchema(Schema):
    id: int
    attendee: AttendeeSchema
    title: str
    type: str
    wants_short_talk: bool
    votes: int
    link: str
    @staticmethod
    def resolve_votes(abstract: Abstract) -> int:
        return abstract.votes.count()
    @staticmethod
    def resolve_link(abstract: Abstract) -> str:
        from django.conf import settings
        import os
        full_path = os.path.join(settings.HEADLESS_URL_ROOT, settings.MEDIA_URL, abstract.file_path)
        return full_path
    
class AbstractSchema(Schema):
    id: int
    attendee: AttendeeSchema
    title: str
    body: str
    type: str
    wants_short_talk: bool
    votes: int
    link: str
    @staticmethod
    def resolve_votes(abstract: Abstract) -> int:
        return abstract.votes.count()
    @staticmethod
    def resolve_body(abstract: Abstract) -> str:
        from django.conf import settings
        import os
        full_path = os.path.join(settings.MEDIA_ROOT, abstract.file_path)
        try:
            if full_path.endswith(".docx"):
                return docx_to_html(full_path)
            elif full_path.endswith(".odt"):
                return odt_to_html(full_path)
        except:
            return "An error occured while trying to convert the file to HTML. Please contact the administrator."
    @staticmethod
    def resolve_link(abstract: Abstract) -> str:
        from django.conf import settings
        import os
        full_path = os.path.join(settings.HEADLESS_URL_ROOT, settings.MEDIA_URL, abstract.file_path)
        return full_path
    
class AbstractUserSchema(Schema):
    """Schema for user's own abstract - excludes votes"""
    id: int
    attendee: AttendeeSchema
    title: str
    body: str
    type: str
    wants_short_talk: bool
    link: str
    @staticmethod
    def resolve_body(abstract: Abstract) -> str:
        from django.conf import settings
        import os
        full_path = os.path.join(settings.MEDIA_ROOT, abstract.file_path)
        try:
            if full_path.endswith(".docx"):
                return docx_to_html(full_path)
            elif full_path.endswith(".odt"):
                return odt_to_html(full_path)
        except:
            return "An error occured while trying to convert the file to HTML. Please contact the administrator."
    @staticmethod
    def resolve_link(abstract: Abstract) -> str:
        from django.conf import settings
        import os
        full_path = os.path.join(settings.HEADLESS_URL_ROOT, settings.MEDIA_URL, abstract.file_path)
        return full_path

class AbstractVoteSchema(Schema):
    id: int
    reviewer: AttendeeSchema
    voted_abstracts: List[AbstractShortSchema]

class OnSiteAttendeeSchema(Schema):
    id: int
    onsiteattendee_nametag_id: int
    name: str
    email: str
    institute: str
    job_title: str
    is_confirmed: bool

class PaymentHistorySchema(Schema):
    number: str
    checkout_date: str
    amount: int
    event_id: int
    event_name: str
    start_date: str
    end_date: str
    venue: str
    venue_ko: str
    organizers_en: str
    organizers_ko: str
    status: str
    payment_type: str
    attendee_name: str
    attendee_name_ko: str
    attendee_institute: str
    attendee_institute_ko: str


class BusinessSettingsSchema(Schema):
    business_name: str
    business_registration_number: str
    address: str
    representative: str
    phone: str
    email: str
    timezone: str


class BusinessSettingsUpdateSchema(Schema):
    business_name: str = ""
    business_registration_number: str = ""
    address: str = ""
    representative: str = ""
    phone: str = ""
    email: str = ""
    timezone: str = "Asia/Seoul"


class AccountSettingsSchema(Schema):
    account_deletion_period: int
    account_warning_period: int
    attendee_retention_years: int
    payment_retention_years: int
    minimum_retention_years: int


class AccountSettingsUpdateSchema(Schema):
    account_deletion_period: int = 3 * 365
    account_warning_period: int = 7
    attendee_retention_years: int = 5
    payment_retention_years: int = 5


class SiteSettingsSchema(Schema):
    site_name: str
    site_description: str
    site_keywords: str


class SiteSettingsUpdateSchema(Schema):
    site_name: str = "IEUM"
    site_description: str = "An open-source conference management system for organizing scientific conferences. Manage event registrations, abstract submissions, and attendee workflows seamlessly."
    site_keywords: str = "conference management, event registration, abstract submission, scientific conference, academic event"


class RegistrationHistorySchema(Schema):
    id: int
    registration_date: str
    event_id: int
    event_name: str
    start_date: str
    end_date: str
    venue: str
    venue_ko: str
    organizers_en: str
    organizers_ko: str
    attendee_name: str
    attendee_institute: str
    registration_fee: int
    payment_status: str  # 'free', 'completed', 'pending', 'cancelled'
    is_attended: bool


class EventPaymentSchema(Schema):
    """Schema for event admin to view payments"""
    id: int
    number: str
    checkout_date: str
    amount: int
    status: str
    payment_type: str
    manual_payment_type: str = ""  # For 직접입력: card, transfer, cash
    note: str
    attendee_id: Optional[int] = None
    attendee_name: str
    attendee_name_ko: str
    attendee_email: str
    attendee_institute: str
    attendee_institute_ko: str
    # Manual transaction details (common)
    supply_amount: int = 0
    vat: int = 0
    # Manual transaction details (card)
    card_type: str = ""
    card_number: str = ""
    approval_number: str = ""
    installment: str = ""
    # Manual transaction details (transfer)
    transaction_datetime: str = ""
    transaction_description: str = ""


class PaymentCreateSchema(Schema):
    """Schema for creating a new manual payment (직접입력)"""
    attendee_id: int
    amount: int
    order_id: str  # Generated by frontend
    payment_type: str  # card, transfer, cash
    note: str = ""
    # Common fields
    supply_amount: int = 0
    vat: int = 0
    # Card-specific fields (optional)
    card_type: str = ""
    card_number: str = ""
    approval_number: str = ""
    installment: str = "single"
    # Transfer-specific fields (optional)
    transaction_datetime: str = ""  # ISO datetime string
    transaction_description: str = ""


class PaymentNoteUpdateSchema(Schema):
    """Schema for updating payment note"""
    note: str


class PaymentCancelSchema(Schema):
    """Schema for cancelling a payment"""
    cancel_reason: str = "관리자 취소"


class TossPaymentConfirmSchema(Schema):
    """Schema for confirming Toss payment"""
    paymentKey: str
    orderId: str
    amount: int
    eventId: int  # Event ID for which payment is being made


class PayPalCreateOrderSchema(Schema):
    """Schema for creating PayPal order"""
    eventId: int
    amount: int  # Amount in KRW


class PayPalCaptureOrderSchema(Schema):
    """Schema for capturing PayPal order"""
    orderId: str  # PayPal order ID
    eventId: int


class PrivacyPolicySchema(Schema):
    """Schema for privacy policy (rendered content)"""
    content_en: str
    content_ko: str
    updated_at: str


class PrivacyPolicyAdminSchema(Schema):
    """Schema for privacy policy admin (raw content for editing)"""
    content_en: str
    content_ko: str
    updated_at: str


class PrivacyPolicyUpdateSchema(Schema):
    """Schema for updating privacy policy"""
    content_en: str
    content_ko: str


class TermsOfServiceSchema(Schema):
    """Schema for terms of service (rendered content)"""
    content_en: str
    content_ko: str
    updated_at: str


class TermsOfServiceAdminSchema(Schema):
    """Schema for terms of service admin (raw content for editing)"""
    content_en: str
    content_ko: str
    updated_at: str


class TermsOfServiceUpdateSchema(Schema):
    """Schema for updating terms of service"""
    content_en: str
    content_ko: str
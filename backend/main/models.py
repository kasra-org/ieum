from django.contrib.auth.models import AbstractUser
from django.db import models

def default_main_languages():
    return ['en']

class Institution(models.Model):
    """
    Institution model - stores institution names in both English and Korean
    """
    name_en = models.CharField(max_length=1000, unique=True)
    name_ko = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name_en']

    def __str__(self):
        return f"{self.name_en} ({self.name_ko})" if self.name_ko else self.name_en

class User(AbstractUser):
    """
    User model
    
    Extends Django's AbstractUser model, which provides the following fields:
    - username
    - first_name
    - last_name
    - email
    - is_staff
    - is_active
    - date_joined
    """

    # Add additional fields here
    NATIONALITY_CHOICES = [
        (1, 'Korean'),
        (2, 'Non-Korean'),
        (3, 'Prefer not to respond'),
    ]
    middle_initial = models.CharField(max_length=1, blank=True)
    korean_name = models.CharField(max_length=1000, blank=True)
    nationality = models.IntegerField(choices=NATIONALITY_CHOICES, default=1)
    job_title = models.CharField(max_length=1000, blank=True)
    institute = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    department = models.CharField(max_length=1000, blank=True)
    disability = models.TextField(blank=True)
    dietary = models.TextField(blank=True)
    deletion_warning_sent = models.BooleanField(default=False)  # True if 1-week warning email was sent

    @property
    def name(self):
        return f'{self.first_name}{" " + self.middle_initial if self.middle_initial else ""} {self.last_name}'

    def __str__(self):
        return self.username
class Attendee(models.Model):
    """
    Attendee model
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    attendee_nametag_id = models.PositiveIntegerField(default=0)
    first_name = models.CharField(max_length=1000)
    middle_initial = models.CharField(max_length=1, blank=True)
    last_name = models.CharField(max_length=1000)
    korean_name = models.CharField(max_length=1000, blank=True)
    nationality = models.IntegerField()
    institute = models.CharField(max_length=1000)  # English name
    institute_ko = models.CharField(max_length=1000, blank=True)  # Korean name
    department = models.CharField(max_length=1000, blank=True)
    job_title = models.CharField(max_length=1000, blank=True)
    disability = models.TextField(blank=True)
    dietary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # When the registration was created
    user_deleted_at = models.DateTimeField(null=True, blank=True)  # When the associated user was deleted
    user_email = models.EmailField(blank=True)  # Preserved email after user deletion
    is_attended = models.BooleanField(default=False)

    class Meta:
        unique_together = [['event', 'attendee_nametag_id']]

    def save(self, *args, **kwargs):
        if not self.attendee_nametag_id:
            max_id = Attendee.objects.filter(event=self.event).aggregate(
                models.Max('attendee_nametag_id')
            )['attendee_nametag_id__max'] or 0
            self.attendee_nametag_id = max_id + 1
        super().save(*args, **kwargs)

    @property
    def name(self):
        return f'{self.first_name}{" " + self.middle_initial if self.middle_initial else ""} {self.last_name}'

class OnSiteAttendee(models.Model):
    """
    OnSiteAttendee model
    """
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='onsite_attendees')
    onsiteattendee_nametag_id = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=1000)
    email = models.EmailField(blank=True)
    institute = models.CharField(max_length=1000)
    job_title = models.CharField(max_length=1000, blank=True)
    is_confirmed = models.BooleanField(default=False)

    class Meta:
        unique_together = [['event', 'onsiteattendee_nametag_id']]

    def save(self, *args, **kwargs):
        if not self.onsiteattendee_nametag_id:
            max_id = OnSiteAttendee.objects.filter(event=self.event).aggregate(
                models.Max('onsiteattendee_nametag_id')
            )['onsiteattendee_nametag_id__max'] or 0
            self.onsiteattendee_nametag_id = max_id + 1
        super().save(*args, **kwargs)

    @property
    def korean_name(self):
        return self.name

    @property
    def first_name(self):
        return self.name

    @property
    def last_name(self):
        return ''

    def __str__(self):
        return self.name

class Setting(models.Model):
    """
    Setting model
    """
    key = models.CharField(max_length=100)
    value = models.TextField() # JSON

    def __str__(self):
        return self.key

class Event(models.Model):
    """
    Event model
    """
    CATEGORY_CHOICES = [
        ('workshop', 'Workshop'),
        ('hackathon', 'Hackathon'),
        ('symposium', 'Symposium'),
        ('meeting', 'Meeting'),
        ('conference', 'Conference'),
    ]

    link_info = models.URLField(blank=True)
    name = models.CharField(max_length=1000)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='conference')
    start_date = models.DateField()
    end_date = models.DateField()
    venue = models.CharField(max_length=1000)  # Venue display name (English)
    venue_ko = models.CharField(max_length=1000, blank=True)  # Venue display name (Korean)
    venue_address = models.CharField(max_length=1000, blank=True)  # Full address (English)
    venue_address_ko = models.CharField(max_length=1000, blank=True)  # Full address (Korean)
    venue_latitude = models.FloatField(blank=True, null=True)  # Latitude for map
    venue_longitude = models.FloatField(blank=True, null=True)  # Longitude for map
    # Organizers are stored in the Organizer model (organizer_set)
    main_languages = models.JSONField(default=default_main_languages)  # Array of language codes: ['ko', 'en']
    registration_deadline = models.DateField(blank=True, null=True)
    capacity = models.IntegerField()
    registration_fee = models.IntegerField(blank=True, null=True)
    accepts_abstract = models.BooleanField(default=False)
    abstract_submission_type = models.CharField(max_length=10, choices=[('internal', 'Internal'), ('external', 'External')], default='internal')
    external_abstract_url = models.URLField(max_length=500, blank=True)
    abstract_deadline = models.DateField(blank=True, null=True)
    capacity_abstract = models.IntegerField(null=True)
    max_votes = models.IntegerField(null=True)
    email_template_registration = models.ForeignKey('EmailTemplate', on_delete=models.SET_NULL, blank=True, null=True, related_name='email_template_registration')
    email_template_abstract_submission = models.ForeignKey('EmailTemplate', on_delete=models.SET_NULL, blank=True, null=True, related_name='email_template_abstract_submission')
    email_template_certificate = models.ForeignKey('EmailTemplate', on_delete=models.SET_NULL, blank=True, null=True, related_name='email_template_certificate')
    invitation_code = models.CharField(max_length=100, blank=True)  # Empty = public event, non-empty = invitation only
    onsite_code = models.CharField(max_length=6, blank=True)  # Auto-generated code for onsite registration URL
    attendees = models.ManyToManyField('Attendee', related_name='events', blank=True)
    reviewers = models.ManyToManyField('Attendee', related_name='reviewed_events', blank=True)
    admins = models.ManyToManyField('User', related_name='admins', blank=True)
    main_admin = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='main_admin_events')
    published = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    # Nametag settings
    nametag_paper_width = models.FloatField(default=90)  # Width in mm
    nametag_paper_height = models.FloatField(default=100)  # Height in mm
    nametag_orientation = models.CharField(max_length=20, default='portrait')  # 'portrait' or 'landscape'

    def __str__(self):
        return self.name

    @property
    def organizers_en(self):
        """Return formatted organizers in English: Name (Affiliation)"""
        organizer_list = []
        for org in self.organizer_set.all():
            name = org.name
            if org.affiliation:
                organizer_list.append(f"{name} ({org.affiliation})")
            else:
                organizer_list.append(name)
        return ", ".join(organizer_list)

    @property
    def organizers_ko(self):
        """Return formatted organizers in Korean: 한글이름 (기관명)"""
        organizer_list = []
        for org in self.organizer_set.all():
            name = org.korean_name if org.korean_name else org.name
            affiliation = org.affiliation_ko if org.affiliation_ko else org.affiliation
            if affiliation:
                organizer_list.append(f"{name} ({affiliation})")
            else:
                organizer_list.append(name)
        return ", ".join(organizer_list)

    def delete(self, *args, **kwargs):
        if self.email_template_registration:
            self.email_template_registration.delete()
        if self.email_template_abstract_submission:
            self.email_template_abstract_submission.delete()
        if self.email_template_certificate:
            self.email_template_certificate.delete()
        super().delete(*args, **kwargs)

class Organizer(models.Model):
    """
    Organizer model - stores copied organizer info (not FK to User)
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='organizer_set')
    name = models.CharField(max_length=1000)
    korean_name = models.CharField(max_length=1000, blank=True, default='')
    email = models.EmailField(max_length=254, blank=True)
    affiliation = models.CharField(max_length=1000, blank=True)
    affiliation_ko = models.CharField(max_length=1000, blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.event.name})"

class Speaker(models.Model):
    """
    Speaker model
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='speakers')
    name = models.CharField(max_length=1000)
    korean_name = models.CharField(max_length=1000, blank=True, default='')
    email = models.EmailField(max_length=254)
    affiliation = models.CharField(max_length=1000, blank=True)
    affiliation_ko = models.CharField(max_length=1000, blank=True, default='')
    is_domestic = models.BooleanField(default=False)
    type = models.CharField(max_length=1000, choices=[
        ('keynote', 'Keynote Talk'),
        ('invited', 'Invited Talk'),
        ('contributed', 'Contributed Talk'),
        ('short', 'Short Talk'),
        ('poster', 'Poster'),
    ])

class AbstractVote(models.Model):
    """
    AbstractVote model
    """
    reviewer = models.ForeignKey('Attendee', on_delete=models.CASCADE)
    voted_abstracts = models.ManyToManyField('Abstract', related_name='votes')

class Abstract(models.Model):
    """
    Abstract model
    """
    TYPE_CHOICES = [
        ('speaker', 'Speaker'),
        ('poster', 'Poster'),
    ]

    attendee = models.ForeignKey(Attendee, null=True, on_delete=models.CASCADE, related_name='abstracts')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='abstracts')
    title = models.CharField(max_length=1000)
    file_path = models.CharField(max_length=1000)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='poster')
    wants_short_talk = models.BooleanField(default=False)  # Only applicable for poster type
    def delete(self):
        try:
            import os, shutil
            from django.conf import settings
            shutil.rmtree(os.path.dirname(os.path.join(settings.MEDIA_ROOT, self.file_path)))
        except:
            pass
        super(Abstract, self).delete()

class CustomQuestion(models.Model):
    """
    CustomQuestion model
    """
    event = models.ForeignKey(Event, null=True, on_delete=models.CASCADE, related_name='custom_questions')
    question = models.JSONField() # {'type': one of 'text' or 'textarea' or 'checkbox' or 'dropdown',
                                  #  'question': 'What is your favorite color?',
                                  #  'detail': 'Please select one color.',
                                  #  'options': ['Red', 'Green', 'Blue']}
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

class CustomAnswer(models.Model):
    """
    CustomAnswer model
    """
    reference = models.ForeignKey(CustomQuestion, null=True, blank=True, on_delete=models.SET_NULL)
    attendee = models.ForeignKey(Attendee, null=True, on_delete=models.CASCADE, related_name='custom_answers')
    question = models.TextField(blank=True)
    answer = models.TextField(blank=True)

class EmailTemplate(models.Model):
    """
    EmailTemplates model
    """
    subject = models.CharField(max_length=1000)
    body = models.TextField()

class EmailVerificationKey(models.Model):
    """
    Temporary verification keys for email verification resend
    """
    email = models.EmailField()
    verification_key = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['email', 'verification_key']),
        ]

class PaymentHistory(models.Model):
    """
    Payment history for event registrations
    """
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
    ]

    attendee = models.ForeignKey(Attendee, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    event = models.ForeignKey('Event', on_delete=models.SET_NULL, null=True, related_name='payments')
    amount = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    payment_type = models.CharField(max_length=50, blank=True)  # Payment method from Toss (e.g., 카드, 계좌이체)
    note = models.TextField(blank=True)  # Admin notes for the transaction
    # Toss Payments fields
    toss_payment_key = models.CharField(max_length=200, blank=True, null=True)
    toss_order_id = models.CharField(max_length=64, blank=True, null=True)  # Our generated order ID
    created_at = models.DateTimeField(auto_now_add=True)

    # Copied attendee information for receipts (preserved even if attendee is deleted)
    attendee_first_name = models.CharField(max_length=1000, blank=True)
    attendee_middle_initial = models.CharField(max_length=1, blank=True)
    attendee_last_name = models.CharField(max_length=1000, blank=True)
    attendee_korean_name = models.CharField(max_length=1000, blank=True)
    attendee_nationality = models.IntegerField(null=True, blank=True)
    attendee_institute = models.CharField(max_length=1000, blank=True)
    attendee_institute_ko = models.CharField(max_length=1000, blank=True)
    attendee_department = models.CharField(max_length=1000, blank=True)
    attendee_job_title = models.CharField(max_length=1000, blank=True)
    attendee_email = models.EmailField(blank=True)

    # Copied event information for receipts (preserved even if event is deleted)
    event_name = models.CharField(max_length=1000, blank=True)
    event_start_date = models.DateField(null=True, blank=True)
    event_end_date = models.DateField(null=True, blank=True)
    event_venue = models.CharField(max_length=1000, blank=True)
    event_venue_ko = models.CharField(max_length=1000, blank=True)
    event_organizers_en = models.CharField(max_length=1000, blank=True)
    event_organizers_ko = models.CharField(max_length=1000, blank=True)

    @property
    def attendee_name(self):
        """Get the attendee's full name from copied fields"""
        if self.attendee_first_name or self.attendee_last_name:
            middle = f" {self.attendee_middle_initial}" if self.attendee_middle_initial else ""
            return f'{self.attendee_first_name}{middle} {self.attendee_last_name}'.strip()
        return self.attendee_korean_name or ''

    def copy_attendee_info(self, attendee):
        """Copy attendee information for receipt preservation"""
        self.attendee_first_name = attendee.first_name
        self.attendee_middle_initial = attendee.middle_initial
        self.attendee_last_name = attendee.last_name
        self.attendee_korean_name = attendee.korean_name
        self.attendee_nationality = attendee.nationality
        self.attendee_institute = attendee.institute
        self.attendee_institute_ko = attendee.institute_ko
        self.attendee_department = attendee.department
        self.attendee_job_title = attendee.job_title
        self.attendee_email = attendee.user.email if attendee.user else ''

    def copy_event_info(self, event):
        """Copy event information for receipt preservation"""
        self.event_name = event.name
        self.event_start_date = event.start_date
        self.event_end_date = event.end_date
        self.event_venue = event.venue or ''
        self.event_venue_ko = event.venue_ko or ''
        self.event_organizers_en = event.organizers_en or ''
        self.event_organizers_ko = event.organizers_ko or ''

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Payment histories'

    def __str__(self):
        email = self.attendee_email or 'Unknown'
        event_name = self.event_name or (self.event.name if self.event else 'Unknown')
        return f"Payment #{self.id} - {email} - {event_name}"


class BusinessSettings(models.Model):
    """
    Singleton model for business settings used in receipts (영수증용 사업자 정보)
    """
    business_name = models.CharField(max_length=200, blank=True)  # 상호명
    business_registration_number = models.CharField(max_length=20, blank=True)  # 사업자등록번호
    address = models.CharField(max_length=500, blank=True)  # 주소
    representative = models.CharField(max_length=100, blank=True)  # 대표자
    phone = models.CharField(max_length=20, blank=True)  # 연락처
    email = models.EmailField(blank=True)  # 이메일
    timezone = models.CharField(max_length=50, default='Asia/Seoul')  # 시간대

    class Meta:
        verbose_name = 'Business Settings'
        verbose_name_plural = 'Business Settings'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion of the singleton instance
        pass

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Business Settings - {self.business_name}"


class AccountSettings(models.Model):
    """
    Singleton model for account and data retention settings
    """
    # Account inactivity settings (in days)
    account_deletion_period = models.IntegerField(default=3 * 365)  # 3 years default
    account_warning_period = models.IntegerField(default=7)  # Warning sent 7 days before deletion

    # Data retention settings (in years) - minimum 5 years
    attendee_retention_years = models.IntegerField(default=5)  # Minimum 5 years
    payment_retention_years = models.IntegerField(default=5)  # Minimum 5 years

    MINIMUM_RETENTION_YEARS = 5  # Cannot be set lower than this

    class Meta:
        verbose_name = 'Account Settings'
        verbose_name_plural = 'Account Settings'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        self.pk = 1
        # Enforce minimum retention periods
        if self.attendee_retention_years < self.MINIMUM_RETENTION_YEARS:
            self.attendee_retention_years = self.MINIMUM_RETENTION_YEARS
        if self.payment_retention_years < self.MINIMUM_RETENTION_YEARS:
            self.payment_retention_years = self.MINIMUM_RETENTION_YEARS
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion of the singleton instance
        pass

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Account Settings"


class SiteSettings(models.Model):
    """
    Singleton model for site name and meta tag settings
    """
    site_name = models.CharField(max_length=200, default='IEUM')
    site_description = models.TextField(
        blank=True,
        default='An open-source conference management system for organizing scientific conferences. Manage event registrations, abstract submissions, and attendee workflows seamlessly.'
    )
    site_keywords = models.CharField(
        max_length=500,
        blank=True,
        default='conference management, event registration, abstract submission, scientific conference, academic event'
    )

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Site Settings - {self.site_name}"


class PrivacyPolicy(models.Model):
    """
    Singleton model for privacy policy content in English and Korean.
    Content supports Django template syntax for dynamic values from BusinessSettings.
    """
    content_en = models.TextField(blank=True, default='')  # English content (informational)
    content_ko = models.TextField(blank=True, default='')  # Korean content (legally binding)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Privacy Policy'
        verbose_name_plural = 'Privacy Policies'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion of the singleton instance
        pass

    @classmethod
    def _load_default_template(cls, language):
        """Load default template content from file"""
        import os
        from django.conf import settings
        template_name = f'privacy_policy_{language}.txt'
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'terms', template_name)
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ''

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance. Initialize with default templates if newly created."""
        obj, created = cls.objects.get_or_create(pk=1)
        if created:
            obj.content_en = cls._load_default_template('en')
            obj.content_ko = cls._load_default_template('ko')
            obj.save()
        return obj

    def render_content(self, language='en'):
        """
        Render the content using Django's template engine with BusinessSettings and AccountSettings context.
        """
        from django.template import Template, Context

        business = BusinessSettings.get_instance()
        account = AccountSettings.get_instance()

        context = Context({
            # BusinessSettings
            'business_name': business.business_name,
            'business_registration_number': business.business_registration_number,
            'address': business.address,
            'representative': business.representative,
            'phone': business.phone,
            'email': business.email,
            # AccountSettings
            'account_deletion_period': account.account_deletion_period,
            'account_deletion_years': account.account_deletion_period // 365,
            'account_warning_period': account.account_warning_period,
            'attendee_retention_years': account.attendee_retention_years,
            'payment_retention_years': account.payment_retention_years,
        })

        content = self.content_ko if language == 'ko' else self.content_en

        if not content.strip():
            return ''

        try:
            template = Template(content)
            return template.render(context)
        except Exception:
            return content  # Return raw content if template rendering fails

    def __str__(self):
        return "Privacy Policy"


class TermsOfService(models.Model):
    """
    Singleton model for terms of service content in English and Korean.
    Content supports Django template syntax for dynamic values from BusinessSettings.
    """
    content_en = models.TextField(blank=True, default='')  # English content (informational)
    content_ko = models.TextField(blank=True, default='')  # Korean content (legally binding)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Terms of Service'
        verbose_name_plural = 'Terms of Service'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion of the singleton instance
        pass

    @classmethod
    def _load_default_template(cls, language):
        """Load default template content from file"""
        import os
        from django.conf import settings
        template_name = f'terms_of_service_{language}.txt'
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'terms', template_name)
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ''

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance. Initialize with default templates if newly created."""
        obj, created = cls.objects.get_or_create(pk=1)
        if created:
            obj.content_en = cls._load_default_template('en')
            obj.content_ko = cls._load_default_template('ko')
            obj.save()
        return obj

    def render_content(self, language='en'):
        """
        Render the content using Django's template engine with BusinessSettings and AccountSettings context.
        """
        from django.template import Template, Context

        business = BusinessSettings.get_instance()
        account = AccountSettings.get_instance()

        context = Context({
            # BusinessSettings
            'business_name': business.business_name,
            'business_registration_number': business.business_registration_number,
            'address': business.address,
            'representative': business.representative,
            'phone': business.phone,
            'email': business.email,
            # AccountSettings
            'account_deletion_period': account.account_deletion_period,
            'account_deletion_years': account.account_deletion_period // 365,
            'account_warning_period': account.account_warning_period,
            'attendee_retention_years': account.attendee_retention_years,
            'payment_retention_years': account.payment_retention_years,
        })

        content = self.content_ko if language == 'ko' else self.content_en

        if not content.strip():
            return ''

        try:
            template = Template(content)
            return template.render(context)
        except Exception:
            return content  # Return raw content if template rendering fails

    def __str__(self):
        return "Terms of Service"


class ManualTransaction(models.Model):
    """
    Manual transaction details for admin-entered payments (직접입력)
    Linked to PaymentHistory via OneToOne relationship
    """
    PAYMENT_TYPE_CHOICES = [
        ('card', '카드'),
        ('transfer', '계좌이체'),
        ('cash', '현금'),
    ]

    payment = models.OneToOneField(PaymentHistory, on_delete=models.CASCADE, related_name='manual_transaction')
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TYPE_CHOICES)
    # Common fields
    supply_amount = models.IntegerField(default=0)  # Supply amount (공급가액)
    vat = models.IntegerField(default=0)  # VAT amount
    # Card-specific fields
    card_type = models.CharField(max_length=100, blank=True)  # Card issuer (e.g., 신한카드)
    card_number = models.CharField(max_length=50, blank=True)  # Masked card number
    approval_number = models.CharField(max_length=50, blank=True)  # Approval number
    installment = models.CharField(max_length=20, blank=True, default='single')  # Installment plan
    # Transfer-specific fields
    transaction_datetime = models.DateTimeField(null=True, blank=True)  # 거래일시
    transaction_description = models.CharField(max_length=200, blank=True)  # 거래내용

    def __str__(self):
        return f"Manual: {self.get_payment_type_display()} - Payment #{self.payment_id}"


class ExchangeRate(models.Model):
    """
    Cached exchange rate for currency conversion (e.g., KRW to USD)
    Updated once per day from Open Exchange Rates API
    """
    currency_from = models.CharField(max_length=3)  # e.g., 'KRW'
    currency_to = models.CharField(max_length=3)  # e.g., 'USD'
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['currency_from', 'currency_to']

    def __str__(self):
        return f"{self.currency_from}/{self.currency_to}: {self.rate}"
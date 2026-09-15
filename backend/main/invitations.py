"""Invitation links: an admin emails one, the recipient opens it, and they are
registered for the event.

Three moments matter:

1. ``send`` - the admin names addresses and a body. Each address gets its own
   EventInvitation row and its own link, rendered into the body by the
   ``{{ invitation_link }}`` template variable.

2. ``accept`` - the link's owner is logged in (or has just signed up; see
   ``main.forms.CustomSignupForm.signup``) and is registered from their profile
   rather than from the registration form. The token is bound to the invited
   address, so someone else's account cannot spend it.

3. Already registered - the link still settles the fee waiver, so an admin can
   invite someone who beat them to the form and waive them that way.
"""

import logging
import secrets

from django.conf import settings
from django.utils import timezone

from main.models import Attendee, EventInvitation, Speaker
from main.tasks import send_mail
from main.utils import render_email_template

logger = logging.getLogger(__name__)


class InvitationError(Exception):
    """Refused, with a code the API turns into a response."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def link_for(invitation):
    return f"{settings.HEADLESS_URL_ROOT}/invite/{invitation.token}"


def new_token():
    # 32 bytes is far past guessable; 43 characters after encoding.
    return secrets.token_urlsafe(32)


def template_context(invitation):
    return {
        'event': invitation.event,
        'invitation': invitation,
        'invitation_link': link_for(invitation),
    }


def send(event, emails, subject, body, fee_waived, invited_by, attachments=None,
         as_speaker=False, as_chair=False):
    """Create one invitation per address and email it. Returns the rows."""
    reply_to = event.main_admin.email if event.main_admin else None
    created = []
    for email in emails:
        invitation = EventInvitation.objects.create(
            event=event,
            email=email,
            token=new_token(),
            fee_waived=fee_waived,
            as_speaker=as_speaker,
            as_chair=as_chair,
            invited_by=invited_by,
        )
        context = template_context(invitation)
        send_mail.delay(
            render_email_template(subject, context),
            render_email_template(body, context),
            email,
            reply_to=reply_to,
            rich=True,
            attachments=attachments or [],
        )
        created.append(invitation)
    return created


def attendee_from_profile(event, user, category):
    """The registration the form would have produced, filled from the account."""
    institution = user.institute
    return Attendee.objects.create(
        user=user,
        event=event,
        category=category,
        first_name=user.first_name,
        middle_initial=user.middle_initial,
        last_name=user.last_name,
        korean_name=user.korean_name,
        nationality=user.nationality,
        institute=institution.name_en if institution else '',
        institute_ko=institution.name_ko if institution else '',
        department=user.department,
        job_title=user.job_title,
        disability=user.disability,
        dietary=user.dietary,
    )


def accept(invitation, user):
    """Register ``user`` through this invitation. Returns the attendee.

    Idempotent for the person it was sent to: opening the link twice, or
    opening it after registering by hand, just makes sure the waiver is in
    place. Raises InvitationError when it cannot be honoured.

    The registration deadline is deliberately not checked - an admin sending
    an invitation after the deadline is the override - but capacity is, since
    the room does not get bigger for an invited guest.
    """
    if not invitation.matches(user.email):
        raise InvitationError(
            'wrong_account',
            'This invitation was sent to a different email address. '
            'Please log in with the account that received it.',
        )

    event = invitation.event
    attendee = event.attendees.filter(user=user).first()
    newly_registered = attendee is None

    if newly_registered:
        if event.capacity > 0 and event.capacity <= event.attendees.count():
            raise InvitationError('event_full', 'Sorry, the event is full.')
        category = event.active_categories[0] if event.active_categories else None
        attendee = attendee_from_profile(event, user, category)
        event.attendees.add(attendee)

    if invitation.fee_waived and not attendee.fee_waived:
        attendee.fee_waived = True
        attendee.save(update_fields=['fee_waived'])

    if invitation.as_speaker or invitation.as_chair:
        list_as_speaker(invitation, attendee)

    if not invitation.is_accepted:
        invitation.accepted_at = timezone.now()
        invitation.attendee = attendee
        invitation.save(update_fields=['accepted_at', 'attendee'])

    if newly_registered:
        send_registration_confirmation(event, attendee, user.email)

    return attendee


def list_as_speaker(invitation, attendee):
    """Put the accepted invitee on the speaker/chair list.

    Done at acceptance rather than when the invitation is sent, because only
    then is there a profile to fill the row from - a list entry with nothing
    but an email address would be a blank line on the speakers tab. Someone
    already listed just gains the invited role(s); their exemption follows
    the invitation only when it waives the fee, never the other way.
    """
    event = invitation.event
    existing = event.speakers.filter(email__iexact=attendee.email).first()
    if existing:
        existing.is_speaker = existing.is_speaker or invitation.as_speaker
        existing.is_chair = existing.is_chair or invitation.as_chair
        if invitation.fee_waived:
            existing.is_payment_exempt = True
        existing.save(update_fields=['is_speaker', 'is_chair', 'is_payment_exempt'])
        return existing
    return Speaker.objects.create(
        event=event,
        name=attendee.name,
        korean_name=attendee.korean_name,
        email=attendee.email,
        affiliation=attendee.institute,
        affiliation_ko=attendee.institute_ko,
        is_domestic=attendee.nationality == 1,
        is_payment_exempt=invitation.fee_waived,
        is_speaker=invitation.as_speaker,
        is_chair=invitation.as_chair,
        type='invited',
    )


def send_registration_confirmation(event, attendee, to):
    """The same confirmation a form registration triggers."""
    template = event.email_template_registration
    if template is None:
        return
    context = {'event': event, 'attendee': attendee}
    reply_to = event.main_admin.email if event.main_admin else None
    send_mail.delay(
        render_email_template(template.subject, context),
        render_email_template(template.body, context),
        to,
        reply_to=reply_to,
        rich=True,
        attachments=list(template.attachments.values_list('file_path', flat=True)),
    )


def accept_by_token(token, user):
    """``accept`` for a token that may not exist; used by the signup hook.

    Never raises: the person is mid-signup, and a bad invitation must not
    cost them the account. The miss is logged and the signup goes on.
    """
    if not token:
        return None
    try:
        invitation = EventInvitation.objects.select_related('event').get(token=token)
    except EventInvitation.DoesNotExist:
        logger.warning('Signup carried an unknown invitation token')
        return None
    try:
        return accept(invitation, user)
    except InvitationError as exc:
        logger.info('Invitation %s not applied at signup for %s: %s',
                    invitation.id, user.email, exc.code)
        return None

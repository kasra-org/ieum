# The previous default (0083) opened "On behalf of the organising committee"
# and signed with the main admin's name. The mail goes out in the committee's
# own name, so both change; a template still holding that text is rewritten,
# and one the admin has edited is left alone. Events that never ran 0083 with
# the interim text are already on the final wording, since 0083 reads the
# current default.

from django.conf import settings
from django.db import migrations


def interim_body():
    return (
        "Dear Colleague,\n\n"
        "On behalf of the organising committee, it is our great pleasure to "
        "invite you to {{ event.name }}.\n\n"
        "{% if invitation.as_speaker and invitation.as_chair %}"
        "We would be honoured if you would join us as an invited speaker and "
        "also serve as a session chair.\n\n"
        "{% elif invitation.as_speaker %}"
        "We would be honoured if you would join us as an invited speaker.\n\n"
        "{% elif invitation.as_chair %}"
        "We would be honoured if you would serve as a session chair.\n\n"
        "{% endif %}"
        "Event Details:\n"
        " - Dates: {{ event.start_date|date:'F d, Y' }} - {{ event.end_date|date:'F d, Y' }}\n"
        " - Venue: {{ event.venue }}\n"
        " - Official Website: {{ event.link_info }}\n\n"
        "To accept this invitation, kindly follow the link below. Should you not "
        "yet have an account, you may create one there; your registration for "
        "the event will be completed at the same time.\n\n"
        "[{{ invitation_link }}]({{ invitation_link }})\n\n"
        "{% if invitation.fee_waived %}Please note that the registration fee is "
        "waived for you.\n\n{% endif %}"
        "Should you have any questions, please do not hesitate to contact us at "
        + settings.EMAIL_FROM + ".\n\n"
        "We sincerely hope you will be able to join us and look forward to "
        "welcoming you.\n\n"
        "Yours sincerely,\n"
        "{{ event.organizers_en }}"
    )


def forwards(apps, schema_editor):
    # The default bodies embed EMAIL_FROM. With it unset the old text cannot
    # be recognised and the new one would carry no contact address, so this
    # rewrite is skipped rather than either crashing the migration or writing
    # a broken template. Nothing is lost: the admin can paste the new text in.
    if not settings.EMAIL_FROM:
        return
    from main.apis import default_invitation_body
    Event = apps.get_model('main', 'Event')
    EmailTemplate = apps.get_model('main', 'EmailTemplate')
    ids = Event.objects.exclude(email_template_invitation=None).values_list(
        'email_template_invitation_id', flat=True)
    EmailTemplate.objects.filter(id__in=list(ids), body=interim_body()).update(
        body=default_invitation_body())


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0083_formal_invitation_body'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

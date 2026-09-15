# Rewrites invitation templates that still carry the first default body, so
# events created before the wording was revised get the formal, role-aware
# text without the admin having to paste it in. A template the admin has
# edited differs from the old default and is left exactly as it is.

from django.conf import settings
from django.db import migrations


def old_body():
    return (
        "Dear Colleague,\n\n"
        "You are invited to {{ event.name }}.\n\n"
        "Event Details:\n"
        " - Dates: {{ event.start_date|date:'F d, Y' }} - {{ event.end_date|date:'F d, Y' }}\n"
        " - Venue: {{ event.venue }}\n"
        " - Official Website: {{ event.link_info }}\n\n"
        "To accept this invitation, please open the link below. If you do not "
        "have an account yet, you can create one there and your registration "
        "for the event will be completed at the same time.\n\n"
        "[{{ invitation_link }}]({{ invitation_link }})\n\n"
        "{% if invitation.fee_waived %}The registration fee is waived for you.\n\n{% endif %}"
        "If you have any questions, please contact us at: " + settings.EMAIL_FROM + "\n\n"
        "Warm regards,\n"
        "{{ event.organizers_en }}"
    )


def new_body():
    # Kept in step with main.apis.default_invitation_body by the test suite.
    from main.apis import default_invitation_body
    return default_invitation_body()


def forwards(apps, schema_editor):
    # The default bodies embed EMAIL_FROM. With it unset the old text cannot
    # be recognised and the new one would carry no contact address, so this
    # rewrite is skipped rather than either crashing the migration or writing
    # a broken template. Nothing is lost: the admin can paste the new text in.
    if not settings.EMAIL_FROM:
        return
    Event = apps.get_model('main', 'Event')
    EmailTemplate = apps.get_model('main', 'EmailTemplate')
    ids = Event.objects.exclude(email_template_invitation=None).values_list(
        'email_template_invitation_id', flat=True)
    EmailTemplate.objects.filter(id__in=list(ids), body=old_body()).update(body=new_body())


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0082_speaker_roles'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

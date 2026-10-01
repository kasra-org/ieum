# A registration that has been paid for must not also be exempt: the exemption
# makes it report as free, hiding the payment. People do pay first and become a
# speaker or chair afterwards, so existing rows can be in that state. This
# clears the exemption wherever a completed payment exists - on the speaker
# list entry, and on a per-registration waiver. From here on the API refuses
# to set either for a paid registration.

from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    Speaker = apps.get_model('main', 'Speaker')
    Attendee = apps.get_model('main', 'Attendee')
    PaymentHistory = apps.get_model('main', 'PaymentHistory')

    paid_attendee_ids = set(
        PaymentHistory.objects.filter(status='completed', attendee__isnull=False)
        .values_list('attendee_id', flat=True))
    if not paid_attendee_ids:
        return

    Attendee.objects.filter(id__in=paid_attendee_ids, fee_waived=True).update(fee_waived=False)

    for speaker in Speaker.objects.filter(is_payment_exempt=True):
        email = (speaker.email or '').strip()
        if not email:
            continue
        paid = Attendee.objects.filter(
            Q(user__email__iexact=email) | Q(user_email__iexact=email),
            event_id=speaker.event_id, id__in=paid_attendee_ids,
        ).exists()
        if paid:
            speaker.is_payment_exempt = False
            speaker.save(update_fields=['is_payment_exempt'])


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0084_invitation_from_committee'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

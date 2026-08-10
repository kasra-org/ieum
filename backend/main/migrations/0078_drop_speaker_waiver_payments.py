from django.db import migrations

# The first version of the speaker exemption recorded a zero-amount payment.
# It is now read from the speaker list instead, so these rows describe a
# transaction that never happened - and they offered a receipt for it.
SPEAKER_PAYMENT_TYPE = '연사'


def drop_waiver_payments(apps, schema_editor):
    PaymentHistory = apps.get_model('main', 'PaymentHistory')
    PaymentHistory.objects.filter(payment_type=SPEAKER_PAYMENT_TYPE, amount=0).delete()


def noop(apps, schema_editor):
    """Nothing to restore: the exemption is derived, so these add no information."""


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0077_speaker_payment_exemption'),
    ]

    operations = [
        migrations.RunPython(drop_waiver_payments, noop),
    ]

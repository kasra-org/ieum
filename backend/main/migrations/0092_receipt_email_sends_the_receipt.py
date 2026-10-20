from django.db import migrations

# The receipt email's earlier default texts: the first, for walk-ins, and
# the one for every payer (0091). Both read as confirming the payment; a
# template still holding either, unedited, gets the text that sends the
# receipt.
FIRST = '{{ name }}님, {{ event.name }} 현장 등록 결제가 확인되었습니다.\n\n- 결제 금액: {{ amount }}원\n- 결제일: {{ payment_date }}\n\n[영수증 보기]({{ receipt_link }})\n\n---\n\nDear {{ name }},\n\nYour on-site registration payment for {{ event.name }} has been received.\n\n- Amount paid: KRW {{ amount }}\n- Date: {{ payment_date }}\n\n[View your receipt]({{ receipt_link }})\n\n{{ event.name }}'
SECOND = FIRST.replace('현장 등록 결제', '등록비 결제').replace('on-site registration payment', 'registration payment')
NEW = (
    "{{ name }}님, {{ event.name }} 등록비 결제 영수증을 송부드립니다.\n\n"
    "- 결제 금액: {{ amount }}원\n"
    "- 결제일: {{ payment_date }}\n\n"
    "아래 링크에서 영수증을 확인 및 출력하실 수 있습니다.\n\n"
    "[영수증 보기]({{ receipt_link }})\n\n"
    "---\n\n"
    "Dear {{ name_en }},\n\n"
    "Please find below the receipt for your registration payment for {{ event.name }}.\n\n"
    "- Amount paid: KRW {{ amount }}\n"
    "- Date: {{ payment_date }}\n\n"
    "You can view and print it at the link below.\n\n"
    "[View your receipt]({{ receipt_link }})\n\n"
    "{{ event.name }}"
)


def send_the_receipt_rather_than_confirm(apps, schema_editor):
    EmailTemplate = apps.get_model('main', 'EmailTemplate')
    EmailTemplate.objects.filter(email_template_receipt__isnull=False, body__in=[FIRST, SECOND]).update(body=NEW)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0091_receipt_for_every_payment'),
    ]

    operations = [
        migrations.RunPython(send_the_receipt_rather_than_confirm, migrations.RunPython.noop),
    ]

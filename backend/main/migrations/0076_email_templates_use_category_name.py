from django.db import migrations

# get_student_status_display() went away with the field; category_name is the
# equivalent on the new model.
STALE = '{{ attendee.get_student_status_display }}'
CURRENT = '{{ attendee.category_name }}'


def use_category_name(apps, schema_editor):
    """Point existing templates at the new field.

    Targeted rather than a wholesale overwrite, so an organiser's customised
    wording around the line is preserved.
    """
    EmailTemplate = apps.get_model('main', 'EmailTemplate')
    for template in EmailTemplate.objects.filter(body__contains=STALE):
        template.body = template.body.replace(STALE, CURRENT)
        template.save(update_fields=['body'])


def revert(apps, schema_editor):
    EmailTemplate = apps.get_model('main', 'EmailTemplate')
    for template in EmailTemplate.objects.filter(body__contains=CURRENT):
        template.body = template.body.replace(CURRENT, STALE)
        template.save(update_fields=['body'])


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0075_registration_categories'),
    ]

    operations = [
        migrations.RunPython(use_category_name, revert),
    ]

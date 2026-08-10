from django.db import migrations, models
import django.db.models.deletion

# Names the three fixed tiers were shown under, so a migrated event reads exactly
# as it did before. They are ordinary rows from here on - editable and removable.
UNDERGRADUATE = {'name': 'Undergraduate student', 'name_ko': '학부생'}
GRADUATE = {'name': 'Graduate student / Postdoc', 'name_ko': '대학원생/박사후연구원'}
STANDARD = {'name': 'PI / Non-academic', 'name_ko': 'PI / 일반'}


def build_categories(apps, schema_editor):
    """Turn each event's fixed tiers into rows, then repoint its registrations.

    Only the tiers an event actually offered become categories, and every
    attendee is mapped to the one that priced them: a status whose tier was
    switched off was charged the standard fee, so it maps to the standard
    category and the amount owed does not move.
    """
    Event = apps.get_model('main', 'Event')
    RegistrationCategory = apps.get_model('main', 'RegistrationCategory')

    for event in Event.objects.all():
        categories = {}
        order = 0

        if event.undergraduate_enabled:
            categories['undergraduate'] = RegistrationCategory.objects.create(
                event=event, order=order, is_active=True,
                fee=event.registration_fee_undergraduate or 0,
                onsite_fee=event.onsite_registration_fee_undergraduate,
                **UNDERGRADUATE,
            )
            order += 1

        if event.graduate_enabled:
            categories['graduate'] = RegistrationCategory.objects.create(
                event=event, order=order, is_active=True,
                fee=event.registration_fee_graduate or 0,
                onsite_fee=event.onsite_registration_fee_graduate,
                **GRADUATE,
            )
            order += 1

        # Always offered, and the price anyone outside a student tier paid.
        standard = RegistrationCategory.objects.create(
            event=event, order=order, is_active=True,
            fee=event.registration_fee or 0,
            onsite_fee=event.onsite_registration_fee,
            **STANDARD,
        )
        categories['pi_non_academic'] = standard

        for model_name in ('Attendee', 'OnSiteAttendee'):
            Model = apps.get_model('main', model_name)
            for status, category in categories.items():
                Model.objects.filter(event=event, student_status=status).update(category=category)
            # Anything else - an unknown status, or one whose tier was off -
            # paid the standard fee.
            Model.objects.filter(event=event, category__isnull=True).update(category=standard)


def noop(apps, schema_editor):
    """Reversing drops the categories with the schema; the old columns return
    empty. Kept so the schema half of this migration can still be rolled back."""


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0074_alter_attendee_student_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistrationCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('name_ko', models.CharField(blank=True, max_length=200)),
                ('fee', models.IntegerField(default=0)),
                ('onsite_fee', models.IntegerField(blank=True, null=True)),
                ('order', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registration_categories', to='main.event')),
            ],
            options={
                'verbose_name_plural': 'registration categories',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddField(
            model_name='attendee',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='attendees', to='main.registrationcategory'),
        ),
        migrations.AddField(
            model_name='onsiteattendee',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='onsite_attendees', to='main.registrationcategory'),
        ),
        migrations.RunPython(build_categories, noop),
        migrations.RemoveField(model_name='attendee', name='student_status'),
        migrations.RemoveField(model_name='onsiteattendee', name='student_status'),
        migrations.RemoveField(model_name='event', name='registration_fee'),
        migrations.RemoveField(model_name='event', name='onsite_registration_fee'),
        migrations.RemoveField(model_name='event', name='onsite_registration_fee_undergraduate'),
        migrations.RemoveField(model_name='event', name='onsite_registration_fee_graduate'),
        migrations.RemoveField(model_name='event', name='undergraduate_enabled'),
        migrations.RemoveField(model_name='event', name='registration_fee_undergraduate'),
        migrations.RemoveField(model_name='event', name='graduate_enabled'),
        migrations.RemoveField(model_name='event', name='registration_fee_graduate'),
    ]

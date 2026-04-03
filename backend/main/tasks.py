from celery import shared_task
import base64
from datetime import timedelta
import logging

from django.core.mail import send_mail as django_send_mail
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def send_mail(subject, body, to, reply_to=None, cc=None):
    print(f"Sending email to {to}...")
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.EMAIL_FROM,
            to=[to],
            reply_to=[reply_to] if reply_to else [],
            cc=cc or [],
        )
        email.send(fail_silently=False)
        print(f"Mail sent to {to}!")
    except Exception as e:
        print(f"Error sending email to {to}: {e}")

@shared_task
def send_mail_with_attachment(subject, body, to, attachment_name, attachment_base64, attachment_mimetype='application/pdf', reply_to=None):
    """Send an email with a file attachment."""
    print(f"Sending email with attachment to {to}...")
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.EMAIL_FROM,
            to=[to],
            reply_to=[reply_to] if reply_to else [],
        )
        attachment_data = base64.b64decode(attachment_base64)
        email.attach(attachment_name, attachment_data, attachment_mimetype)
        email.send(fail_silently=False)
        print(f"Mail with attachment sent to {to}!")
    except Exception as e:
        print(f"Error sending email with attachment to {to}: {e}")


@shared_task
def check_inactive_users():
    """
    Check for inactive users and handle account deletion warnings/deletions.

    - Users inactive for (deletion_period - warning_period): Send warning email
    - Users inactive for deletion_period or more: Delete account (preserving Attendee records)
    """
    from main.models import User, Attendee, AccountSettings

    account_settings = AccountSettings.get_instance()
    now = timezone.now()
    deletion_days = account_settings.account_deletion_period
    warning_days = account_settings.account_warning_period

    deletion_threshold = now - timedelta(days=deletion_days)
    warning_threshold = now - timedelta(days=deletion_days - warning_days)

    # Find users to delete (inactive for deletion_period or more)
    users_to_delete = User.objects.filter(
        last_login__lte=deletion_threshold,
        is_staff=False,  # Don't delete staff accounts
        is_superuser=False,  # Don't delete superuser accounts
    )

    deleted_count = 0
    for user in users_to_delete:
        email = user.email
        logger.info(f"Deleting inactive user account: {email} (last login: {user.last_login})")

        # Preserve attendee records by marking them with deletion timestamp and email
        Attendee.objects.filter(user=user).update(
            user_deleted_at=now,
            user_email=email
        )

        user.delete()
        deleted_count += 1

    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} inactive user accounts")

    # Find users to warn (inactive for almost deletion_period, not yet warned)
    users_to_warn = User.objects.filter(
        last_login__lte=warning_threshold,
        last_login__gt=deletion_threshold,
        deletion_warning_sent=False,
        is_staff=False,
        is_superuser=False,
    )

    warned_count = 0
    for user in users_to_warn:
        deletion_date = user.last_login + timedelta(days=deletion_days)
        subject = f"{settings.ACCOUNT_EMAIL_SUBJECT_PREFIX}Account Deletion Warning"
        body = f"""Dear {user.first_name or user.username},

Your account has been inactive for a long time. According to our data retention policy, accounts that have been inactive for {deletion_days} days will be automatically deleted.

Your account will be deleted on {deletion_date.strftime('%Y-%m-%d')} unless you log in before that date.

To keep your account active, please log in to our website.

If you no longer wish to use our service, you can ignore this email and your account will be automatically deleted.

Best regards,
The IEUM Team
"""
        try:
            django_send_mail(subject, body, settings.EMAIL_FROM, [user.email], fail_silently=False)
            user.deletion_warning_sent = True
            user.save(update_fields=['deletion_warning_sent'])
            warned_count += 1
            logger.info(f"Sent deletion warning to: {user.email}")
        except Exception as e:
            logger.error(f"Failed to send deletion warning to {user.email}: {e}")

    if warned_count > 0:
        logger.info(f"Sent {warned_count} deletion warning emails")

    return {
        'deleted': deleted_count,
        'warned': warned_count,
    }


@shared_task
def cleanup_old_data():
    """
    Clean up old PaymentHistory records based on retention settings.

    - PaymentHistory records: Deleted after payment_retention_years from payment (created_at)
    """
    from main.models import PaymentHistory, AccountSettings

    account_settings = AccountSettings.get_instance()
    now = timezone.now()

    # Calculate retention threshold (from payment date)
    payment_threshold = now - timedelta(days=account_settings.payment_retention_years * 365)

    # Delete old payment history records (only those where attendee is null AND older than retention period from payment)
    old_payments = PaymentHistory.objects.filter(
        attendee__isnull=True,  # Attendee was deleted
        created_at__lte=payment_threshold  # Payment is older than retention period
    )
    payment_count = old_payments.count()
    old_payments.delete()

    if payment_count > 0:
        logger.info(f"Deleted {payment_count} old payment history records (retention: {account_settings.payment_retention_years} years from payment)")

    return {
        'payments_deleted': payment_count,
    }


@shared_task
def cleanup_media_files(min_age_hours=24):
    """
    Clean up orphaned media files (editor uploads and abstract files).

    - Editor files: Files in media/editor/ not referenced in Event descriptions,
      PrivacyPolicy, or TermsOfService content
    - Abstract files: Folders in media/abstracts/ not referenced in Abstract records
    """
    import os
    import re
    import shutil
    from django.conf import settings
    from main.models import Event, PrivacyPolicy, TermsOfService, Abstract

    min_age = timezone.now() - timedelta(hours=min_age_hours)
    media_root = settings.MEDIA_ROOT
    total_deleted = 0
    total_size = 0

    # === Editor Files Cleanup ===
    editor_dirs = [
        os.path.join(media_root, 'editor', 'images'),
        os.path.join(media_root, 'editor', 'attachments'),
    ]

    # Collect all referenced files from content
    referenced_files = set()
    file_pattern = re.compile(r'/media/(editor/(?:images|attachments)/[^"\'\s\)]+)')

    # Check Event descriptions
    for event in Event.objects.exclude(description=''):
        matches = file_pattern.findall(event.description)
        referenced_files.update(matches)

    # Check PrivacyPolicy
    try:
        policy = PrivacyPolicy.objects.get(pk=1)
        for content in [policy.content_en, policy.content_ko]:
            if content:
                matches = file_pattern.findall(content)
                referenced_files.update(matches)
    except PrivacyPolicy.DoesNotExist:
        pass

    # Check TermsOfService
    try:
        terms = TermsOfService.objects.get(pk=1)
        for content in [terms.content_en, terms.content_ko]:
            if content:
                matches = file_pattern.findall(content)
                referenced_files.update(matches)
    except TermsOfService.DoesNotExist:
        pass

    # Find and delete orphaned editor files
    editor_deleted = 0
    editor_size = 0
    for editor_dir in editor_dirs:
        if not os.path.exists(editor_dir):
            continue
        for uuid_folder in os.listdir(editor_dir):
            folder_path = os.path.join(editor_dir, uuid_folder)
            if os.path.isdir(folder_path):
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        rel_path = os.path.relpath(file_path, media_root)
                        mtime = os.path.getmtime(file_path)
                        file_time = timezone.datetime.fromtimestamp(
                            mtime, tz=timezone.get_current_timezone()
                        )
                        if rel_path not in referenced_files and file_time < min_age:
                            try:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                try:
                                    os.rmdir(folder_path)
                                except OSError:
                                    pass
                                editor_deleted += 1
                                editor_size += file_size
                                logger.info(f"Deleted orphaned editor file: {rel_path}")
                            except Exception as e:
                                logger.error(f"Failed to delete {rel_path}: {e}")

    # === Abstract Files Cleanup ===
    abstracts_dir = os.path.join(media_root, 'abstracts')
    abstract_deleted = 0
    abstract_size = 0

    if os.path.exists(abstracts_dir):
        db_abstract_paths = set(Abstract.objects.values_list('file_path', flat=True))

        for uuid_folder in os.listdir(abstracts_dir):
            folder_path = os.path.join(abstracts_dir, uuid_folder)
            if not os.path.isdir(folder_path):
                continue

            is_referenced = False
            folder_size = 0
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    rel_path = os.path.relpath(file_path, media_root)
                    folder_size += os.path.getsize(file_path)
                    if rel_path in db_abstract_paths:
                        is_referenced = True
                        break

            if not is_referenced:
                mtime = os.path.getmtime(folder_path)
                folder_time = timezone.datetime.fromtimestamp(
                    mtime, tz=timezone.get_current_timezone()
                )
                if folder_time < min_age:
                    try:
                        shutil.rmtree(folder_path)
                        abstract_deleted += 1
                        abstract_size += folder_size
                        logger.info(f"Deleted orphaned abstract folder: {uuid_folder}")
                    except Exception as e:
                        logger.error(f"Failed to delete abstract folder {uuid_folder}: {e}")

    total_deleted = editor_deleted + abstract_deleted
    total_size = editor_size + abstract_size

    if total_deleted > 0:
        logger.info(f"Media cleanup complete: deleted {total_deleted} items ({total_size} bytes)")

    return {
        'editor_files_deleted': editor_deleted,
        'editor_size': editor_size,
        'abstract_folders_deleted': abstract_deleted,
        'abstract_size': abstract_size,
    }

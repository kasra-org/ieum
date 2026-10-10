import os
import re
import shutil
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from main.models import Event, PrivacyPolicy, TermsOfService, Abstract


class Command(BaseCommand):
    help = 'Cleans up orphaned media files (editor uploads and abstract files)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--min-age-hours',
            type=int,
            default=24,
            help='Only delete files older than this many hours (default: 24)',
        )
        parser.add_argument(
            '--editor-only',
            action='store_true',
            help='Only clean up editor files',
        )
        parser.add_argument(
            '--abstracts-only',
            action='store_true',
            help='Only clean up abstract files',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_age_hours = options['min_age_hours']
        editor_only = options['editor_only']
        abstracts_only = options['abstracts_only']

        total_deleted = 0
        total_size = 0

        if not abstracts_only:
            deleted, size = self.cleanup_editor_files(dry_run, min_age_hours)
            total_deleted += deleted
            total_size += size

        if not editor_only:
            deleted, size = self.cleanup_abstract_files(dry_run, min_age_hours)
            total_deleted += deleted
            total_size += size

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDry run complete. Would delete {total_deleted} items ({total_size} bytes).'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nCleanup complete. Deleted {total_deleted} items ({total_size} bytes).'
            ))

    def cleanup_editor_files(self, dry_run, min_age_hours):
        """Clean up orphaned editor files."""
        self.stdout.write('\n=== Editor Files Cleanup ===')

        min_age = timezone.now() - timedelta(hours=min_age_hours)
        media_root = settings.MEDIA_ROOT
        editor_dirs = [
            os.path.join(media_root, 'editor', 'images'),
            os.path.join(media_root, 'editor', 'attachments'),
        ]

        # Collect all referenced files from content
        referenced_files = set()
        file_pattern = re.compile(r'/media/(editor/(?:images|attachments)/[^"\'\s\)]+)')

        # Check Event descriptions
        for description in Event.objects.exclude(description='').values_list('description', flat=True):
            referenced_files.update(file_pattern.findall(description))

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

        self.stdout.write(f'Referenced editor files: {len(referenced_files)}')

        # Find all editor files on disk
        all_files = []
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
                            all_files.append({
                                'rel_path': rel_path,
                                'abs_path': file_path,
                                'folder_path': folder_path,
                                'mtime': file_time,
                            })

        self.stdout.write(f'Total editor files on disk: {len(all_files)}')

        # Find orphaned files
        orphaned_files = []
        for file_info in all_files:
            if file_info['rel_path'] not in referenced_files:
                if file_info['mtime'] < min_age:
                    orphaned_files.append(file_info)

        if not orphaned_files:
            self.stdout.write(self.style.SUCCESS('No orphaned editor files found.'))
            return 0, 0

        self.stdout.write(f'Orphaned editor files (older than {min_age_hours}h): {len(orphaned_files)}')

        deleted_count = 0
        deleted_size = 0
        for file_info in orphaned_files:
            file_size = os.path.getsize(file_info['abs_path'])
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would delete: {file_info["rel_path"]}')
                deleted_size += file_size
            else:
                try:
                    os.remove(file_info['abs_path'])
                    try:
                        os.rmdir(file_info['folder_path'])
                    except OSError:
                        pass
                    deleted_count += 1
                    deleted_size += file_size
                    self.stdout.write(f'  Deleted: {file_info["rel_path"]}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Failed: {file_info["rel_path"]}: {e}'))

        return deleted_count if not dry_run else len(orphaned_files), deleted_size

    def cleanup_abstract_files(self, dry_run, min_age_hours):
        """Clean up orphaned abstract files."""
        self.stdout.write('\n=== Abstract Files Cleanup ===')

        min_age = timezone.now() - timedelta(hours=min_age_hours)
        media_root = settings.MEDIA_ROOT
        abstracts_dir = os.path.join(media_root, 'abstracts')

        if not os.path.exists(abstracts_dir):
            self.stdout.write('No abstracts directory found.')
            return 0, 0

        # Get all abstract file paths from database
        db_abstract_paths = set(
            Abstract.objects.values_list('file_path', flat=True)
        )
        self.stdout.write(f'Abstracts in database: {len(db_abstract_paths)}')

        # Find all abstract folders on disk
        orphaned_folders = []
        for uuid_folder in os.listdir(abstracts_dir):
            folder_path = os.path.join(abstracts_dir, uuid_folder)
            if not os.path.isdir(folder_path):
                continue

            # Check if any file in this folder is referenced in the database
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
                # Check folder modification time
                mtime = os.path.getmtime(folder_path)
                folder_time = timezone.datetime.fromtimestamp(
                    mtime, tz=timezone.get_current_timezone()
                )
                if folder_time < min_age:
                    orphaned_folders.append({
                        'path': folder_path,
                        'rel_path': os.path.relpath(folder_path, media_root),
                        'size': folder_size,
                    })

        disk_count = len([
            f for f in os.listdir(abstracts_dir)
            if os.path.isdir(os.path.join(abstracts_dir, f))
        ])
        self.stdout.write(f'Abstract folders on disk: {disk_count}')

        if not orphaned_folders:
            self.stdout.write(self.style.SUCCESS('No orphaned abstract folders found.'))
            return 0, 0

        self.stdout.write(f'Orphaned abstract folders (older than {min_age_hours}h): {len(orphaned_folders)}')

        deleted_count = 0
        deleted_size = 0
        for folder_info in orphaned_folders:
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would delete: {folder_info["rel_path"]}')
                deleted_size += folder_info['size']
            else:
                try:
                    shutil.rmtree(folder_info['path'])
                    deleted_count += 1
                    deleted_size += folder_info['size']
                    self.stdout.write(f'  Deleted: {folder_info["rel_path"]}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Failed: {folder_info["rel_path"]}: {e}'))

        return deleted_count if not dry_run else len(orphaned_folders), deleted_size

"""Whole-database backup and restore for superusers.

A backup is a .tar.gz holding a plain-SQL pg_dump of the database plus the
uploaded media tree, so a restore brings back both the rows and the files those
rows point at. pg_dump is used rather than Django's dumpdata because it captures
sequence positions: after a dumpdata/loaddata restore the next insert collides
with a restored primary key, whereas a pg_dump restore is exact.

Everything here is destructive or exposes every secret in the database, so the
endpoints that call it are superuser-only.
"""
import json
import os
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone

from django.conf import settings
from django.db import connection, connections


def _db():
    """The connected database's settings (the test DB under a test run)."""
    return connection.settings_dict


# Objects the dump restores, and the order matters: the media swap happens only
# after the SQL has applied cleanly, so a failed restore leaves media untouched.
SQL_NAME = 'database.sql'
MEDIA_DIR = 'media'
MANIFEST_NAME = 'manifest.json'


class BackupError(Exception):
    """A backup or restore could not be completed; the message is user-facing."""


def is_supported():
    """pg_dump/psql only apply to PostgreSQL; sqlite (local dev) is unsupported."""
    return connection.vendor == 'postgresql'


def _server_major():
    # connection.pg_version is an int like 130023; the major is the leading part.
    version = connection.pg_version
    return version // 10000 if version >= 100000 else version // 100


def _bin(name):
    """The pg client binary matching the server version, else whatever is on PATH.

    Debian installs versioned tools under /usr/lib/postgresql/<major>/bin, and the
    generic wrapper on PATH picks the newest installed version - which may be too
    new for the server. Preferring the matched binary keeps the dump restorable.
    """
    matched = f'/usr/lib/postgresql/{_server_major()}/bin/{name}'
    return matched if os.path.exists(matched) else name


def _pg_env():
    env = os.environ.copy()
    db = _db()
    if db.get('PASSWORD'):
        env['PGPASSWORD'] = str(db['PASSWORD'])
    return env


def _conn_args():
    db = _db()
    return [
        '--host', str(db.get('HOST') or 'localhost'),
        '--port', str(db.get('PORT') or '5432'),
        '--username', str(db.get('USER') or ''),
    ]


def _run(cmd, **kwargs):
    kwargs.setdefault('stdout', subprocess.PIPE)
    result = subprocess.run(cmd, env=_pg_env(), stderr=subprocess.PIPE, **kwargs)
    if result.returncode != 0:
        # The stderr tail is the useful part; the rest is repeated notices.
        tail = (result.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        raise BackupError('; '.join(tail[-3:]) or f'{cmd[0]} failed')
    return result


def create_backup(path):
    """Write a .tar.gz of the database dump and media files to `path`."""
    if not is_supported():
        raise BackupError('Backups are only available on PostgreSQL.')

    with tempfile.TemporaryDirectory() as tmp:
        sql_path = os.path.join(tmp, SQL_NAME)
        # --clean --if-exists makes the dump self-restoring: it drops each object
        # before recreating it. --no-owner/--no-privileges keep it free of role
        # names that may not exist on the machine it is restored to.
        with open(sql_path, 'wb') as out:
            _run([_bin('pg_dump'), *_conn_args(), '--no-owner', '--no-privileges',
                  '--clean', '--if-exists', str(_db()['NAME'])], stdout=out)

        manifest = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'database': str(_db()['NAME']),
            'includes_media': os.path.isdir(settings.MEDIA_ROOT),
        }
        with open(os.path.join(tmp, MANIFEST_NAME), 'w') as f:
            json.dump(manifest, f, indent=2)

        with tarfile.open(path, 'w:gz') as tar:
            tar.add(os.path.join(tmp, MANIFEST_NAME), arcname=MANIFEST_NAME)
            tar.add(sql_path, arcname=SQL_NAME)
            if os.path.isdir(settings.MEDIA_ROOT):
                tar.add(settings.MEDIA_ROOT, arcname=MEDIA_DIR)


# Terminate every other connection to this database first, so the DROPs in the
# dump are not blocked waiting on locks the app's own workers still hold.
_TERMINATE = (
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
    "WHERE datname = current_database() AND pid <> pg_backend_pid();"
)


def restore_backup(uploaded_file):
    """Replace the database and media with the contents of an uploaded backup."""
    if not is_supported():
        raise BackupError('Restore is only available on PostgreSQL.')

    with tempfile.TemporaryDirectory() as tmp:
        archive_path = os.path.join(tmp, 'backup.tar.gz')
        with open(archive_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        extracted = os.path.join(tmp, 'extracted')
        os.makedirs(extracted)
        try:
            with tarfile.open(archive_path, 'r:gz') as tar:
                # filter='data' (Python 3.12+) refuses absolute paths, ..
                # traversal, symlinks and device files - a tarball from an
                # untrusted uploader must not write outside this directory.
                tar.extractall(extracted, filter='data')
        except (tarfile.TarError, OSError) as exc:
            raise BackupError('The uploaded file is not a valid backup archive.') from exc

        sql_path = os.path.join(extracted, SQL_NAME)
        if not os.path.isfile(sql_path):
            raise BackupError(f'The archive does not contain {SQL_NAME}.')

        # Prepend the connection-termination so both run in one psql session,
        # leaving no window for a worker to reconnect and grab a lock between.
        combined = os.path.join(tmp, 'restore.sql')
        with open(combined, 'w') as out:
            out.write(_TERMINATE + '\n')
            with open(sql_path, 'r') as src:
                out.write(src.read())

        # Drop our own pooled connection so it is not one of the ones being
        # terminated mid-statement.
        connections.close_all()
        _run([_bin('psql'), *_conn_args(), '--dbname', str(_db()['NAME']),
              '--set', 'ON_ERROR_STOP=1', '--quiet', '--file', combined])

        _restore_media(extracted)
        connections.close_all()


def _restore_media(extracted):
    """Swap the media contents for the backup's, keeping the old set until it works.

    MEDIA_ROOT is a mounted volume, so the directory itself cannot be renamed;
    only its contents are moved. The current files are stashed alongside first,
    so a failure mid-way can roll them back. A backup with no media/ entry leaves
    the current files untouched.
    """
    import shutil

    source = os.path.join(extracted, MEDIA_DIR)
    if not os.path.isdir(source):
        return

    media_root = str(settings.MEDIA_ROOT)
    os.makedirs(media_root, exist_ok=True)
    stash = os.path.join(media_root, '.restore-old')
    shutil.rmtree(stash, ignore_errors=True)
    os.makedirs(stash)

    def _clear_live():
        for name in os.listdir(media_root):
            if name == '.restore-old':
                continue
            target = os.path.join(media_root, name)
            shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)

    # Move the current files into the stash.
    for name in os.listdir(media_root):
        if name == '.restore-old':
            continue
        shutil.move(os.path.join(media_root, name), os.path.join(stash, name))

    try:
        for name in os.listdir(source):
            shutil.move(os.path.join(source, name), os.path.join(media_root, name))
    except OSError as exc:
        # Roll the original files back before surfacing the failure.
        _clear_live()
        for name in os.listdir(stash):
            shutil.move(os.path.join(stash, name), os.path.join(media_root, name))
        shutil.rmtree(stash, ignore_errors=True)
        raise BackupError(
            'The database was restored but its media files could not be written.') from exc

    shutil.rmtree(stash, ignore_errors=True)

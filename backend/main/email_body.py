"""Turning an admin-authored email body into what actually goes on the wire.

Bodies are written in the same markdown editor the event description uses, so
they arrive as markdown that may reference uploaded files by their media URL:

    ![poster](/media/editor/images/<uuid>/poster.png)

A mail client cannot fetch that path, and most clients block remote images even
when the URL is absolute. So every referenced image is read off the media
storage, attached to the message, and its ``src`` rewritten to the ``cid:`` of
that attachment - the image then renders inline without a network round trip.

The message goes out as multipart/alternative: the markdown source is the
text/plain part (it is written to be readable as-is) and the rendered HTML is
the text/html one, so a plain-text client still gets something sensible.
"""

import logging
import mimetypes
import os
import re
from email.utils import make_msgid

import markdown
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

# Markdown, configured to match what the editor can produce. nl2br matters most:
# bodies predating rich text are plain paragraphs whose single newlines are real
# line breaks, and without it they would reflow into one blob.
MARKDOWN_EXTENSIONS = ['nl2br', 'tables', 'fenced_code', 'sane_lists']

# Where uploaded files live, as they appear in a body. Anything outside this
# prefix is left alone: it is somebody else's URL, not our storage.
MEDIA_URL_PREFIX = '/media/'

# <img src="..."> in the rendered HTML.
IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.IGNORECASE)

# Bare enough that a body can be styled without a stylesheet, which mail clients
# largely ignore anyway.
HTML_SHELL = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', \
Arial, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 14px; \
line-height: 1.6; color: #1f2937;">
{body}
</body>
</html>"""


def media_path(url):
    """The storage-relative path a body's URL points at, or None.

    None means the URL is not one of ours - an external image, say, or a link
    out to some other site - and must be left exactly as written.
    """
    if not url or not url.startswith(MEDIA_URL_PREFIX):
        return None
    path = url[len(MEDIA_URL_PREFIX):].split('?')[0].split('#')[0]
    # A body is admin-authored, but it is still text: never let one walk out of
    # the media root and attach an arbitrary file off the server.
    if not path or path.startswith('/') or '..' in path.split('/'):
        return None
    return path


def read_media(path):
    """The bytes stored at a media-relative path, or None if unreadable."""
    try:
        if not default_storage.exists(path):
            return None
        with default_storage.open(path, 'rb') as fh:
            return fh.read()
    except OSError as exc:
        logger.warning('Email body references unreadable media %s: %s', path, exc)
        return None


def guess_mimetype(filename, fallback='application/octet-stream'):
    return mimetypes.guess_type(filename)[0] or fallback


def render(body):
    """Render a markdown body into (html, inline_images).

    Each inline image is a dict of ``cid``/``filename``/``content``/``mimetype``
    ready to be attached; the HTML already points at their content ids. An image
    whose file is missing keeps its original src rather than breaking the send -
    the recipient sees a broken image instead of no email at all.
    """
    html = markdown.markdown(body or '', extensions=MARKDOWN_EXTENSIONS)
    inline_images = []
    # One cid per distinct source, so an image used twice is attached once.
    by_src = {}

    def swap(match):
        prefix, src, suffix = match.groups()
        if src in by_src:
            return f'{prefix}cid:{by_src[src]}{suffix}'

        path = media_path(src)
        content = read_media(path) if path else None
        if content is None:
            return match.group(0)

        filename = os.path.basename(path)
        # make_msgid gives the <...> form; a cid: URL references it without.
        cid = make_msgid()[1:-1]
        by_src[src] = cid
        inline_images.append({
            'cid': cid,
            'filename': filename,
            'content': content,
            'mimetype': guess_mimetype(filename, 'image/png'),
        })
        return f'{prefix}cid:{cid}{suffix}'

    html = IMG_SRC_RE.sub(swap, html)
    return HTML_SHELL.format(body=html), inline_images


def load_attachments(paths):
    """Read the files at these media-relative paths, skipping any that are gone.

    A body is sent even when an attachment has vanished - losing the file is
    better than losing the email, and the miss is logged.
    """
    loaded = []
    for path in paths or []:
        content = read_media(path)
        if content is None:
            logger.warning('Skipping missing email attachment: %s', path)
            continue
        filename = os.path.basename(path)
        loaded.append({
            'filename': filename,
            'content': content,
            'mimetype': guess_mimetype(filename),
        })
    return loaded

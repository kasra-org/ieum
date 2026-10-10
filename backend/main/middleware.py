"""
API key authentication for machine clients.

Runs as middleware rather than as a Django Ninja authenticator on purpose:
NinjaAPI is configured with `csrf=True`, and ninja checks CSRF *before* it runs
any authenticator, so an authenticator has no way to exempt its own requests.
Authenticating here — before the view — lets us both set `request.user` and
mark the request CSRF-exempt.

Setting `request.user` also means nothing downstream needs to change: ninja's
`django_auth` sees an authenticated user, and the existing `@ensure_staff` /
`@ensure_event_staff` decorators keep working as written.
"""

from django.utils import timezone


class ApiKeyAuthMiddleware:
    """Authenticate `X-API-Key: <key>` as the key's owner, on the API only.

    A missing or unknown key is left alone — the request continues
    unauthenticated and normal session auth applies.
    """

    HEADER = "HTTP_X_API_KEY"

    # API keys are issued for machine clients (the MCP server), which only ever
    # calls /api/. Without this scope a key would also authenticate the Django
    # admin UI and the allauth account pages as its owner, with CSRF disabled —
    # turning a credential meant for one JSON API into a full interactive
    # session for a staff account.
    PATH_PREFIX = "/api/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.META.get(self.HEADER, "").strip()
        if raw and request.path.startswith(self.PATH_PREFIX):
            user = self._resolve(raw)
            if user is not None:
                request.user = user
                # CSRF protects cookie-authenticated browsers. This request is
                # authenticated by a secret header that a cross-site attacker
                # cannot cause a browser to send, so the check does not apply.
                request._dont_enforce_csrf_checks = True
        return self.get_response(request)

    @staticmethod
    def _resolve(raw: str):
        from main.models import ApiKey

        try:
            key = ApiKey.objects.select_related("user").get(
                key_hash=ApiKey.hash_key(raw), revoked_at__isnull=True
            )
        except ApiKey.DoesNotExist:
            return None
        if not key.user.is_active:
            return None
        # Coarse timestamp: avoids a write on every single request.
        now = timezone.now()
        if key.last_used_at is None or (now - key.last_used_at).total_seconds() > 60:
            ApiKey.objects.filter(pk=key.pk).update(last_used_at=now)
        return key.user


class RejectNulMiddleware:
    """Refuse a request carrying text the database cannot store: 400, not 500.

    PostgreSQL text cannot hold NUL, and a lone surrogate cannot even be
    encoded to send it, so either one fails deep in a query - for any
    endpoint, since every one hands its input to the ORM. Such input is never
    meaningful here, so it is turned away at the door: in the path, the query
    string, the session and CSRF cookies, form fields, and any other body
    the views might parse as JSON (they do so whatever the declared type) -
    decoded to be sure, so text that merely mentions "\\u0000" passes.
    Uploaded files themselves (a backup is binary) are left alone.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import JsonResponse

        if _refused(request):
            return JsonResponse({'code': 'invalid_input', 'message': 'Invalid characters in the request.'},
                                status=400)
        return self.get_response(request)


def _unstorable(text):
    """True for a string PostgreSQL cannot hold."""
    if '\x00' in text:
        return True
    try:
        text.encode('utf-8')
    except UnicodeEncodeError:
        return True
    return False


def _any_unstorable(querydict):
    return any(_unstorable(key) or any(_unstorable(value) for value in values)
               for key, values in querydict.lists())


def _refused(request):
    if _unstorable(request.path_info) or _any_unstorable(request.GET):
        return True
    # The session cookie is looked up in the database on every request, and
    # the CSRF token is compared against. Other cookies never reach a query -
    # one set by a neighbouring app on the domain must not lock anyone out.
    from django.conf import settings
    for name in (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
        if _unstorable(request.COOKIES.get(name, '')):
            return True
    content_type = request.content_type or ''
    if content_type == 'multipart/form-data':
        # The text fields reach views through request.POST (the NicePay
        # callback); the file parts go to upload handlers, never decoded
        # here, so a binary upload is unaffected. Reading POST consumes the
        # stream, after which request.body cannot be read - so a small body
        # is read first, for views that parse it as JSON whatever its type.
        # A large one (a backup) is left streaming, never held in memory.
        from django.http.multipartparser import MultiPartParserError
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            length = 0
        small = length <= (settings.DATA_UPLOAD_MAX_MEMORY_SIZE or 2621440)
        if small:
            request.body
        try:
            if _any_unstorable(request.POST):
                return True
        except MultiPartParserError:
            pass  # malformed: the view reports that itself
        if not small:
            return False
    elif content_type == 'application/x-www-form-urlencoded' and _any_unstorable(request.POST):
        return True
    # Whatever the declared type, the views may still read the body as JSON.
    body = request.body
    # Only a body that could decode to such text is parsed: an escape, a NUL
    # byte (also the mark of UTF-16/32 JSON), or 0xED, which leads a UTF-8
    # encoded surrogate. A base64 upload has none of them.
    if body and (b'\\u' in body or b'\x00' in body or b'\xed' in body):
        return _holds_unstorable(body)
    return False


def _holds_unstorable(body):
    """True when a JSON body decodes to an unstorable key or string."""
    import json

    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        return False  # not JSON we can read: the view reports that itself
    return holds_unstorable(data)


def holds_unstorable(data):
    """True when decoded JSON holds an unstorable key or string anywhere.

    Also used by apis.read_json on JSON a view decodes out of a field (event
    organizers, categories, languages), which this middleware sees only as
    text and does not decode a second time - text that looks like JSON is
    not, in any other field.
    """
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            if _unstorable(item):
                return True
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False

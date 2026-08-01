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

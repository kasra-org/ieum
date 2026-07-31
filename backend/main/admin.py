from django.contrib import admin, messages
from django.apps import apps

from .models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """Create, rotate and revoke API keys. Superusers only.

    The secret is shown exactly once — on creation or rotation — because only
    its hash is stored. If it is lost, rotate to issue a new one.

    Restricted to superusers rather than any `is_staff` user: a key can be bound
    to *any* account, so the ability to create one is the ability to act as that
    account. Leaving it at the default model permissions would let a staff user
    mint a key for a superuser and escalate.
    """
    list_display = ('name', 'user', 'prefix', 'created_at', 'last_used_at', 'revoked_at')
    list_filter = ('revoked_at',)
    search_fields = ('name', 'prefix', 'user__username', 'user__email')
    readonly_fields = ('prefix', 'created_at', 'last_used_at')
    fields = ('name', 'user', 'prefix', 'created_at', 'last_used_at', 'revoked_at')
    actions = ('rotate_keys', 'revoke_keys', 'unrevoke_keys')

    # --- superuser-only gate -------------------------------------------------
    # Covers the admin UI end to end: the changelist, the add/change forms, the
    # actions (which Django gates on has_change_permission), and the app index
    # entry. A non-superuser never sees API keys exist.

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        # Creating: mint the secret and surface it once.
        key, raw = ApiKey.generate(name=obj.name, user=obj.user)
        obj.pk = key.pk
        self._show_secret(request, key, raw)

    @admin.action(description="Rotate selected keys (issues a new secret)")
    def rotate_keys(self, request, queryset):
        for key in queryset:
            raw = key.rotate()
            self._show_secret(request, key, raw)

    @admin.action(description="Revoke selected keys")
    def revoke_keys(self, request, queryset):
        from django.utils import timezone
        n = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f"Revoked {n} key(s).", messages.WARNING)

    @admin.action(description="Un-revoke selected keys")
    def unrevoke_keys(self, request, queryset):
        n = queryset.filter(revoked_at__isnull=False).update(revoked_at=None)
        self.message_user(request, f"Re-enabled {n} key(s).", messages.INFO)

    def _show_secret(self, request, key, raw):
        self.message_user(
            request,
            f'API key for "{key.name}" — copy it now, it will not be shown again: {raw}',
            messages.SUCCESS,
        )


# Register every other model with the default admin.
for model in apps.get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass

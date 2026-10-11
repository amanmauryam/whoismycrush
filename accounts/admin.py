from django.contrib import admin

from .models import EmailVerification


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "verified_at", "sent_at", "created_at")
    list_filter = ("verified_at",)
    search_fields = ("user__email", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    actions = ["mark_verified_now"]

    @admin.action(description="Mark selected emails verified")
    def mark_verified_now(self, request, queryset):
        from django.utils import timezone

        queryset.filter(verified_at__isnull=True).update(verified_at=timezone.now())

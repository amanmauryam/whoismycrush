from django.conf import settings
from django.contrib import admin

from .emails import deliver_verification_email
from .models import EmailVerification


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "verified_at",
        "sent_at",
        "email_status",
        "email_attempts",
        "email_last_attempt_at",
        "created_at",
    )
    list_filter = ("verified_at", "email_status")
    search_fields = ("user__email", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = (
        "created_at",
        "email_status",
        "email_attempts",
        "email_last_error",
        "email_queued_at",
        "email_last_attempt_at",
    )
    actions = ["mark_verified_now", "retry_verification_email"]

    @admin.action(description="Mark selected emails verified")
    def mark_verified_now(self, request, queryset):
        from django.utils import timezone

        queryset.filter(verified_at__isnull=True).update(verified_at=timezone.now())

    @admin.action(description="Retry queued/failed verification emails")
    def retry_verification_email(self, request, queryset):
        attempts = getattr(settings, "VERIFICATION_EMAIL_MAX_ATTEMPTS", 5)
        candidates = queryset.filter(
            verified_at__isnull=True,
            email_status__in=[
                EmailVerification.EmailStatus.PENDING,
                EmailVerification.EmailStatus.FAILED,
                EmailVerification.EmailStatus.SENDING,
            ],
        ).filter(email_attempts__lt=attempts)
        sent = 0
        for record in candidates:
            if deliver_verification_email(record.pk, retry_stale=True):
                sent += 1
        self.message_user(request, f"{sent} verification email(s) sent.")

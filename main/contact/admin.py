from django.contrib import admin, messages

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "topic", "status", "created_at", "resolved_at")
    list_filter = ("status", "topic", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "topic", "message", "created_at", "resolved_at", "resolved_by")
    date_hierarchy = "created_at"
    actions = ["mark_resolved", "mark_pending"]

    fieldsets = (
        (None, {"fields": ("name", "email", "topic", "message", "created_at")}),
        ("Triage", {"fields": ("status", "resolved_at", "resolved_by")}),
    )

    def has_add_permission(self, request):
        # Messages arrive through the public form; staff may only triage them.
        return False

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            if obj.status == ContactMessage.Status.RESOLVED:
                obj.mark_resolved(request.user)
                return
            if obj.status == ContactMessage.Status.PENDING:
                obj.mark_pending()
                return
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark selected messages as resolved")
    def mark_resolved(self, request, queryset):
        count = 0
        for message_obj in queryset:
            message_obj.mark_resolved(request.user)
            count += 1
        self.message_user(request, f"{count} message(s) marked resolved.", level=messages.SUCCESS)

    @admin.action(description="Mark selected messages as pending")
    def mark_pending(self, request, queryset):
        count = queryset.update(
            status=ContactMessage.Status.PENDING,
            resolved_at=None,
            resolved_by=None,
        )
        self.message_user(request, f"{count} message(s) marked pending.", level=messages.SUCCESS)

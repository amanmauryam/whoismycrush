from django.contrib import admin, messages

from .models import (
    Block,
    College,
    CollegeInvite,
    CrushEntry,
    MutualMatch,
    Notification,
    PotentialMatch,
    Report,
    Rose,
    StudentProfile,
)
from .services import ApprovalError, approve_potential_match, reject_potential_match


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "state", "is_active", "created_at")
    list_filter = ("is_active", "state")
    search_fields = ("name", "city", "state", "domain")
    list_editable = ("is_active",)


class StudentProfileInline(admin.TabularInline):
    model = StudentProfile
    extra = 0
    fields = ("full_name", "roll_number", "course", "year", "is_verified")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "roll_number",
        "college",
        "course",
        "year",
        "is_verified",
    )
    list_filter = ("college", "course", "year", "gender", "is_verified")
    search_fields = ("full_name", "roll_number", "normalized_roll_number", "nickname")
    list_editable = ("is_verified",)
    autocomplete_fields = ("college",)


@admin.register(CrushEntry)
class CrushEntryAdmin(admin.ModelAdmin):
    """Admin sees priority; students never do (requirement 13 vs 16)."""

    list_display = (
        "id",
        "full_name",
        "college",
        "roll_number",
        "course",
        "year",
        "priority",
        "submitted_by",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "priority", "college", "course", "year")
    search_fields = (
        "full_name",
        "roll_number",
        "normalized_roll_number",
        "submitted_by__full_name",
    )
    autocomplete_fields = ("college", "submitted_by")
    readonly_fields = ("normalized_roll_number", "created_at")


@admin.register(MutualMatch)
class MutualMatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_a",
        "user_b",
        "status",
        "user_a_consented",
        "user_b_consented",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("user_a__full_name", "user_b__full_name")
    autocomplete_fields = ("user_a", "user_b")
    actions = ["close_matches"]

    @admin.action(description="Close selected matches")
    def close_matches(self, request, queryset):
        queryset.update(status=MutualMatch.Status.CLOSED)


@admin.register(PotentialMatch)
class PotentialMatchAdmin(admin.ModelAdmin):
    """Mandatory human verification gate (requirements 11/12/14/24/25).

    The Approve/Reject actions delegate to the exact same service functions the
    review-desk views use, so both paths share one code path and one audit
    trail.
    """

    list_display = (
        "id",
        "author",
        "registered_student",
        "confidence_score",
        "status",
        "is_reciprocal",
        "verified_by",
        "verified_at",
        "created_at",
    )
    list_filter = ("status", "confidence_score", "created_at")
    search_fields = (
        "crush_entry__full_name",
        "crush_entry__roll_number",
        "crush_entry__submitted_by__full_name",
        "registered_student__full_name",
    )
    autocomplete_fields = ("crush_entry", "registered_student", "mutual_match")
    readonly_fields = (
        "confidence_score",
        "match_reasons",
        "verified_at",
        "verified_by",
        "created_at",
    )
    actions = ["approve_selected", "reject_selected"]

    @admin.action(description="Approve selected (creates mutual crush + notifies)")
    def approve_selected(self, request, queryset):
        approved = skipped = 0
        for proposal in queryset:
            try:
                approve_potential_match(proposal, request.user)
            except ApprovalError:
                skipped += 1
            else:
                approved += 1
        self.message_user(
            request,
            f"{approved} approved, {skipped} skipped.",
            level=messages.SUCCESS if approved else messages.WARNING,
        )

    @admin.action(description="Reject selected (nobody is notified)")
    def reject_selected(self, request, queryset):
        rejected = skipped = 0
        for proposal in queryset:
            try:
                reject_potential_match(proposal, request.user)
            except ApprovalError:
                skipped += 1
            else:
                rejected += 1
        self.message_user(
            request,
            f"{rejected} rejected, {skipped} skipped.",
            level=messages.SUCCESS if rejected else messages.WARNING,
        )


@admin.register(Rose)
class RoseAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "sender", "receiver", "rose_type", "amount", "payment_status", "created_at")
    list_filter = ("rose_type", "payment_status")
    autocomplete_fields = ("match", "sender", "receiver")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__full_name", "blocked__full_name")
    autocomplete_fields = ("blocker", "blocked")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reported", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("reported__full_name",)
    autocomplete_fields = ("reporter", "reported")
    actions = ["mark_reviewed", "mark_dismissed"]

    @admin.action(description="Mark reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(status=Report.Status.REVIEWED)

    @admin.action(description="Dismiss")
    def mark_dismissed(self, request, queryset):
        queryset.update(status=Report.Status.DISMISSED)


@admin.register(CollegeInvite)
class CollegeInviteAdmin(admin.ModelAdmin):
    list_display = ("college", "email", "status", "created_at")
    list_filter = ("status",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("student", "kind", "message", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = ("student__full_name", "message")
    autocomplete_fields = ("student",)
    actions = ["mark_read"]

    @admin.action(description="Mark read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

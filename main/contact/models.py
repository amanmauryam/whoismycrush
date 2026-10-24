from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class ContactMessage(models.Model):
    """A message submitted through the public contact form.

    Messages are stored here instead of being emailed so nothing is lost to an
    SMTP outage. Staff triage them in the admin by flipping the status between
    pending and resolved.
    """

    class Topic(models.TextChoices):
        GENERAL = "general", "General question"
        PRIVACY = "privacy", "Privacy or data request"
        SAFETY = "safety", "Safety or abuse report"
        BUG = "bug", "Something is broken"
        PRESS = "press", "Press or partnership"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    topic = models.CharField(
        max_length=20,
        choices=Topic.choices,
        default=Topic.GENERAL,
    )
    message = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_contact_messages",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "contact message"
        verbose_name_plural = "contact messages"

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> - {self.get_topic_display()}"

    def mark_resolved(self, user=None) -> None:
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = user if getattr(user, "is_authenticated", False) else None
        self.save(update_fields=["status", "resolved_at", "resolved_by"])

    def mark_pending(self) -> None:
        self.status = self.Status.PENDING
        self.resolved_at = None
        self.resolved_by = None
        self.save(update_fields=["status", "resolved_at", "resolved_by"])

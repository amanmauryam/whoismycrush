"""Public-site forms (contact / general enquiries)."""

from __future__ import annotations

from django import forms
from django.db import models


class ContactForm(forms.Form):
    class Topic(models.TextChoices):
        GENERAL = "general", "General question"
        PRIVACY = "privacy", "Privacy or data request"
        SAFETY = "safety", "Safety or abuse report"
        BUG = "bug", "Something is broken"
        PRESS = "press", "Press or partnership"

    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "input", "autocomplete": "email", "inputmode": "email"}
        )
    )
    topic = forms.ChoiceField(choices=Topic.choices, widget=forms.Select(attrs={"class": "input"}))
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(
            attrs={"class": "input", "rows": "5", "placeholder": "How can we help?"}
        ),
    )
    #: A honeypot. Real people never fill this; bots usually do.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Spam detected.")
        return value

    def clean_message(self):
        return self.cleaned_data["message"].strip()

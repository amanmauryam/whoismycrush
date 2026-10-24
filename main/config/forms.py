"""Public-site forms (contact / general enquiries)."""

from __future__ import annotations

from django import forms

from contact.models import ContactMessage


class ContactForm(forms.ModelForm):
    #: A honeypot. Real people never fill this; bots usually do.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "topic", "message")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "autocomplete": "name"}),
            "email": forms.EmailInput(
                attrs={"class": "input", "autocomplete": "email", "inputmode": "email"}
            ),
            "topic": forms.Select(attrs={"class": "input"}),
            "message": forms.Textarea(
                attrs={"class": "input", "rows": "5", "placeholder": "How can we help?"}
            ),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Spam detected.")
        return value

    def clean_message(self):
        return self.cleaned_data["message"].strip()

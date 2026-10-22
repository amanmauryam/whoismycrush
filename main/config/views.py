from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from config import seo
from config.content import FAQ_GROUPS, faq_pairs
from config.forms import ContactForm
from config.mail import send_mail
from config.ratelimit import ratelimit

HOME = ("Home", "/")


class MarketingView(TemplateView):
    """Base for the public brochure pages.

    Each subclass declares its template, title, description and breadcrumb;
    everything else (canonical absolute URL, breadcrumb structured data) is
    derived, so metadata can never drift out of sync with the page name.
    """

    template_name = ""
    page_title = ""
    meta_description = ""
    breadcrumb_label = ""
    canonical_route = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ``reverse`` the route name to a canonical path so the tag in base.html
        # points at the real URL rather than a hand-typed string.
        from django.urls import reverse

        path = reverse(self.request.resolver_match.view_name)
        context["page_title"] = self.page_title
        context["meta_description"] = self.meta_description
        context["canonical_path"] = path
        context["structured_data"] = [
            seo.breadcrumb([HOME, (self.breadcrumb_label or self.page_title, path)])
        ]
        return context


class AboutView(MarketingView):
    template_name = "core/about.html"
    page_title = "About"
    breadcrumb_label = "About"
    meta_description = (
        "WhoIsMyCrush is a private college game. Secretly pick up to three "
        "people and we only tell you when it is mutual."
    )


class HowItWorksView(MarketingView):
    template_name = "core/how_it_works.html"
    page_title = "How it works"
    breadcrumb_label = "How it works"
    meta_description = (
        "Pick. Wait. Match. Three steps, and your list stays hidden the whole time."
    )


class SecretCrushView(MarketingView):
    template_name = "core/secret_crush.html"
    page_title = "Secret crush, explained"
    breadcrumb_label = "Secret crush"
    meta_description = (
        "What a secret crush is, and how WhoIsMyCrush keeps yours private: no "
        "search, no public list, and no notification until a match is mutual."
    )


class MutualCrushView(MarketingView):
    template_name = "core/mutual_crush.html"
    page_title = "Mutual crush, explained"
    breadcrumb_label = "Mutual crush"
    meta_description = (
        "A mutual crush means you both picked each other. Here is how a "
        "verified mutual crush works and why your identity stays hidden until "
        "you both choose to reveal."
    )


class CollegeCrushView(MarketingView):
    template_name = "core/college_crush.html"
    page_title = "College crush"
    breadcrumb_label = "College crush"
    meta_description = (
        "College crushes stay on campus. See how a campus-only crush platform "
        "makes a match mean more, and how to invite your college."
    )


class FAQView(MarketingView):
    template_name = "core/faq.html"
    page_title = "Frequently asked questions"
    breadcrumb_label = "FAQ"
    meta_description = (
        "Answers about secret crushes, privacy, verification, matching and "
        "optional roses on WhoIsMyCrush."
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["faq_groups"] = FAQ_GROUPS
        context["structured_data"] = context["structured_data"] + [seo.faq(faq_pairs())]
        return context


class SafetyView(MarketingView):
    template_name = "core/safety.html"
    page_title = "Safety guidelines"
    breadcrumb_label = "Safety"
    meta_description = (
        "How to stay safe and respectful on WhoIsMyCrush: reporting, blocking, "
        "consent and what we will never do with your data."
    )


class PrivacyPolicyView(MarketingView):
    template_name = "core/privacy_policy.html"
    page_title = "Privacy"
    breadcrumb_label = "Privacy"
    meta_description = (
        "Your crush list, your priorities, and everything else you pick stays private."
    )


class TermsView(MarketingView):
    template_name = "core/terms.html"
    page_title = "Terms of Service"
    breadcrumb_label = "Terms"
    meta_description = (
        "The rules for using WhoIsMyCrush, including the 18+ requirement, "
        "acceptable use and account deletion."
    )


@method_decorator(ratelimit(key="ip", rate="5/h"), name="post")
class ContactView(TemplateView):
    template_name = "core/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", ContactForm())
        context["page_title"] = "Contact"
        context["meta_description"] = (
            "Questions about privacy, safety or the product? Send us a note and "
            "we'll get back to you."
        )
        context["canonical_path"] = "/contact/"
        context["structured_data"] = [seo.breadcrumb([HOME, ("Contact", "/contact/")])]
        return context

    def post(self, request, *args, **kwargs):
        form = ContactForm(request.POST)
        if form.is_valid():
            self._deliver(form.cleaned_data)
            messages.success(
                request, "Thanks — your message is with us. We'll reply by email."
            )
            return redirect("core:contact")
        messages.error(request, "Please check the form and try again.")
        return self.render_to_response(self.get_context_data(form=form))

    def _deliver(self, data):
        to = getattr(settings, "CONTACT_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
        body = (
            f"Topic: {data['topic']}\n"
            f"From: {data['name']} <{data['email']}>\n\n"
            f"{data['message']}\n"
        )
        # Best-effort: a mail failure should not lose the user's submission or
        # show them an error they cannot act on. It is still logged, so a broken
        # mail server does not silently swallow every contact form message.
        send_mail(
            f"[WhoIsMyCrush] {data['topic']}",
            body,
            [to],
        )


def handler404(request, exception):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)


def handler403(request, exception):
    return render(request, "errors/403.html", status=403)

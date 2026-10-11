from django.shortcuts import render
from django.views.generic import TemplateView


class AboutView(TemplateView):
    template_name = "core/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "About"
        context["meta_description"] = (
            "WhoIsMyCrush is a private college game. Secretly pick up to three "
            "people and we only tell you when it is mutual."
        )
        return context


class HowItWorksView(TemplateView):
    template_name = "core/how_it_works.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "How it works"
        context["meta_description"] = (
            "Pick. Wait. Match. Three steps, and your list stays hidden the whole time."
        )
        return context


class PrivacyPolicyView(TemplateView):
    template_name = "core/privacy_policy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Privacy"
        context["meta_description"] = (
            "Your crush list, your priorities, and everything else you pick stays private."
        )
        return context


class TermsView(TemplateView):
    template_name = "core/terms.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Terms of Service"
        return context


def handler404(request, exception):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)


def handler403(request, exception):
    return render(request, "errors/403.html", status=403)
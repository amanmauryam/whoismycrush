from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from config import seo
from config.ratelimit import ratelimit

from .forms import (
    BlockForm,
    CampusChoiceForm,
    CampusIdForm,
    CampusSearchForm,
    CollegeCreateForm,
    CollegeInviteForm,
    CrushEntryForm,
    PotentialMatchNotesForm,
    ReportForm,
    RevealChoiceForm,
    StudentIdentityForm,
    active_entry_count,
    blocked_between,
    next_free_priority,
    remaining_slots,
)
from .matching import match_new_student, pending_pairs, unpaired_pending
from .models import (
    MAX_CRUSHES,
    Block,
    College,
    CollegeInvite,
    CrushEntry,
    MutualMatch,
    Notification,
    PotentialMatch,
    Report,
    StudentProfile,
)
from .services import (
    ApprovalError,
    SelectionError,
    approve_potential_match,
    campus_status,
    notify_reveal_pending,
    reconcile_all_matches,
    reject_potential_match,
    seal_secret,
)


def _student(user):
    return getattr(user, "student", None)


def student_required(view):
    """Everything past onboarding needs a campus identity."""

    @login_required
    def wrapper(request, *args, **kwargs):
        student = _student(request.user)
        if student is None:
            messages.info(request, "First, tell us which campus you're from.")
            return redirect("campus:campus_select")
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def _next_priority(student: StudentProfile) -> int:
    """Deprecated alias kept for template-facing call sites."""
    return next_free_priority(student)


def verifier_required(view):
    """Staff-only gate for the pending-match review desk (requirement 23).

    Uses the dedicated ``campus.verify_potentialmatch`` permission rather than
    blanket ``is_staff``, so an ordinary moderator can be granted exactly this
    one job and nothing else.
    """

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        allowed = user.is_superuser or (
            user.is_staff and user.has_perm("campus.verify_potentialmatch")
        )
        if not allowed:
            messages.error(request, "You are not allowed to review matches.")
            return redirect("campus:dashboard")
        return view(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------


class LandingView(TemplateView):
    template_name = "campus/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Who is your crush?",
                "meta_description": (
                    "Secretly pick up to 3 people from your college. "
                    "Nobody will know unless they picked you too."
                ),
                "canonical_path": "/",
                "campus_count": College.objects.filter(is_active=True).count(),
                "student_count": StudentProfile.objects.count(),
                "match_count": MutualMatch.objects.count(),
                "max_crushes": MAX_CRUSHES,
            }
        )
        return context


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


def _campus_next(request):
    """Send the student to the right next step after picking a campus."""

    if request.user.is_authenticated:
        return redirect("campus:identity")
    return redirect(f"{reverse('accounts:login')}?next={reverse('campus:identity')}")


def _campus_picker_context(request, *, choice_form=None, add_form=None):
    """Shared context for the campus picker, including manual-entry errors."""

    search_form = CampusSearchForm(request.GET or None)
    query = search_form.cleaned_data.get("q", "") if search_form.is_valid() else ""
    colleges = College.objects.filter(is_active=True)
    if query:
        colleges = colleges.filter(
            Q(name__icontains=query) | Q(city__icontains=query) | Q(state__icontains=query)
        )
    return {
        "search_form": search_form,
        "query": query,
        "colleges": colleges[:40],
        "result_count": colleges.count(),
        "selected": request.session.get("campus_id"),
        "choice_form": choice_form,
        "college_form": add_form or CollegeCreateForm(),
        "add_open": bool(add_form and add_form.errors),
        "page_title": "Which campus are you from?",
        "meta_description": (
            "Pick your campus so your crush list stays inside your college."
        ),
        "canonical_path": "/campus/",
        "step": 1,
    }


class CampusSelectView(TemplateView):
    """'Which campus are you from?' (design.md 14/35)."""

    template_name = "campus/campus_select.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and _student(request.user):
            return redirect("campus:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            **_campus_picker_context(self.request),
        }

    def post(self, request, *args, **kwargs):
        form = CampusChoiceForm(request.POST)
        if form.is_valid():
            request.session["campus_id"] = form.cleaned_data["college"].pk
            return _campus_next(request)
        context = self.get_context_data()
        context["choice_form"] = form
        return render(request, self.template_name, context)


@require_POST
@ratelimit(key="ip", rate="10/h")
def add_college(request):
    """Let a candidate add a college that is missing from the picker.

    India has thousands of institutions, so the list can never be complete.
    The first student to notice a gap types it in; the row is created active,
    de-duplicated case-insensitively, and shows up in every later search
    (requirements 5 / design.md 14).
    """

    form = CollegeCreateForm(request.POST)
    if not form.is_valid():
        context = _campus_picker_context(request, add_form=form)
        return render(request, "campus/campus_select.html", context)

    name = form.cleaned_data["name"]
    college = College.objects.filter(name__iexact=name).first()
    if college is None:
        try:
            college = College.objects.create(
                name=name,
                city=form.cleaned_data.get("city", ""),
                state=form.cleaned_data.get("state", ""),
            )
        except IntegrityError:
            # Another candidate added the same name a moment ago.
            college = College.objects.filter(name__iexact=name).first()

    if college is not None:
        # Fill in a detail the original submitter skipped, never overwrite.
        updates = {}
        if not college.city and form.cleaned_data.get("city"):
            updates["city"] = form.cleaned_data["city"]
        if not college.state and form.cleaned_data.get("state"):
            updates["state"] = form.cleaned_data["state"]
        if updates:
            for field, value in updates.items():
                setattr(college, field, value)
            college.save(update_fields=list(updates))

    if college is None:
        messages.error(request, "Could not add that college. Try a different name.")
        return redirect("campus:campus_select")

    request.session["campus_id"] = college.pk
    messages.success(
        request,
        f"{college.name} is on the list now. Other students can find it too.",
    )
    return _campus_next(request)


@login_required
def identity(request):
    """FULL NAME / ROLL NUMBER / COURSE / YEAR / SECTION (design.md 15)."""

    existing = _student(request.user)
    if existing:
        return redirect("campus:dashboard")

    college = College.objects.filter(pk=request.session.get("campus_id")).first()
    if college is None:
        messages.info(request, "Pick your campus first.")
        return redirect("campus:campus_select")

    if request.method == "POST":
        form = StudentIdentityForm(request.POST, user=request.user, college=college)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.college = college
            profile.save()
            request.session.pop("campus_id", None)
            # A brand-new student may already have been typed in by someone
            # else. Matching only ever creates pending proposals -- no
            # notification is sent here (requirements 8/17).
            match_new_student(profile)
            messages.success(
                request, "Campus ID ready. Now tell us who your secret crush is."
            )
            return redirect("campus:secret")
    else:
        form = StudentIdentityForm(user=request.user, college=college)

    return render(
        request,
        "campus/identity.html",
        {
            "form": form,
            "college": college,
            "page_title": "Your campus ID",
            "meta_description": "Just enough information to find the right person.",
            "canonical_path": "/identity/",
            "step": 2,
        },
    )


# ---------------------------------------------------------------------------
# Secret desk
# ---------------------------------------------------------------------------


@student_required
def secret_desk(request):
    """Three private slots, each filled in by hand. No search anywhere.

    There is deliberately no student lookup here: a crush does not need an
    account, and searching for people is exactly the behaviour that let
    strangers appear in your list without consent (requirements 1/2/21).
    """

    student = _student(request.user)
    entries = list(
        CrushEntry.objects.for_student(student).order_by("priority", "created_at")
    )
    by_priority = {e.priority: e for e in entries}
    next_slot = next_free_priority(student)
    slots_left = remaining_slots(student)

    slots = []
    for index in range(1, MAX_CRUSHES + 1):
        entry = by_priority.get(index)
        if entry is not None:
            form = CrushEntryForm(
                instance=entry, author=student, priority=index, prefix=f"crush{index}"
            )
        else:
            form = CrushEntryForm(
                author=student, priority=index, prefix=f"crush{index}"
            )
        slots.append(
            {
                "index": index,
                "entry": entry,
                "form": form,
                "open": entry is None and index == next_slot,
            }
        )

    return render(
        request,
        "campus/secret.html",
        {
            "student": student,
            "slots": slots,
            "next_slot": next_slot,
            "entry_count": len(entries),
            "slots_left": slots_left,
            "can_seal": bool(entries),
            "max_crushes": MAX_CRUSHES,
            "page_title": "Who is your secret crush?",
            "meta_description": (
                "Enter up to 3 crushes by hand. They don't need an account, "
                "and nobody is told."
            ),
            "canonical_path": "/secret/",
            "nav_secret": True,
        },
    )


@student_required
@require_POST
@ratelimit(key="user", rate="30/h")
def add_crush(request, slot=None):
    """Save one slot from the typed form. The crush need not be registered."""

    student = _student(request.user)
    if slot is None:
        slot = next_free_priority(student)

    if CrushEntry.objects.active().filter(submitted_by=student, priority=slot).exists():
        messages.info(request, f"Crush #{slot} is already saved. Remove it first.")
        return redirect("campus:secret")
    if remaining_slots(student) <= 0:
        messages.error(request, f"You can only enter {MAX_CRUSHES} people.")
        return redirect("campus:secret")

    form = CrushEntryForm(
        request.POST, author=student, priority=slot, prefix=f"crush{slot}"
    )
    if not form.is_valid():
        # Re-render the desk with the user's input intact rather than silently
        # dropping what they typed.
        messages.error(request, "Check the highlighted fields and try again.")
        return _secret_with_errors(request, student, slot, form)

    form.save()
    messages.success(request, f"Crush #{slot} saved. Still completely secret.")
    return redirect("campus:secret")


@student_required
@require_POST
@ratelimit(key="user", rate="60/h")
def edit_crush(request, pk):
    """Update a saved slot in place, keeping its priority."""

    student = _student(request.user)
    entry = get_object_or_404(
        CrushEntry.objects.active(), pk=pk, submitted_by=student
    )
    form = CrushEntryForm(
        request.POST,
        instance=entry,
        author=student,
        priority=entry.priority,
        prefix=f"crush{entry.priority}",
    )
    if not form.is_valid():
        messages.error(request, "Check the highlighted fields and try again.")
        return _secret_with_errors(request, student, entry.priority, form, entry=entry)

    form.save()
    messages.success(request, f"Crush #{entry.priority} updated.")
    return redirect("campus:secret")


@student_required
@require_POST
def remove_crush(request, pk):
    """Soft-delete one slot. Scoped to the owner, so ids are not guessable."""

    student = _student(request.user)
    entry = get_object_or_404(
        CrushEntry.objects.active(), pk=pk, submitted_by=student
    )
    slot = entry.priority
    entry.is_active = False
    entry.save(update_fields=["is_active"])
    messages.success(request, f"Crush #{slot} removed.")
    return redirect("campus:secret")


def _secret_with_errors(request, student, slot, form, entry=None):
    """Re-render the desk after a validation failure, keeping typed values."""

    entries = list(
        CrushEntry.objects.for_student(student).order_by("priority", "created_at")
    )
    by_priority = {e.priority: e for e in entries}
    next_slot = next_free_priority(student)

    slots = []
    for index in range(1, MAX_CRUSHES + 1):
        existing = by_priority.get(index)
        if index == slot:
            slot_form = form
        elif existing is not None:
            slot_form = CrushEntryForm(
                instance=existing,
                author=student,
                priority=index,
                prefix=f"crush{index}",
            )
        else:
            slot_form = CrushEntryForm(
                author=student, priority=index, prefix=f"crush{index}"
            )
        slots.append(
            {
                "index": index,
                "entry": existing,
                "form": slot_form,
                "open": existing is None and (index == slot or index == next_slot),
            }
        )

    return render(
        request,
        "campus/secret.html",
        {
            "student": student,
            "slots": slots,
            "next_slot": next_slot,
            "entry_count": len(entries),
            "slots_left": remaining_slots(student),
            "can_seal": bool(entries),
            "max_crushes": MAX_CRUSHES,
            "page_title": "Who is your secret crush?",
            "canonical_path": "/secret/",
            "nav_secret": True,
        },
    )


@student_required
def seal_secret_view(request):
    """'YOUR SECRET IS LOCKED' -> SEALED. Silent. (design.md 22, req 22/26)

    Sealing never tells anyone anything. It only asks the matcher whether any
    registered student lines up with what was typed; every hit waits for an
    admin (requirements 6/10/17).
    """

    student = _student(request.user)
    if request.method == "POST":
        try:
            proposals = seal_secret(student)
        except SelectionError as exc:
            messages.error(request, str(exc))
            return redirect("campus:secret")
        return render(
            request,
            "campus/sealed.html",
            {
                "count": active_entry_count(student),
                "pending_review": proposals,
                "page_title": "Sealed",
                "meta_description": "Your list is locked away.",
                "canonical_path": "/secret/seal/",
                "nav_secret": True,
            },
        )

    count = active_entry_count(student)
    if not count:
        messages.info(request, "Enter at least one crush before sealing your list.")
        return redirect("campus:secret")
    return render(
        request,
        "campus/seal_confirm.html",
        {
            "count": count,
            "student": student,
            "page_title": "Lock my crushes",
            "meta_description": "Nobody can read or change your list after this.",
            "canonical_path": "/secret/seal/",
            "nav_secret": True,
        },
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@student_required
def dashboard(request):
    student = _student(request.user)
    status = campus_status(student)
    recent = MutualMatch.objects.with_counterpart(student).filter(
        Q(user_a=student) | Q(user_b=student)
    )[:5]

    hour = timezone.localtime().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    return render(
        request,
        "campus/dashboard.html",
        {
            "student": student,
            "status": status,
            "matches": recent,
            "has_matches": recent.exists(),
            "greeting": f"{greeting}, {student.full_name.split(' ')[0]}.",
            "sealed": status["sealed"] > 0,
            "page_title": "My secret desk",
            "canonical_path": "/desk/",
            "nav_secret": True,
        },
    )


# ---------------------------------------------------------------------------
# Matches + reveal
# ---------------------------------------------------------------------------


@student_required
def matches(request):
    student = _student(request.user)
    # The counterpart is resolved server-side; the template never gets a
    # method call with arguments, and never sees a priority.
    rows = [
        {"match": match, "other": match.other(student)}
        for match in MutualMatch.objects.with_counterpart(student).filter(
            Q(user_a=student) | Q(user_b=student)
        )
    ]
    return render(
        request,
        "campus/matches.html",
        {
            "student": student,
            "rows": rows,
            "has_matches": bool(rows),
            "page_title": "Matches",
            "canonical_path": "/matches/",
            "nav_matches": True,
        },
    )


@student_required
def match_detail(request, pk):
    student = _student(request.user)
    # Scoped to the caller: a match id is never a way into someone else's data.
    match = get_object_or_404(
        MutualMatch.objects.with_counterpart(student),
        Q(user_a=student) | Q(user_b=student),
        pk=pk,
    )
    match.sync_status()
    other = match.other(student)
    return render(
        request,
        "campus/match_detail.html",
        {
            "student": student,
            "match": match,
            "other": other,
            "revealed": match.status == MutualMatch.Status.REVEALED,
            "i_consented": match.has_consented(student),
            "page_title": "Mutual crush",
            "canonical_path": f"/matches/{match.pk}/",
            "nav_matches": True,
        },
    )


@student_required
@require_POST
@ratelimit(key="user", rate="40/h")
def reveal_choice(request, pk):
    student = _student(request.user)
    match = get_object_or_404(MutualMatch, pk=pk)
    if student.pk not in {match.user_a_id, match.user_b_id}:
        messages.error(request, "That match is not yours.")
        return redirect("campus:matches")

    form = RevealChoiceForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Pick an option.")
        return redirect("campus:match_detail", pk=match.pk)

    if form.cleaned_data["choice"] == "reveal":
        if not match.has_consented(student):
            match.record_consent(student)
            match.sync_status(save=False)
            match.save()
            if match.status != MutualMatch.Status.REVEALED:
                notify_reveal_pending(match, match.other(student))
        return redirect("campus:match_detail", pk=match.pk)

    match.status = MutualMatch.Status.CLOSED
    match.save(update_fields=["status"])
    messages.success(request, "You stayed anonymous. Your secret is still safe.")
    return redirect("campus:matches")


# ---------------------------------------------------------------------------
# Campus ID + privacy center
# ---------------------------------------------------------------------------


@student_required
def campus_id(request):
    student = _student(request.user)
    if request.method == "POST":
        form = CampusIdForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Campus ID updated.")
            return redirect("campus:campus_id")
    else:
        form = CampusIdForm(instance=student)

    return render(
        request,
        "campus/campus_id.html",
        {
            "student": student,
            "form": form,
            "entry_count": active_entry_count(student),
            "match_count": MutualMatch.objects.for_student(student).count(),
            "page_title": "My campus ID",
            "meta_description": "Your private campus identity.",
            "canonical_path": "/campus-id/",
            "nav_account": True,
        },
    )


@student_required
def privacy(request):
    student = _student(request.user)
    return render(
        request,
        "campus/privacy.html",
        {
            "student": student,
            "entry_count": active_entry_count(student),
            "match_count": MutualMatch.objects.for_student(student).count(),
            "page_title": "Privacy center",
            "canonical_path": "/privacy/",
            "nav_account": True,
        },
    )


@student_required
@require_POST
def delete_crushes(request):
    student = _student(request.user)
    count = active_entry_count(student)
    with transaction.atomic():
        CrushEntry.objects.filter(submitted_by=student, is_active=True).update(
            is_active=False
        )
    messages.success(request, f"{count} secret crush(es) deleted.")
    return redirect("campus:dashboard")


@student_required
@require_POST
def delete_account(request):
    student = _student(request.user)
    user = request.user
    student.delete()
    user.delete()
    messages.success(request, "Your account and campus ID are gone.")
    return redirect("campus:landing")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@student_required
def notification_list(request):
    student = _student(request.user)
    return render(
        request,
        "campus/notifications.html",
        {
            "student": student,
            "notifications": student.notifications.all()[:60],
            "unread": student.notifications.filter(is_read=False).count(),
            "page_title": "Notifications",
            "canonical_path": "/notifications/",
        },
    )


@student_required
@require_POST
def mark_read(request, pk=None):
    student = _student(request.user)
    queryset = student.notifications.all()
    if pk is not None:
        queryset = queryset.filter(pk=pk)
    queryset.update(is_read=True)
    return redirect(request.POST.get("next") or "campus:notifications")


# ---------------------------------------------------------------------------
# Invite / report / block
# ---------------------------------------------------------------------------


class InviteCollegeView(TemplateView):
    """'Can't find them? Invite your college.' (design.md 19/46)"""

    template_name = "campus/invite.html"

    def get_context_data(self, **kwargs):
        student = _student(self.request.user)
        return {
            **super().get_context_data(**kwargs),
            "form": CollegeInviteForm(),
            "student": student,
            "college": student.college if student else None,
            "page_title": "Invite your campus",
            "canonical_path": "/invite/",
        }

    def post(self, request, *args, **kwargs):
        student = _student(request.user)
        if student is None:
            messages.error(request, "Join a campus before inviting.")
            return redirect("campus:landing")
        form = CollegeInviteForm(request.POST)
        if form.is_valid():
            CollegeInvite.objects.get_or_create(
                college=student.college,
                email=form.cleaned_data.get("email") or "",
            )
            messages.success(request, "Thanks. We'll nudge your campus.")
            return redirect("campus:secret")
        context = self.get_context_data()
        context["form"] = form
        return render(request, self.template_name, context)


class CollegeLandingView(TemplateView):
    """Public, shareable page for one campus (growth).

    Deliberately not a directory: it shows the college name and how many
    students have joined, but never a list of people. Thin campuses are
    marked ``noindex`` so search engines are not fed near-empty pages that
    would also leak campus names (design.md 54).
    """

    template_name = "campus/college_landing.html"

    def get_context_data(self, **kwargs):
        college = get_object_or_404(
            College, slug=self.kwargs["slug"], is_active=True
        )
        count = college.student_count()
        return {
            **super().get_context_data(**kwargs),
            "college": college,
            "member_count": count,
            "can_index": count >= 5,
            "page_title": f"Secret crushes at {college.name}",
            "meta_description": (
                f"Join {college.display_name} on WhoIsMyCrush. Add your secret "
                "crushes privately and only find out when it is mutual."
            ),
            "canonical_path": college.get_absolute_url(),
            "structured_data": [
                seo.breadcrumb(
                    [("Home", "/"), (college.name, college.get_absolute_url())]
                )
            ],
        }


def join_college(request, slug):
    """Shareable invite link: preselect a campus, then start onboarding."""

    college = get_object_or_404(College, slug=slug, is_active=True)
    request.session["campus_id"] = college.pk
    if request.user.is_authenticated:
        if _student(request.user) is None:
            return redirect("campus:identity")
        return redirect("campus:dashboard")
    messages.info(request, f"Create your profile to join {college.name}.")
    return redirect("accounts:register")


@student_required
@require_POST
@ratelimit(key="user", rate="20/h")
def report_student(request, pk):
    student = _student(request.user)
    reported = get_object_or_404(StudentProfile, pk=pk, college=student.college)
    fallback = request.POST.get("next") or "campus:matches"
    if reported.pk == student.pk:
        messages.error(request, "You can't report yourself.")
        return redirect(fallback)
    form = ReportForm(request.POST)
    if form.is_valid():
        Report.objects.create(reporter=student, reported=reported, **form.cleaned_data)
        messages.success(request, "Reported. Our team will take a look.")
    else:
        messages.error(request, "Pick a reason before reporting.")
    return redirect(fallback)


@student_required
@require_POST
@ratelimit(key="user", rate="20/h")
def block_student(request, pk):
    student = _student(request.user)
    blocked = get_object_or_404(StudentProfile, pk=pk, college=student.college)
    fallback = request.POST.get("next") or "campus:matches"
    if blocked.pk == student.pk:
        messages.error(request, "You can't block yourself.")
        return redirect(fallback)
    if not BlockForm(request.POST).is_valid():
        messages.error(request, "Confirm the block first.")
        return redirect(fallback)

    with transaction.atomic():
        Block.objects.get_or_create(blocker=student, blocked=blocked)
        # Entries are typed by hand, so "blocking" means retiring any entry the
        # blocker wrote that happens to describe the blocked person, and
        # killing pending proposals in both directions (requirements 17/18).
        blocked_roll = blocked.normalized_roll_number
        CrushEntry.objects.filter(
            submitted_by=student,
            college_id=blocked.college_id,
            normalized_roll_number=blocked_roll,
            is_active=True,
        ).update(is_active=False)
        PotentialMatch.objects.filter(
            Q(crush_entry__submitted_by=student, registered_student=blocked)
            | Q(crush_entry__submitted_by=blocked, registered_student=student)
        ).delete()
        MutualMatch.objects.filter(
            Q(user_a=student, user_b=blocked) | Q(user_a=blocked, user_b=student)
        ).update(status=MutualMatch.Status.CLOSED)
    messages.success(request, "Blocked. Your lists were cleaned up.")
    return redirect("campus:matches")


@login_required
@require_POST
def reconcile(request):
    """Staff maintenance sweep: re-run the matcher over every active entry."""

    if not request.user.is_staff:
        messages.error(request, "Staff only.")
        return redirect("campus:dashboard")
    made = reconcile_all_matches()
    messages.success(request, f"{made} new proposal(s) queued for review.")
    return redirect("campus:pending_matches")


# ---------------------------------------------------------------------------
# Staff: pending crush matches (requirements 10/11/12/14/24/25)
# ---------------------------------------------------------------------------


@verifier_required
def pending_matches(request):
    """"PENDING CRUSH MATCHES" review desk.

    Only reciprocal pairs show up here, because a one-sided entry can never
    become a mutual crush. Confidence is advisory: nothing auto-approves
    (requirements 10/11/18).
    """

    pairs = pending_pairs()
    approved = PotentialMatch.objects.approved().for_review()[:20]
    rejected = PotentialMatch.objects.filter(
        status=PotentialMatch.Status.REJECTED
    ).for_review()[:20]

    return render(
        request,
        "campus/pending_matches.html",
        {
            "pairs": pairs,
            "pair_count": len(pairs),
            "unpaired": unpaired_pending(),
            "recently_approved": approved,
            "recently_rejected": rejected,
            "page_title": "Pending crush matches",
            "canonical_path": "/staff/matches/",
        },
    )


@verifier_required
def pending_match_detail(request, pk):
    """Side-by-side comparison for one pending proposal (requirement 12)."""

    proposal = get_object_or_404(PotentialMatch.objects.for_review(), pk=pk)
    partner = proposal.reciprocal
    return render(
        request,
        "campus/pending_match_detail.html",
        {
            "proposal": proposal,
            "partner": partner,
            "notes_form": PotentialMatchNotesForm(),
            "page_title": f"Match review #{proposal.pk}",
            "canonical_path": f"/staff/matches/{proposal.pk}/",
        },
    )


@verifier_required
@require_POST
def approve_match(request, pk):
    """APPROVE MATCH -> real mutual crush + notifications (requirement 14)."""

    proposal = get_object_or_404(PotentialMatch.objects.for_review(), pk=pk)
    notes = PotentialMatchNotesForm(request.POST).cleaned_data.get("admin_notes", "")
    try:
        match = approve_potential_match(proposal, request.user, admin_notes=notes)
    except ApprovalError as exc:
        messages.error(request, str(exc))
        return redirect("campus:pending_match_detail", pk=proposal.pk)
    messages.success(
        request,
        f"Match #{match.pk} approved. Both students have been notified.",
    )
    return redirect("campus:pending_matches")


@verifier_required
@require_POST
def reject_match(request, pk):
    """REJECT MATCH -> pair closed, nobody notified."""

    proposal = get_object_or_404(PotentialMatch.objects.for_review(), pk=pk)
    notes = PotentialMatchNotesForm(request.POST).cleaned_data.get("admin_notes", "")
    try:
        reject_potential_match(proposal, request.user, admin_notes=notes)
    except ApprovalError as exc:
        messages.error(request, str(exc))
        return redirect("campus:pending_match_detail", pk=proposal.pk)
    messages.success(request, "Match rejected. Neither student was contacted.")
    return redirect("campus:pending_matches")
from django.urls import path

from . import views

app_name = "campus"

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    # onboarding
    path("campus/", views.CampusSelectView.as_view(), name="campus_select"),
    path("campus/add/", views.add_college, name="add_college"),
    path("identity/", views.identity, name="identity"),
    # secret desk
    path("secret/", views.secret_desk, name="secret"),
    path("secret/add/", views.add_crush, name="add_crush"),
    path("secret/add/<int:slot>/", views.add_crush, name="add_crush_slot"),
    path("secret/edit/<int:pk>/", views.edit_crush, name="edit_crush"),
    path("secret/remove/<int:pk>/", views.remove_crush, name="remove_crush"),
    path("secret/seal/", views.seal_secret_view, name="seal"),
    # dashboard + matches
    path("desk/", views.dashboard, name="dashboard"),
    path("matches/", views.matches, name="matches"),
    path("matches/<int:pk>/", views.match_detail, name="match_detail"),
    path("matches/<int:pk>/reveal/", views.reveal_choice, name="reveal"),
    # identity + privacy
    path("campus-id/", views.campus_id, name="campus_id"),
    path("privacy/", views.privacy, name="privacy"),
    path("privacy/delete-crushes/", views.delete_crushes, name="delete_crushes"),
    path("privacy/delete-account/", views.delete_account, name="delete_account"),
    # staff: pending crush match verification
    path("staff/matches/", views.pending_matches, name="pending_matches"),
    path(
        "staff/matches/<int:pk>/",
        views.pending_match_detail,
        name="pending_match_detail",
    ),
    path(
        "staff/matches/<int:pk>/approve/",
        views.approve_match,
        name="approve_match",
    ),
    path(
        "staff/matches/<int:pk>/reject/",
        views.reject_match,
        name="reject_match",
    ),
    # staff: separate ambiguous identity review desk
    path("staff/identities/", views.identity_review, name="identity_review"),
    path(
        "staff/identities/<int:pk>/",
        views.identity_review_detail,
        name="identity_review_detail",
    ),
    path(
        "staff/identities/<int:pk>/<str:action>/",
        views.identity_entry_action,
        name="identity_entry_action",
    ),
    path(
        "staff/identities/candidate/<int:pk>/<str:action>/",
        views.identity_candidate_action,
        name="identity_candidate_action",
    ),
    # notifications
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/read/", views.mark_read, name="mark_all_read"),
    path("notifications/<int:pk>/read/", views.mark_read, name="mark_read"),
    # safety + growth
    path("college/<slug:slug>/", views.CollegeLandingView.as_view(), name="college_landing"),
    path("join/<slug:slug>/", views.join_college, name="join"),
    path("invite/", views.InviteCollegeView.as_view(), name="invite"),
    path("report/<int:pk>/", views.report_student, name="report"),
    path("block/<int:pk>/", views.block_student, name="block"),
    path("reconcile/", views.reconcile, name="reconcile"),
]
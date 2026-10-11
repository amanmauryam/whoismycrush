from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.AccountLoginView.as_view(), name="login"),
    path("logout/", views.AccountLogoutView.as_view(), name="logout"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path(
        "forgot-password/sent/",
        views.ForgotPasswordDoneView.as_view(),
        name="forgot_password_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        views.ResetPasswordConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        views.ResetPasswordCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # email verification
    path(
        "verify-email/",
        views.verify_email_notice,
        name="verify_email_notice",
    ),
    path(
        "verify-email/resend/",
        views.resend_verification,
        name="resend_verification",
    ),
    path(
        "verify-email/<uidb64>/<token>/",
        views.verify_email,
        name="verify_email",
    ),
]
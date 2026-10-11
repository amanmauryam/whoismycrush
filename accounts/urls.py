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
]
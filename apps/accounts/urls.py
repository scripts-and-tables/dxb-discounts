from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views


app_name = "accounts"

urlpatterns = [
    # Signup + 2FA verify
    path("signup/", views.signup, name="signup"),
    path("signup/verify/", views.signup_verify, name="signup_verify"),
    path("signup/resend/", views.signup_resend, name="signup_resend"),

    # Login + 2FA verify
    path("login/", views.login_view, name="login"),
    path("login/verify/", views.login_verify, name="login_verify"),
    path("login/resend/", views.login_resend, name="login_resend"),

    # Logout
    path("logout/", views.logout_view, name="logout"),

    # Profile
    path("profile/", views.profile, name="profile"),

    # Favorite toggle (HTMX-friendly)
    path("favorites/<slug:slug>/toggle/", views.favorite_toggle, name="favorite_toggle"),

    # Gem toggle (admin-only, HTMX-friendly)
    path("gems/<slug:slug>/toggle/", views.gem_toggle, name="gem_toggle"),

    # Password reset (Django built-ins, our templates)
    path(
        "password/reset/",
        views.RateLimitedPasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]

import logging

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .emails import EmailDeliveryFailed, _notify_admin_send_failure


logger = logging.getLogger("apps.accounts.emails")
User = get_user_model()


class SignupForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "field", "autocomplete": "email", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "field", "autocomplete": "new-password", "placeholder": "Choose a strong password"}),
        min_length=8,
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with that email already exists. Try logging in.")
        return email

    def clean_password(self):
        pw = self.cleaned_data["password"]
        validate_password(pw)
        return pw


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "field", "autocomplete": "email", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "field", "autocomplete": "current-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        password = cleaned.get("password") or ""
        if email and password:
            user = authenticate(username=email, password=password)
            if user is None:
                raise ValidationError("That email and password don't match an account.")
            if not user.is_active:
                raise ValidationError("This account is inactive.")
            cleaned["user"] = user
        return cleaned


class PasswordResetForm(DjangoPasswordResetForm):
    """Wrap Django's send_mail so a Resend rejection lands in admin alerts + logs
    instead of 500-ing the request."""

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        try:
            super().send_mail(
                subject_template_name, email_template_name, context,
                from_email, to_email, html_email_template_name=html_email_template_name,
            )
        except Exception as exc:
            logger.exception("password_reset send_mail failed: to=%s", to_email)
            _notify_admin_send_failure(to_email=to_email, purpose="password reset", exc=exc)
            raise EmailDeliveryFailed(str(exc)) from exc


class CodeForm(forms.Form):
    code = forms.CharField(
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "class": "field text-center tracking-[0.5em] text-2xl font-mono",
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]{6}",
            "placeholder": "000000",
        }),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise ValidationError("Codes are 6 digits.")
        return code

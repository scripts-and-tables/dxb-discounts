import logging

from django.conf import settings
from django.core.mail import mail_admins, send_mail


logger = logging.getLogger(__name__)


class EmailDeliveryFailed(Exception):
    """Raised when the underlying email backend rejects or fails the send."""


def send_code_email(*, to_email: str, code: str, purpose: str) -> None:
    if purpose == "signup":
        subject = f"Verify your DXB Discounts email — {code}"
        intro = "Welcome to DXB Discounts. Use the code below to verify your email."
    else:
        subject = f"Your DXB Discounts login code — {code}"
        intro = "Use the code below to finish signing in."

    body = (
        f"{intro}\n\n"
        f"    {code}\n\n"
        f"This code expires in 10 minutes. If you didn't request it, ignore this email."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception(
            "send_code_email failed: to=%s purpose=%s from=%s",
            to_email, purpose, settings.DEFAULT_FROM_EMAIL,
        )
        _notify_admin_send_failure(to_email=to_email, purpose=purpose, exc=exc)
        raise EmailDeliveryFailed(str(exc)) from exc


def _notify_admin_send_failure(*, to_email: str, purpose: str, exc: Exception) -> None:
    subject = f"[DXB Discounts] {purpose} email failed for {to_email}"
    body = (
        f"A {purpose} verification email failed to send.\n\n"
        f"Recipient: {to_email}\n"
        f"From:      {settings.DEFAULT_FROM_EMAIL}\n"
        f"Backend:   {settings.EMAIL_BACKEND}\n"
        f"Error:     {exc.__class__.__name__}: {exc}\n"
    )
    mail_admins(subject=subject, message=body, fail_silently=True)

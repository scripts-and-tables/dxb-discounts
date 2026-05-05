from django.conf import settings
from django.core.mail import send_mail


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
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )

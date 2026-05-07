import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


CODE_LIFETIME = timedelta(minutes=10)
CODE_ISSUE_WINDOW = timedelta(hours=1)
CODE_ISSUE_MAX_PER_WINDOW = 8


class CodeRateLimitExceeded(Exception):
    """Raised when too many EmailCodes have been issued for a (user, purpose) recently."""


class EmailCodePurpose(models.TextChoices):
    SIGNUP = "signup", "Verify signup email"
    LOGIN = "login", "2FA login code"


class EmailCodeQuerySet(models.QuerySet):
    def valid(self):
        return self.filter(used_at__isnull=True, expires_at__gte=timezone.now())


def _generate_numeric_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class EmailCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_codes",
    )
    purpose = models.CharField(max_length=10, choices=EmailCodePurpose.choices)
    code = models.CharField(max_length=6)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EmailCodeQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_purpose_display()} for {self.user_id}"

    @classmethod
    def issue(cls, user, purpose: str) -> "EmailCode":
        recent = cls.objects.filter(
            user=user,
            purpose=purpose,
            created_at__gte=timezone.now() - CODE_ISSUE_WINDOW,
        ).count()
        if recent >= CODE_ISSUE_MAX_PER_WINDOW:
            raise CodeRateLimitExceeded
        # Invalidate any prior outstanding codes for this user+purpose.
        cls.objects.filter(
            user=user, purpose=purpose, used_at__isnull=True
        ).update(used_at=timezone.now())
        return cls.objects.create(
            user=user,
            purpose=purpose,
            code=_generate_numeric_code(),
            expires_at=timezone.now() + CODE_LIFETIME,
        )

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    discount = models.ForeignKey(
        "discounts.Discount",
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "discount"], name="favorite_unique_user_discount"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user_id} ♥ {self.discount_id}"

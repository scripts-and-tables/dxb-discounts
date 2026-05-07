from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import EmailCode, EmailCodePurpose

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthBaseTest(TestCase):
    def setUp(self):
        # django-ratelimit stores counters in Django's cache; reset between tests.
        cache.clear()
        # Site framework caches the current Site by id; reset so per-test domain
        # changes are picked up.
        Site.objects.clear_cache()


class PasswordResetEmailTests(AuthBaseTest):
    def test_email_link_uses_configured_site_domain_not_example_com(self):
        # Regression for the bug that motivated this audit: reset emails were
        # going out with the Django default 'example.com' domain.
        User.objects.create_user(
            username="alice@example.com", email="alice@example.com", password="rosebud-spaniel-7"
        )
        Site.objects.update_or_create(
            pk=1, defaults={"domain": "test.dxbdiscounts.com", "name": "DXB Discounts"}
        )
        Site.objects.clear_cache()

        resp = self.client.post(
            reverse("accounts:password_reset"), {"email": "alice@example.com"}
        )
        self.assertRedirects(resp, reverse("accounts:password_reset_done"))

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("test.dxbdiscounts.com/accounts/password/reset/", body)
        self.assertNotIn("example.com", body)


class SignupTests(AuthBaseTest):
    def test_happy_path_creates_user_and_logs_in_after_code(self):
        resp = self.client.post(
            reverse("accounts:signup"),
            {"email": "alice@example.com", "password": "rosebud-spaniel-7"},
        )
        self.assertRedirects(resp, reverse("accounts:signup_verify"))

        user = User.objects.get(email="alice@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)

        code_obj = EmailCode.objects.filter(
            user=user, purpose=EmailCodePurpose.SIGNUP, used_at__isnull=True
        ).first()
        self.assertIsNotNone(code_obj)

        resp = self.client.post(
            reverse("accounts:signup_verify"), {"code": code_obj.code}
        )
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertRedirects(resp, reverse("accounts:profile"))

    def test_wrong_code_blocks_after_max_attempts(self):
        self.client.post(
            reverse("accounts:signup"),
            {"email": "alice@example.com", "password": "rosebud-spaniel-7"},
        )
        for _ in range(5):
            self.client.post(
                reverse("accounts:signup_verify"), {"code": "000000"}
            )
        resp = self.client.post(
            reverse("accounts:signup_verify"), {"code": "000000"}
        )
        self.assertContains(resp, "Too many attempts")


class LoginTests(AuthBaseTest):
    def test_login_requires_email_code_then_succeeds(self):
        user = User.objects.create_user(
            username="bob@example.com", email="bob@example.com", password="hunter22-xy-grape"
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        resp = self.client.post(
            reverse("accounts:login"),
            {"email": "bob@example.com", "password": "hunter22-xy-grape"},
        )
        self.assertRedirects(resp, reverse("accounts:login_verify"))

        # Wrong code: still on verify page, not logged in.
        resp = self.client.post(
            reverse("accounts:login_verify"), {"code": "000000"}
        )
        self.assertEqual(resp.status_code, 200)

        code_obj = (
            EmailCode.objects
            .filter(user=user, purpose=EmailCodePurpose.LOGIN, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        resp = self.client.post(
            reverse("accounts:login_verify"), {"code": code_obj.code}
        )
        self.assertEqual(resp.status_code, 302)


class RateLimitTests(AuthBaseTest):
    def test_login_rate_limit_blocks_after_threshold(self):
        url = reverse("accounts:login")
        for i in range(10):
            resp = self.client.post(url, {"email": "x@y.com", "password": "wrong"})
            self.assertNotEqual(resp.status_code, 403, f"blocked too early at attempt {i + 1}")
        resp = self.client.post(url, {"email": "x@y.com", "password": "wrong"})
        self.assertEqual(resp.status_code, 403)

    def test_password_reset_rate_limit_blocks_after_threshold(self):
        url = reverse("accounts:password_reset")
        for i in range(5):
            resp = self.client.post(url, {"email": "anyone@example.com"})
            self.assertNotEqual(resp.status_code, 403, f"blocked too early at attempt {i + 1}")
        resp = self.client.post(url, {"email": "anyone@example.com"})
        self.assertEqual(resp.status_code, 403)

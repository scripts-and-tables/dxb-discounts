from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_site(sender, **kwargs):
    # Keep django_site row {SITE_ID} aligned with settings on every migrate,
    # so password-reset emails (and any Site-aware code) use the real domain.
    if getattr(sender, "name", None) != "django.contrib.sites":
        return
    from django.conf import settings
    from django.contrib.sites.models import Site

    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": settings.SITE_DOMAIN, "name": settings.SITE_NAME},
    )


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self):
        post_migrate.connect(_sync_site, dispatch_uid="accounts.sync_site")

from urllib.parse import urlparse

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.TextChoices):
    RESTAURANT = "restaurant", "Restaurants & Cafes"
    ATTRACTION = "attraction", "Attractions & Entertainment"
    HOTEL = "hotel", "Hotels & Staycations"
    RETAIL = "retail", "Retail, Beauty & Services"


class Place(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    area = models.CharField(max_length=120, help_text="e.g. Dubai Marina, Downtown, JBR")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    is_members_only = models.BooleanField(default=False, help_text="Hidden from anonymous visitors; visible to signed-in users.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["area"]),
            models.Index(fields=["is_published"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "place"
            slug = base
            i = 2
            while Place.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("places:detail", kwargs={"slug": self.slug})

    @property
    def logo_domain(self) -> str:
        """Bare domain extracted from `website`, e.g. 'mondoux.ae'. Empty if unset."""
        if not self.website:
            return ""
        netloc = urlparse(self.website).netloc or urlparse(self.website).path
        return netloc.removeprefix("www.").strip("/")

    @property
    def logo_url(self) -> str:
        """Brand logo via Clearbit. Returns "" if no website is set."""
        return f"https://logo.clearbit.com/{self.logo_domain}" if self.logo_domain else ""

    @property
    def favicon_url(self) -> str:
        """Favicon via Google's S2 service — used as the onerror fallback for logo_url."""
        return f"https://www.google.com/s2/favicons?domain={self.logo_domain}&sz=128" if self.logo_domain else ""

from urllib.parse import urlparse

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.TextChoices):
    RESTAURANT = "restaurant", "Restaurants & Cafes"
    ATTRACTION = "attraction", "Attractions & Entertainment"
    HOTEL = "hotel", "Hotels & Staycations"
    RETAIL = "retail", "Retail, Beauty & Services"
    SERVICE = "service", "Online & At-Home Services"


class Experience(models.Model):
    """Tag for what kind of visit a Place supports — breakfast, brunch, pool,
    spa, staycation, etc. Used as a multi-select filter on the home page."""

    slug = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=60)
    sort_order = models.PositiveSmallIntegerField(default=100, help_text="Lower = higher in the filter panel.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self) -> str:
        return self.label


class Place(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    area = models.CharField(max_length=120, blank=True, help_text="e.g. Dubai Marina, Downtown, JBR. Leave blank for online/UAE-wide services.")
    address = models.TextField(blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    is_members_only = models.BooleanField(default=False, help_text="Hidden from anonymous visitors; visible to signed-in users.")
    aggregates_branches = models.BooleanField(
        default=False,
        help_text=(
            "When True, this Place's detail page rolls up Discount rows from "
            "sibling Places whose name starts with this Place's name. Used for "
            "brand-level Places (e.g. 'Jones the Grocer') that share branding "
            "with multiple branch Places."
        ),
    )
    logo_url_override = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Direct image URL for the brand logo (e.g. an Entertainer CDN URL). "
            "Takes precedence over the domain-derived icon.horse URL when set."
        ),
    )
    experiences = models.ManyToManyField(
        Experience, blank=True, related_name="places",
        help_text="What kind of visit this place supports — used as a home-page filter.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["area"]),
            models.Index(fields=["is_published"]),
            models.Index(fields=["lat", "lng"]),
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
        """Best brand logo URL. Prefers `logo_url_override` (set by the
        refresh-icons backfill, e.g. an Entertainer CDN logo); falls back to
        icon.horse derived from the website domain. Returns "" if neither
        path produces a candidate.

        (Clearbit's Logo API was retired in 2023 — its old subdomain no longer
        resolves — which is why we use icon.horse for the auto-derived case.)
        """
        if self.logo_url_override:
            return self.logo_url_override
        return f"https://icon.horse/icon/{self.logo_domain}" if self.logo_domain else ""

    @property
    def favicon_url(self) -> str:
        """Favicon via Google's S2 service — used as the onerror fallback for logo_url."""
        return f"https://www.google.com/s2/favicons?domain={self.logo_domain}&sz=128" if self.logo_domain else ""

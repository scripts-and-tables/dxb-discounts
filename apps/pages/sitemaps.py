from django.contrib import sitemaps
from django.urls import reverse

from apps.discounts.models import Discount
from apps.places.models import Place


class StaticSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return ["pages:home", "pages:about"]

    def location(self, item):
        return reverse(item)


class PlaceSitemap(sitemaps.Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return Place.objects.filter(is_published=True, is_members_only=False)

    def lastmod(self, obj: Place):
        return obj.updated_at


class DiscountSitemap(sitemaps.Sitemap):
    priority = 0.7
    changefreq = "daily"

    def items(self):
        return Discount.objects.live().filter(is_members_only=False, place__is_members_only=False)

    def lastmod(self, obj: Discount):
        return obj.updated_at


sitemaps = {
    "static": StaticSitemap,
    "places": PlaceSitemap,
    "discounts": DiscountSitemap,
}

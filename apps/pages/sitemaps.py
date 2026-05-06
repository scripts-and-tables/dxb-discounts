from django.contrib import sitemaps
from django.urls import reverse

from apps.discounts.models import Program
from apps.places.models import Place


class StaticSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return ["pages:home", "pages:about", "discounts:list", "places:list"]

    def location(self, item):
        return reverse(item)


class PlaceSitemap(sitemaps.Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return Place.objects.filter(is_published=True, is_members_only=False)

    def lastmod(self, obj: Place):
        return obj.updated_at


class ProgramSitemap(sitemaps.Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Program.objects.filter(is_published=True)

    def lastmod(self, obj: Program):
        return obj.updated_at


sitemaps = {
    "static": StaticSitemap,
    "places": PlaceSitemap,
    "programs": ProgramSitemap,
}

from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.pages.sitemaps import sitemaps
from apps.pages.views import robots_txt


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.pages.urls")),
    path("discounts/", include("apps.discounts.urls")),
    path("places/", include("apps.places.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
]


handler404 = "apps.pages.views.handler404"
handler500 = "apps.pages.views.handler500"

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.discounts.models import Discount
from apps.places.models import Category


@require_GET
def home(request):
    featured = (
        Discount.objects
        .featured()
        .select_related("place")[:6]
    )
    recent = (
        Discount.objects
        .live()
        .select_related("place")
        .exclude(pk__in=[d.pk for d in featured])[:9]
    )
    return render(request, "pages/home.html", {
        "featured": featured,
        "recent": recent,
        "categories": Category.choices,
    })


@require_GET
def about(request):
    return render(request, "pages/about.html")


@require_GET
def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Allow: /",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def handler404(request, exception=None):
    return render(request, "pages/404.html", status=404)


def handler500(request):
    return render(request, "pages/500.html", status=500)

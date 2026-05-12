from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.accounts.selectors import attach_favorited
from apps.discounts.models import Discount, DiscountProgram

from .matching import normalize_name
from .models import Category, Place


# Map source_program slug → Tailwind background class for the outer group
# header. Mirrors the per-program palette in templates/places/_program_tile.html.
_PROGRAM_HEADER_CLASS = {
    "fazaa": "bg-red-700",
    "esaad": "bg-teal-800",
    "in_house": "bg-amber-700",
    "entertainer": "bg-blue-700",
    "zomato": "bg-rose-600",
    "repeat": "bg-violet-700",
    "playbook": "bg-cyan-700",
    "elite_club": "bg-stone-700",
    "supper_club": "bg-emerald-700",
    "emirates_platinum": "bg-zinc-800",
    "shukran": "bg-orange-700",
    "share_rewards": "bg-indigo-700",
    "emirates_skywards": "bg-sky-700",
    "atlantis_circle": "bg-slate-900",
    "u_by_emaar": "bg-purple-700",
    "al_futtaim_blue": "bg-blue-700",
    "referral": "bg-rose-700",
}


PAGE_SIZE = 24


def _filter_choices():
    areas = (
        Place.objects
        .filter(is_published=True)
        .values_list("area", flat=True)
        .distinct()
        .order_by("area")
    )
    return {
        "categories": Category.choices,
        "areas": [a for a in areas if a],
    }


@require_GET
def place_list(request):
    qs = (
        Place.objects
        .filter(is_published=True)
        .annotate(live_discount_count=Count(
            "discounts",
            filter=Q(discounts__is_active=True),
        ))
    )
    if not request.user.is_authenticated:
        qs = qs.filter(is_members_only=False)

    category = request.GET.get("category", "").strip()
    area = request.GET.get("area", "").strip()
    q = request.GET.get("q", "").strip()

    if category:
        qs = qs.filter(category=category)
    if area:
        qs = qs.filter(area__iexact=area)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(area__icontains=q))

    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))

    context = {
        "page_obj": page,
        "selected": {"category": category, "area": area, "q": q},
        **_filter_choices(),
    }
    return render(request, "places/list.html", context)


@require_GET
def place_detail(request, slug: str):
    place = get_object_or_404(Place, slug=slug, is_published=True)
    if place.is_members_only and not request.user.is_authenticated:
        raise Http404
    place_q = Q(place=place)
    if place.aggregates_branches:
        # Brand-rollup: include Discounts from sibling Places whose normalized
        # name starts with this Place's name (e.g. "Jones the Grocer" rolls up
        # "Jones the Grocer — JBR", "Jones the Grocer (Dusit Thani)", etc.).
        brand_norm = normalize_name(place.name)
        if brand_norm:
            sibling_ids = [
                p.id for p in Place.objects.filter(is_published=True).exclude(pk=place.pk).only("id", "name")
                if (n := normalize_name(p.name)) and n.startswith(brand_norm + " ")
            ]
            if sibling_ids:
                place_q |= Q(place_id__in=sibling_ids)
    discounts_qs = (
        Discount.objects
        .live()
        .filter(place_q)
        .select_related("place")
        .order_by("-is_featured", "-created_at")
    )
    if not request.user.is_authenticated:
        discounts_qs = discounts_qs.filter(is_members_only=False)
    discounts = attach_favorited(discounts_qs, request.user)
    # Annotate aggregated rows with a branch label (the part of the sibling
    # Place's name after the brand) so the template can render a chip.
    brand_lower = place.name.lower()
    for d in discounts:
        if place.aggregates_branches and d.place_id != place.id:
            sibling_name = d.place.name
            if sibling_name.lower().startswith(brand_lower):
                tail = sibling_name[len(brand_lower):].strip(" -—–·()[]")
                d.branch_label = tail or sibling_name
            else:
                d.branch_label = sibling_name
        else:
            d.branch_label = ""

    # Collapse identical offers that came from per-outlet ingest. After the
    # dedup-places merges, a brand-level Place often holds N Discount rows
    # with identical (title, headline, description, terms, type) — one per
    # original branch outlet. Showing 35 copies of "3 Bottles of Grapes — 2-
    # for-1" is unhelpful; collapse to one row and stash a count.
    deduped: list[Discount] = []
    seen: dict[tuple, Discount] = {}
    for d in discounts:
        sig = (
            d.source_program or "",
            d.title.strip(),
            (d.description or "").strip(),
            (d.terms or "").strip(),
            d.discount_type,
            d.percentage,
            d.fixed_price_aed,
        )
        keeper = seen.get(sig)
        if keeper is None:
            d.branch_count = 1
            seen[sig] = d
            deduped.append(d)
        else:
            keeper.branch_count += 1
            # Promote `is_featured` and `is_favorited` to the keeper if any
            # of the duplicates carried them — surface the strongest signal.
            if d.is_featured and not keeper.is_featured:
                keeper.is_featured = True
            if getattr(d, "is_favorited", False) and not getattr(keeper, "is_favorited", False):
                keeper.is_favorited = True
    discounts = deduped

    # Group by source_program. In-house first; remaining groups by descending
    # offer count (so the program with the most offers shows up high in the list).
    by_program: dict[str, list[Discount]] = {}
    label_for: dict[str, str] = dict(DiscountProgram.choices)
    for d in discounts:
        by_program.setdefault(d.source_program or "", []).append(d)
    ordered_keys = []
    if "in_house" in by_program:
        ordered_keys.append("in_house")
    rest = [k for k in by_program if k != "in_house"]
    rest.sort(key=lambda k: -len(by_program[k]))
    ordered_keys += rest
    discount_groups = [
        {
            "slug": k,
            "label": label_for.get(k) or "Other offer",
            "header_class": _PROGRAM_HEADER_CLASS.get(k, "bg-slate-700"),
            "discounts": by_program[k],
        }
        for k in ordered_keys
    ]

    return render(request, "places/detail.html", {
        "place": place,
        "discount_groups": discount_groups,
    })

"""Read helpers shared across views."""
from typing import Iterable

from .models import Favorite


def attach_favorited(discounts: Iterable, user) -> list:
    """Attach a `is_favorited` boolean to each Discount based on the user's favorites.

    Returns the list (so callers can chain). Materialises the iterable.
    """
    discounts = list(discounts)
    if not user.is_authenticated or not discounts:
        for d in discounts:
            d.is_favorited = False
        return discounts

    fav_ids = set(
        Favorite.objects
        .filter(user=user, discount__in=discounts)
        .values_list("discount_id", flat=True)
    )
    for d in discounts:
        d.is_favorited = d.id in fav_ids
    return discounts

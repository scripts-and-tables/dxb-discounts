"""Brand-name normalization used by audit_place_icons + resolve_place_icons.

The ingested Place names follow a "Brand <separator> Branch" pattern, e.g.
"1900 Burger – Al Sufouh" or "Color & Aroma - Home Services". To match a
Place against a brand-level catalog (Entertainer merchant_name, Playbook
venue name, etc.), strip the branch suffix and collapse to ASCII-lower-
alphanumeric.
"""
from __future__ import annotations

import re

# Brand/branch separators seen in production data:
#   – (en-dash U+2013), — (em-dash U+2014), ― (horizontal bar U+2015),
#   ` - ` (ASCII hyphen with surrounding spaces).
_SUFFIX_SEP = re.compile(r"\s*[–—―]\s*|\s+-\s+")

# Strip everything that isn't a basic alphanumeric so that "St Regis",
# "St. Regis", and "St-Regis" all collapse to the same key.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def brand(s: str | None) -> str:
    """Return just the brand portion (before any branch separator)."""
    if not s:
        return ""
    return _SUFFIX_SEP.split(s, maxsplit=1)[0]


def normalize(s: str | None) -> str:
    """Return a stable lookup key: lowercase, alphanumeric-only, brand-only."""
    return _NON_ALNUM.sub("", brand(s).lower()) if s else ""

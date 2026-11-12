"""Category selector helpers: query-param parsing and portfolio filtering.

Used by the app page and by tests. No Streamlit import.
"""
from __future__ import annotations

import pandas as pd

try:
    from .calc import CATEGORIES
except ImportError:
    from calc import CATEGORIES

ALL = "all"


def category_slug(category: str) -> str:
    """URL form: 'all', 'lighting', 'home-textiles'."""
    if category == ALL or not category:
        return ALL
    return str(category).strip().lower().replace("_", "-").replace(" ", "-")


def parse_category_param(qp, categories=None) -> str:
    """Return a category name from CATEGORIES, or ALL. Unknown values fall back to ALL."""
    categories = list(categories) if categories is not None else list(CATEGORIES)
    if qp is None:
        return ALL
    if isinstance(qp, (list, tuple)):
        qp = qp[0] if qp else None
        if qp is None:
            return ALL
    raw = category_slug(str(qp))
    if raw in ("", ALL, "all-categories"):
        return ALL
    for c in categories:
        if raw == category_slug(c):
            return c
    return ALL


def assessed_counts_by_category(listings: pd.DataFrame) -> dict:
    """Marketplace (3P) listing counts by category, used in selector labels."""
    three = listings[listings["listing_type"] == "3P"]
    return {c: int((three["category"] == c).sum()) for c in CATEGORIES}


def selector_options(listings: pd.DataFrame, categories=None) -> list[str]:
    """Keys for the selector: 'all' first, then each category."""
    categories = list(categories) if categories is not None else list(CATEGORIES)
    return [ALL] + categories


def selector_label(key: str, listings: pd.DataFrame) -> str:
    counts = assessed_counts_by_category(listings)
    if key == ALL:
        return "All categories"
    return f"{key.title()} ({counts.get(key, 0)})"


def filter_results(res: pd.DataFrame, category: str) -> pd.DataFrame:
    """Marketplace results for the selector, re-ranked 1..n in the same order."""
    if category == ALL or not category:
        out = res.copy()
    else:
        out = res[res["category"] == category].copy()
    out = out.reset_index(drop=True)
    if not out.empty:
        out["rank"] = range(1, len(out) + 1)
    return out


def listings_for_view(listings: pd.DataFrame, category: str) -> pd.DataFrame:
    """Listings (3P and 1P) to feed sensitivity and insights for the current view."""
    if category == ALL or not category:
        return listings
    return listings[listings["category"] == category]

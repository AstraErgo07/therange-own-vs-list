"""
Plain-English observations from the model at a given set of assumptions.

Every sentence is derived from evaluate_portfolio, and is worded as a finding
in this sample under these assumptions, not as a business result.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd

try:
    from .calc import (BRING_IN_HOUSE, KEEP_3P, RECOMMENDATIONS, TEST_3P_FIRST,
                       Assumptions, evaluate_portfolio, hurdle_sensitivity, substitute_prices)
except ImportError:
    from calc import (BRING_IN_HOUSE, KEEP_3P, RECOMMENDATIONS, TEST_3P_FIRST,
                      Assumptions, evaluate_portfolio, hurdle_sensitivity, substitute_prices)


def gbp(x, dp=2):
    return f"-£{abs(x):,.{dp}f}" if x < 0 else f"£{x:,.{dp}f}"


def _counts(res: pd.DataFrame) -> dict:
    return {r: int((res["recommendation"] == r).sum()) for r in RECOMMENDATIONS}


def category_breakdown(res: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cat, g in res.groupby("category"):
        rules = Counter(g["rule"])
        main_rule = rules.most_common(1)[0][0]
        rows.append({
            "Category": cat,
            "Marketplace listings": len(g),
            BRING_IN_HOUSE: int((g["recommendation"] == BRING_IN_HOUSE).sum()),
            TEST_3P_FIRST: int((g["recommendation"] == TEST_3P_FIRST).sum()),
            KEEP_3P: int((g["recommendation"] == KEEP_3P).sum()),
            "Most common rule": main_rule,
            "Median 1P contribution £/unit": round(g["contrib_1p_unit"].median(), 2),
            "Median 3P value £/unit": round(g["net_3p_unit"].median(), 2),
            "Median return on stock": f"{g['return_on_capital'].median():.0%}",
        })
    return pd.DataFrame(rows).sort_values("Category").reset_index(drop=True)


def assessed_table(res: pd.DataFrame, categories=None) -> pd.DataFrame:
    """Compact table: category, listings assessed, in-house, test first, keep 3P."""
    try:
        from .calc import CATEGORIES
    except ImportError:
        from calc import CATEGORIES
    categories = list(categories) if categories is not None else list(CATEGORIES)
    rows = []
    for cat in categories:
        g = res[res["category"] == cat]
        if g.empty:
            continue
        rows.append({
            "Category": cat,
            "Listings assessed": len(g),
            BRING_IN_HOUSE: int((g["recommendation"] == BRING_IN_HOUSE).sum()),
            TEST_3P_FIRST: int((g["recommendation"] == TEST_3P_FIRST).sum()),
            KEEP_3P: int((g["recommendation"] == KEEP_3P).sum()),
        })
    if len(rows) > 1:
        rows.append({
            "Category": "All categories",
            "Listings assessed": sum(r["Listings assessed"] for r in rows),
            BRING_IN_HOUSE: sum(r[BRING_IN_HOUSE] for r in rows),
            TEST_3P_FIRST: sum(r[TEST_3P_FIRST] for r in rows),
            KEEP_3P: sum(r[KEEP_3P] for r in rows),
        })
    return pd.DataFrame(rows)


def disagreement(res: pd.DataFrame, a: Assumptions) -> pd.DataFrame:
    """Products where contribution per unit and return on stock disagree on the 1P case."""
    m = res["contrib_1p_unit"] > res["net_3p_unit"]
    r = res["return_on_capital"] > a.hurdle_rate
    out = res[(m != r)].copy()
    if out.empty:
        out["disagreement"] = pd.Series(dtype="object")
        return out
    out["disagreement"] = [
        "1P wins on contribution, return on stock is below the hurdle" if mi and not ri
        else "return on stock clears the hurdle, 3P is worth more per unit"
        for mi, ri in zip(m[out.index], r[out.index])
    ]
    return out


def insights(listings: pd.DataFrame, a: Assumptions | None = None, category: str | None = None) -> list[str]:
    """Factual bullets at the given assumptions (defaults if none).

    Pass category to report only that category. 1P items in the frame are
    counted as substitutes, not as listings assessed.
    """
    a = a or Assumptions()
    if category:
        listings = listings[listings["category"] == category]
    res = evaluate_portfolio(listings, a)
    n_3p = int((listings.listing_type == "3P").sum())
    n_1p = int((listings.listing_type == "1P").sum())
    n_cats = int(listings.loc[listings.listing_type == "3P", "category"].nunique())
    c = _counts(res)
    recs = (f"{BRING_IN_HOUSE} {c[BRING_IN_HOUSE]}, {TEST_3P_FIRST} {c[TEST_3P_FIRST]}, "
            f"{KEEP_3P} {c[KEEP_3P]}")
    if n_cats == 1:
        cat = listings.loc[listings.listing_type == "3P", "category"].iloc[0]
        scope = (f"{n_3p} marketplace listings are assessed in {cat}. {n_1p} of The Range's "
                 f"own items in this category are used only as price and contribution "
                 f"comparisons (substitutes), not assessed.")
    else:
        scope = (f"{n_3p} marketplace listings are assessed across {n_cats} categories. "
                 f"{n_1p} of The Range's own items are used only as price and contribution "
                 f"comparisons (substitutes), not assessed.")
    lead = (f"In this sample, under these assumptions, {scope} Recommendations: {recs}. "
            f"These are model results on a small public sample, not a forecast of revenue.")
    bullets = [lead]

    # Per-category pattern
    for cat, g in res.groupby("category"):
        recs = _counts(g)
        n = len(g)
        if recs[KEEP_3P] == n:
            why = Counter(g["rule"]).most_common(1)[0][0]
            if why == "3p_wins_margin_and_roc":
                reason = "1P contribution per unit is lower (and in some cases negative) and return on stock is below the hurdle"
            elif why == "3p_wins_margin":
                reason = "3P is worth more contribution per unit"
            else:
                reason = why.replace("_", " ")
            # if mixed rules among all-keep
            rules = set(g["rule"])
            if rules == {"3p_wins_margin", "3p_wins_margin_and_roc"}:
                reason = "3P is worth more contribution per unit (and for some, return on stock is below the hurdle too)"
            ful = float(g["fulfilment_cost"].iloc[0])
            neg = int((g["contrib_1p_unit"] < 0).sum())
            tail = ""
            if ful >= 20:
                tail = (f" Estimated pick, pack and delivery is {gbp(ful)} a unit. "
                        f"{neg} of the {n} have negative 1P contribution after that cost. "
                        f"On the dearest listing, 3P commission alone is {gbp(g.loc[g['price'].idxmax(), 'contrib_3p_unit'] + 0.50)} before cost to serve.")
            bullets.append(f"In this sample, under these assumptions, every {cat} marketplace listing ({n}) comes out as Keep 3P: {reason}.{tail}")
        elif recs[BRING_IN_HOUSE] == n:
            roc = g["return_on_capital"]
            bullets.append(f"In this sample, under these assumptions, every {cat} marketplace listing ({n}) comes out as Bring in-house: 1P contribution per unit is higher and return on stock is between {roc.min():.0%} and {roc.max():.0%}.")
        elif recs[TEST_3P_FIRST] == n and set(g["rule"]) == {"volatile_demand"}:
            cv = g["weekly_units_cv"].iloc[0]
            bullets.append(f"In this sample, under these assumptions, every {cat} marketplace listing ({n}) comes out as Test as 3P first, because weekly demand is treated as swinging by {cv:.0%}, which is above the {a.volatility_cv_threshold:.0%} limit. The money tests do not get a say.")
        else:
            parts = [f"{recs[r]} {r}" for r in RECOMMENDATIONS if recs[r]]
            extra = ""
            # price-point split: cheaper keep 3P, dearer in-house
            inh = g[g["recommendation"] == BRING_IN_HOUSE]
            keep = g[g["recommendation"] == KEEP_3P]
            if len(inh) and len(keep) and inh["price"].min() > keep["price"].max():
                cheap = (gbp(keep["price"].iloc[0]) if len(keep) == 1 or keep["price"].min() == keep["price"].max()
                         else f"{gbp(keep['price'].min())} to {gbp(keep['price'].max())}")
                dear = (gbp(inh["price"].iloc[0]) if len(inh) == 1 or inh["price"].min() == inh["price"].max()
                        else f"{gbp(inh['price'].min())} to {gbp(inh['price'].max())}")
                extra = (f" The ones recommended in-house are the dearer listings ({dear}); the cheaper "
                         f"{'one' if len(keep)==1 else 'ones'} ({cheap}) {'stays' if len(keep)==1 else 'stay'} 3P, where fulfilment of "
                         f"{gbp(keep['fulfilment_cost'].iloc[0])} eats more of the 1P contribution.")
            bullets.append(f"In this sample, under these assumptions, {cat} splits {', '.join(parts)}.{extra}")

    # Disagreement
    d = disagreement(res, a)
    unit_lose_roc_win = d[d["disagreement"].str.startswith("return on stock")]
    unit_win_roc_lose = d[d["disagreement"].str.startswith("1P wins")]
    if unit_win_roc_lose.empty:
        bullets.append(f"In this sample, under these assumptions, no listing wins on contribution per unit and then fails the {a.hurdle_rate:.0%} return-on-stock hurdle.")
    else:
        bullets.append(f"In this sample, under these assumptions, {len(unit_win_roc_lose)} listings win on contribution per unit but fail the {a.hurdle_rate:.0%} return-on-stock hurdle, so they are not recommended in-house.")
    if not unit_lose_roc_win.empty:
        # pick a clear example: largest 1P contribution among them, or furniture echo
        ex = unit_lose_roc_win.sort_values("contrib_1p_unit", ascending=False).iloc[0]
        bullets.append(
            f"Contribution per unit and return on stock do disagree in this sample. "
            f"{len(unit_lose_roc_win)} listings clear the {a.hurdle_rate:.0%} hurdle on return on stock "
            f"but 3P is still worth more per unit, so they stay 3P (both tests must pass). "
            f"Example: {ex['title']} ({ex['category']}) makes {gbp(ex['contrib_1p_unit'])} 1P contribution "
            f"a unit and {ex['return_on_capital']:.0%} return on stock, but net 3P is {gbp(ex['net_3p_unit'])}."
        )

    # Hurdle fragility
    hs, flipped, _ = hurdle_sensitivity(listings, a, hurdles=(0.25, 0.50, 1.00, 1.50, 2.00))
    zero = [row["scenario"] for _, row in hs.iterrows() if row["flipped_vs_current"] == 0 and abs(row["hurdle"] - a.hurdle_rate) > 1e-9]
    first_flip = hs[hs["flipped_vs_current"] > 0]
    if list(hs.loc[hs["hurdle"].round(2).isin([0.25, 0.50, 1.00]), "flipped_vs_current"]) == [0, 0, 0] or (
        int(hs[hs.hurdle == 0.25].flipped_vs_current) == 0 and int(hs[hs.hurdle == 0.50].flipped_vs_current) == 0 and int(hs[hs.hurdle == 1.00].flipped_vs_current) == 0
    ):
        msg = (f"In this sample, under these assumptions, raising the hurdle from {a.hurdle_rate:.0%} to 50% or 100% "
               f"flips no recommendations. Every listing that wins on contribution per unit already clears 100% "
               f"return on stock, so the {a.hurdle_rate:.0%} bar is not what decides these cases.")
        if not first_flip.empty:
            row = first_flip.iloc[0]
            msg += (f" The bar starts to matter higher up: at {row['hurdle']:.0%} there are {int(row['flipped_vs_current'])} "
                    f"flips, and at 200% there are {int(hs[hs.hurdle == 2.00].flipped_vs_current.iloc[0])} "
                    f"(Bring in-house falls to {int(hs[hs.hurdle == 2.00][BRING_IN_HOUSE].iloc[0])}).")
        bullets.append(msg)
    else:
        bullets.append(
            "In this sample, under these assumptions, the recommendations at 25%, 50% and 100% hurdles are: "
            + "; ".join(
                f"{row['scenario']}: {BRING_IN_HOUSE} {int(row[BRING_IN_HOUSE])}, "
                f"{TEST_3P_FIRST} {int(row[TEST_3P_FIRST])}, {KEEP_3P} {int(row[KEEP_3P])}, "
                f"{int(row['flipped_vs_current'])} flipped"
                for _, row in hs[hs.hurdle.isin([0.25, 0.50, 1.00])].iterrows()
            )
            + "."
        )

    # Volatility
    vol = res[res["rule"] == "volatile_demand"]
    if not vol.empty:
        cats = ", ".join(sorted(vol["category"].unique()))
        bullets.append(f"In this sample, under these assumptions, {len(vol)} listings ({cats}) are Test as 3P first solely because of the demand-volatility rule, whatever contribution and return on stock say.")

    return bullets

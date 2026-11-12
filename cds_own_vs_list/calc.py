"""
cds_own_vs_list/calc.py - "Own vs List" for The Range (CDS Superstores). Pure functions, no AI.

Same engine as the original Own vs List prototype, now fed by REAL listings:
  REAL:      price, sold-by (The Range = 1P, marketplace partner = 3P), seller name, category,
             commission rate (The Range's published marketplace fee table, Feb 2026),
             and the price of The Range's own 1P substitutes in the same category.
  ESTIMATED: cogs, fulfilment cost, return rate, markdown rate, stock cover, weekly units,
             demand volatility - from category benchmarks in BENCHMARKS (editable in the app).

All money in GBP per unit unless the name says annual.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace

import pandas as pd

CATEGORIES = ["home textiles", "kitchen", "outdoor", "beauty", "furniture", "lighting", "pets", "crafts"]
BRING_IN_HOUSE, KEEP_3P, TEST_3P_FIRST = "Bring in-house", "Keep 3P", "Test as 3P first"
RECOMMENDATIONS = [BRING_IN_HOUSE, TEST_3P_FIRST, KEEP_3P]
EPSILON = 0.01

# REAL: The Range marketplace commission (percent of total sale incl. shipping), from
# https://marketplacetherange.zendesk.com/hc/en-gb/articles/360018475658-Commission-Based-Fees
# (updated 24 Feb 2026). Mapping of our categories to their selling categories is my judgement:
COMMISSION_REAL = {
    "home textiles": 0.13,   # Home Furnishings 13%
    "kitchen": 0.15,         # Cooking & Dining 15% (air fryers sit under /cooking-and-dining/;
                             # if classed as Technology & Appliances it would be 13%)
    "outdoor": 0.14,         # Outdoor Living 14%
    "beauty": 0.13,          # Health & Beauty 13%
    "furniture": 0.13,       # Furniture 13%
    "lighting": 0.13,        # Lighting 13%
    "pets": 0.11,            # Pets 11%
    "crafts": 0.13,          # Arts & Crafts 13%
}

ESTIMATED_FIELDS = ["cogs", "fulfilment_cost", "return_rate", "markdown_rate",
                    "stock_cover_days", "weekly_units", "weekly_units_cv"]
REAL_FIELDS = ["price", "sold_by", "listing_type", "category", "commission_rate", "substitute_1p_price"]


@dataclass
class Benchmark:
    """ESTIMATES (cogs_pct, return_rate and markdown_rate apply to the ex-VAT price) for one category (UK value home/general-merchandise retail norms - my
    judgement, NOT CDS data). Every value is editable in the app sidebar."""
    cogs_pct: float            # landed cost as share of ex-VAT selling price
    fulfilment_cost: float     # £ per unit pick, pack, deliver (1P)
    return_rate: float         # share of sales value refunded
    markdown_rate: float       # share of sales value lost to markdowns / clearance
    stock_cover_days: float    # days of stock held if 1P
    ref_weekly_units: float    # weekly units at the reference price
    ref_price: float           # reference price for the units curve
    elasticity: float          # units scale with (ref_price / price) ** elasticity
    weekly_units_cv: float     # demand volatility (coefficient of variation)


def default_benchmarks() -> dict:
    return {
        # cogs_pct is a share of the EX-VAT price. All of these are estimates (my judgement
        # for UK value home retail, not CDS data).
        "home textiles": Benchmark(0.40, 3.00, 0.05, 0.15, 75, 25, 15.0, 1.0, 0.35),
        "kitchen":       Benchmark(0.65, 7.50, 0.08, 0.07, 45, 12, 50.0, 1.2, 0.30),  # branded small electricals
        "outdoor":       Benchmark(0.40, 3.50, 0.06, 0.20, 90, 15, 15.0, 1.0, 0.55),  # seasonal -> volatile
        "beauty":        Benchmark(0.65, 3.00, 0.06, 0.08, 50, 6, 40.0, 1.0, 0.30),   # branded hair electricals
        "furniture":     Benchmark(0.55, 45.00, 0.10, 0.15, 120, 3, 400.0, 1.0, 0.40),  # bulky sofas; two-person delivery
        "lighting":      Benchmark(0.45, 4.50, 0.08, 0.12, 60, 12, 25.0, 1.0, 0.35),  # indoor table lamps
        "pets":          Benchmark(0.45, 5.00, 0.06, 0.10, 50, 10, 25.0, 1.0, 0.30),  # pet beds
        "crafts":        Benchmark(0.40, 3.00, 0.04, 0.10, 70, 8, 15.0, 1.0, 0.40),   # craft kits, long-tail
    }


@dataclass
class Assumptions:
    holding_rate: float = 0.08                  # physical storage, insurance and shrink only, % of cost a year
                                                # (Assumption). Cost of capital is not in this figure;
                                                # it is tested only by hurdle_rate on return on stock.
    vat_rate: float = 0.20                      # REAL: UK standard VAT; shelf prices include it
    hurdle_rate: float = 0.25                   # minimum return on stock to go 1P (Assumption: cost of capital plus a cushion)
    marketplace_cost_per_unit: float = 0.50     # cost to serve one 3P sale (£)
    diversion_rates: dict = field(default_factory=lambda: {c: 0.30 for c in CATEGORIES})
    volatility_cv_threshold: float = 0.50
    near_threshold_band: float = 0.10
    gmv_flag_quantile: float = 0.75
    commission_rates: dict = field(default_factory=lambda: dict(COMMISSION_REAL))
    benchmarks: dict = field(default_factory=default_benchmarks)

    def diversion_for(self, c): return float(self.diversion_rates.get(c, 0.30))
    def commission_for(self, c): return float(self.commission_rates.get(c, 0.13))

    def with_all_diversion(self, rate):
        return replace(self, diversion_rates={c: rate for c in self.diversion_rates})

    def with_cogs_shift(self, pts):
        """Copy with every category's cogs_pct moved by `pts` (e.g. +0.10 = 10 points dearer)."""
        b = {c: replace(v, cogs_pct=min(max(v.cogs_pct + pts, 0.05), 0.95)) for c, v in self.benchmarks.items()}
        return replace(self, benchmarks=b)

    def with_hurdle(self, rate):
        return replace(self, hurdle_rate=rate)

    def to_json(self):
        d = asdict(self)
        return json.dumps(d, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Core formulas (unchanged from the original Own vs List)
# ---------------------------------------------------------------------------
def holding_cost(cogs, stock_cover_days, holding_rate):
    """Physical holding cost per unit: cogs x physical holding rate x days of stock / 365.

    holding_rate here is storage, insurance and shrink only. Cost of capital is not
    subtracted from contribution; it is tested only by comparing return on stock
    with the hurdle. That avoids counting the cost of money twice.
    """
    return cogs * holding_rate * stock_cover_days / 365.0


def contribution_1p(price, cogs, fulfilment_cost, return_rate, markdown_rate, holding):
    """= price - cogs - fulfilment - price x return_rate - price x markdown_rate - holding"""
    return price - cogs - fulfilment_cost - price * return_rate - price * markdown_rate - holding


def contribution_3p(price, commission_rate, marketplace_cost_per_unit):
    """= price x commission_rate - marketplace cost per unit"""
    return price * commission_rate - marketplace_cost_per_unit


def average_inventory_value(cogs, weekly_units, stock_cover_days):
    """= cogs x weekly_units x stock_cover_days / 7"""
    return cogs * weekly_units * (stock_cover_days / 7.0)


def return_on_capital(c1p, cogs, weekly_units, stock_cover_days):
    """annual 1P contribution (52 weeks) / average inventory value"""
    inv = average_inventory_value(cogs, weekly_units, stock_cover_days)
    return (c1p * weekly_units * 52) / inv if inv > 0 else 0.0


def net_3p_benefit(c3p, diversion_rate, lost_1p_contribution):
    """= 3P contribution - diversion_rate x lost 1P contribution on the substitute (floored at 0)"""
    return c3p - diversion_rate * max(lost_1p_contribution, 0.0)


def decide(c1p, net3p, roc, cv, a: Assumptions):
    """Same precedence as the original: volatile -> Test; near a threshold -> Test;
    1P beats net 3P AND ROC > hurdle -> Bring in-house; otherwise Keep 3P."""
    band = a.near_threshold_band
    if cv > a.volatility_cv_threshold:
        return TEST_3P_FIRST, "volatile_demand"
    m_pass, r_pass = c1p > net3p, roc > a.hurdle_rate
    near_m = abs(c1p - net3p) <= band * max(abs(net3p), EPSILON)
    near_r = abs(roc - a.hurdle_rate) <= band * max(abs(a.hurdle_rate), EPSILON)
    if m_pass and r_pass:
        near = near_m or near_r
    elif r_pass:
        near = near_m
    elif m_pass:
        near = near_r
    else:
        near = near_m and near_r
    if near:
        return TEST_3P_FIRST, "near_threshold"
    if m_pass and r_pass:
        return BRING_IN_HOUSE, "1p_wins"
    if not m_pass and not r_pass:
        return KEEP_3P, "3p_wins_margin_and_roc"
    return KEEP_3P, "3p_wins_margin" if not m_pass else "roc_below_hurdle"


# ---------------------------------------------------------------------------
# NEW: estimates from benchmarks, and the real 1P substitute
# ---------------------------------------------------------------------------
def estimate_weekly_units(price, b: Benchmark):
    """ESTIMATE: ref_weekly_units x (ref_price / price) ** elasticity, clamped to 0.5-200.
    (The Range shows almost no review counts, so units cannot be read from the page.)"""
    if price <= 0:
        return 0.5
    return min(max(b.ref_weekly_units * (b.ref_price / price) ** b.elasticity, 0.5), 200.0)


def ex_vat(price, vat_rate):
    """Shelf price includes VAT; the retailer keeps price / (1 + VAT) as 1P revenue."""
    return price / (1.0 + vat_rate)


def estimate_fields(price, b: Benchmark, vat_rate: float = 0.20) -> dict:
    """All ESTIMATED economics for one listing from its REAL price and category benchmark.
    cogs = ex-VAT price x cogs_pct."""
    return {"cogs": ex_vat(price, vat_rate) * b.cogs_pct, "fulfilment_cost": b.fulfilment_cost,
            "return_rate": b.return_rate, "markdown_rate": b.markdown_rate,
            "stock_cover_days": b.stock_cover_days, "weekly_units": estimate_weekly_units(price, b),
            "weekly_units_cv": b.weekly_units_cv}


def substitute_prices(listings: pd.DataFrame) -> dict:
    """REAL: median price of The Range's own (1P) listings per category = the substitute
    a diverted shopper would otherwise buy."""
    one_p = listings[listings["listing_type"] == "1P"]
    return one_p.groupby("category")["price"].median().to_dict()


def unit_contribution_1p(price, b: Benchmark, holding_rate, vat_rate=0.20):
    """1P contribution per unit at a given shelf price, using ex-VAT revenue."""
    e = estimate_fields(price, b, vat_rate)
    hold = holding_cost(e["cogs"], e["stock_cover_days"], holding_rate)
    return contribution_1p(ex_vat(price, vat_rate), e["cogs"], e["fulfilment_cost"], e["return_rate"], e["markdown_rate"], hold)


def evaluate_product(row: dict, a: Assumptions, subs: dict) -> dict:
    cat, price = row["category"], float(row["price"])
    b = a.benchmarks[cat]
    e = estimate_fields(price, b, a.vat_rate)
    net = ex_vat(price, a.vat_rate)            # 1P revenue excludes VAT
    hold = holding_cost(e["cogs"], e["stock_cover_days"], a.holding_rate)
    c1p = contribution_1p(net, e["cogs"], e["fulfilment_cost"], e["return_rate"], e["markdown_rate"], hold)
    rate = a.commission_for(cat)
    # The Range's commission is a % of the TOTAL sale the customer pays (VAT-inclusive);
    # the seller, not The Range, owes the VAT on the goods.
    c3p = contribution_3p(price, rate, a.marketplace_cost_per_unit)
    sub_price = subs.get(cat)
    sub_c1p = unit_contribution_1p(sub_price, b, a.holding_rate, a.vat_rate) if sub_price else c1p  # fallback: own economics
    div = a.diversion_for(cat)
    net3p = net_3p_benefit(c3p, div, sub_c1p)
    roc = return_on_capital(c1p, e["cogs"], e["weekly_units"], e["stock_cover_days"])
    rec, rule = decide(c1p, net3p, roc, e["weekly_units_cv"], a)
    wu = e["weekly_units"]
    return {
        "sku": row["sku"], "category": cat, "title": row["title"], "sold_by": row["sold_by"],
        "price": price, "price_ex_vat": net, "commission_rate": rate, **e, "holding_cost_unit": hold,
        "substitute_1p_price": sub_price, "substitute_1p_contrib": sub_c1p,
        "gmv_annual": price * wu * 52,
        "contrib_1p_unit": c1p, "contrib_3p_unit": c3p, "diversion_rate": div, "net_3p_unit": net3p,
        "advantage_1p_unit": c1p - net3p, "advantage_1p_annual": (c1p - net3p) * wu * 52,
        "commission_annual": c3p * wu * 52,
        "avg_inventory_value": average_inventory_value(e["cogs"], wu, e["stock_cover_days"]),
        "return_on_capital": roc, "hurdle_rate": a.hurdle_rate,
        "recommendation": rec, "rule": rule,
        "estimated_fields": ";".join(ESTIMATED_FIELDS),
        "verified": bool(row.get("verified", False)), "url": row.get("url", ""),
    }


def evaluate_portfolio(listings: pd.DataFrame, a: Assumptions) -> pd.DataFrame:
    """Evaluate every 3P (marketplace) listing; 1P listings are only used as substitutes.
    Ranked by annual 1P advantage (biggest case for bringing in-house first)."""
    subs = substitute_prices(listings)
    cands = listings[listings["listing_type"] == "3P"]
    out = pd.DataFrame([evaluate_product(r, a, subs) for r in cands.to_dict("records")])
    out = out.sort_values("advantage_1p_annual", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


def gmv_vs_contribution_flags(results, a: Assumptions):
    """GMV in the top quartile but not recommended for in-house."""
    cut = results["gmv_annual"].quantile(a.gmv_flag_quantile)
    m = (results["gmv_annual"] >= cut) & (results["recommendation"] != BRING_IN_HOUSE)
    return results[m].sort_values("gmv_annual", ascending=False)


def sensitivity(listings, a: Assumptions, rates=(0.10, 0.30, 0.50), cogs_shifts=(-0.10, 0.10)):
    """Counts and flips vs current settings at each diversion rate (all categories), plus
    a COGS-estimate stress test (+/- 10 points on every category's cogs %)."""
    base = evaluate_portfolio(listings, a).set_index("sku")["recommendation"]
    scenarios = [(f"Diversion {r:.0%}", a.with_all_diversion(r)) for r in rates]
    scenarios += [(f"COGS estimate {s:+.0%} pts", a.with_cogs_shift(s)) for s in cogs_shifts]
    rows, flipped = [], {}
    for name, sc in scenarios:
        recs = evaluate_portfolio(listings, sc).set_index("sku")["recommendation"].reindex(base.index)
        ch = recs[recs != base]
        flipped[name] = [f"{k}: {base[k]} -> {recs[k]}" for k in ch.index]
        row = {"scenario": name}
        row.update({rec: int((recs == rec).sum()) for rec in RECOMMENDATIONS})
        row["flipped_vs_current"] = len(ch)
        rows.append(row)
    return pd.DataFrame(rows), flipped, base


def hurdle_sensitivity(listings, a: Assumptions, hurdles=(0.25, 0.50, 1.00)):
    """How recommendations change when only the return-on-stock hurdle moves.

    Default hurdles are 25%, 50% and 100%. These are not industry standards;
    they show how sensitive the answer is to a bar the firm would set itself.
    """
    base = evaluate_portfolio(listings, a).set_index("sku")["recommendation"]
    rows, flipped = [], {}
    for h in hurdles:
        name = f"Hurdle {h:.0%}"
        recs = evaluate_portfolio(listings, a.with_hurdle(h)).set_index("sku")["recommendation"].reindex(base.index)
        ch = recs[recs != base]
        flipped[name] = [f"{k}: {base[k]} -> {recs[k]}" for k in ch.index]
        row = {"scenario": name, "hurdle": h}
        row.update({rec: int((recs == rec).sum()) for rec in RECOMMENDATIONS})
        row["flipped_vs_current"] = len(ch)
        rows.append(row)
    return pd.DataFrame(rows), flipped, base


def seller_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Per marketplace seller: listings sampled, recommendations, estimated GMV."""
    g = results.groupby("sold_by")
    out = g.agg(listings=("sku", "count"), est_gmv_annual=("gmv_annual", "sum"),
                bring_in_house=("recommendation", lambda s: (s == BRING_IN_HOUSE).sum()),
                categories=("category", lambda s: ", ".join(sorted(set(s))))).reset_index()
    return out.sort_values("est_gmv_annual", ascending=False)


def load_listings(path) -> pd.DataFrame:
    return pd.read_csv(path)

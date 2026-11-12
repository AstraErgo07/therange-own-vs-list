"""
cds_own_vs_list/workings.py - plain-English, step-by-step workings for one Own vs List decision.

Used by the app page and tools/build_overview.py. It re-uses the results of calc.evaluate_product and does not
change any calculation; the tests check that the worked numbers match the engine.
"""
from __future__ import annotations

try:
    from .calc import Assumptions
except ImportError:
    from calc import Assumptions

REAL, ASSUMED, WORKED, POLICY = "Real (listing or published fee)", "Assumed (slider)", "Worked out", "Policy (slider)"


def _gbp(x, dp=2):
    return f"-£{abs(x):,.{dp}f}" if x < 0 else f"£{x:,.{dp}f}"


def step(step, working, result, source):
    return {"step": step, "working": working, "result": result, "source": source}


def own_vs_list_workings(c: dict, a: Assumptions) -> list[dict]:
    """c = one row from calc.evaluate_portfolio."""
    b = a.benchmarks[c["category"]]
    s = []
    p, net = c["price"], c["price_ex_vat"]
    s.append(step("Shelf price (avg selling price per unit)", "price on the listing, VAT included", _gbp(p), REAL))
    wu = c["weekly_units"]
    s.append(step("Units a week", f"a {c['category']} item at £{b.ref_price:g} is assumed to sell {b.ref_weekly_units:g} a "
                  f"week; dearer items sell fewer ({b.ref_weekly_units:g} x ({b.ref_price:g} / {p:.2f})"
                  + (f" to the power {b.elasticity:g}" if b.elasticity != 1 else "") + ")",
                  f"{wu:.1f} a week, {wu * 52:,.0f} a year", ASSUMED))
    s.append(step("Est. GMV a year", f"{wu * 52:,.0f} units x {_gbp(p)}", _gbp(c["gmv_annual"], 0), WORKED))
    s.append(step("If The Range stocks it (1P): money kept per sale", f"{_gbp(p)} / {1 + a.vat_rate:.2f} (VAT goes to HMRC)",
                  _gbp(net), REAL))
    s.append(step("less cost of the goods", f"{b.cogs_pct:.0%} of {_gbp(net)}", "-" + _gbp(c["cogs"]), ASSUMED))
    s.append(step("less pick, pack and delivery", "per order", "-" + _gbp(c["fulfilment_cost"]), ASSUMED))
    s.append(step("less refunds and clearance discounts",
                  f"returns {c['return_rate']:.0%} + markdowns {c['markdown_rate']:.0%} of {_gbp(net)}",
                  "-" + _gbp(net * (c["return_rate"] + c["markdown_rate"])), ASSUMED))
    s.append(step("less physical storage, insurance and shrink", f"{_gbp(c['cogs'])} x {a.holding_rate:.0%} a year x "
                  f"{c['stock_cover_days']:.0f} days / 365 (cost of capital is not in this line; it is tested only by the hurdle)", "-" + _gbp(c["holding_cost_unit"]), ASSUMED))
    s.append(step("= 1P contribution per unit", "the lines above", _gbp(c["contrib_1p_unit"]), WORKED))
    s.append(step("If the partner keeps selling it (3P): commission", f"{c['commission_rate']:.0%} of {_gbp(p)} "
                  f"(published rate) - {_gbp(a.marketplace_cost_per_unit)} cost to serve the sale",
                  _gbp(c["contrib_3p_unit"]), REAL + " and " + ASSUMED.lower()))
    sub = c["substitute_1p_contrib"]
    if sub > 0:
        sw = (f"{c['diversion_rate']:.0%} of these buyers would otherwise buy The Range's own similar item (median "
              f"price {_gbp(c['substitute_1p_price'])}), which makes {_gbp(sub)} a unit: {c['diversion_rate']:.0%} x "
              f"{_gbp(sub)}")
    else:
        sw = (f"The Range's own similar item (median price {_gbp(c['substitute_1p_price'])}) makes no contribution "
              f"({_gbp(sub)} a unit), so the partner's sales cost The Range nothing")
    s.append(step("less sales taken from The Range's own range", sw,
                  ("-" + _gbp(c["diversion_rate"] * sub)) if sub > 0 else "£0.00", ASSUMED))
    s.append(step("= 3P value per unit", "commission less the lost own sales", _gbp(c["net_3p_unit"]), WORKED))
    s.append(step("1P advantage a year", f"({_gbp(c['contrib_1p_unit'])} - {_gbp(c['net_3p_unit'])}) x "
                  f"{wu * 52:,.0f} units", _gbp(c["advantage_1p_annual"], 0), WORKED))
    s.append(step("Return on the money tied up in stock", f"1P contribution a year {_gbp(c['contrib_1p_unit'] * wu * 52, 0)} / "
                  f"average stock value {_gbp(c['avg_inventory_value'], 0)} ({c['stock_cover_days']:.0f} days of stock at "
                  f"cost)", f"{c['return_on_capital']:.0%} (needs at least {a.hurdle_rate:.0%})", POLICY))
    s.append(step("How much demand swings week to week", f"assumed {c['weekly_units_cv']:.0%} of the average; above "
                  f"{a.volatility_cv_threshold:.0%} means test as 3P first", f"{c['weekly_units_cv']:.0%}", ASSUMED))
    s.append(step("Decision", decision_sentence(c, a), c["recommendation"], WORKED))
    return s


def decision_sentence(c: dict, a: Assumptions) -> str:
    rule = c["rule"]
    return {
        "volatile_demand": "demand swings too much to commit stock, so test with the partner first",
        "near_threshold": f"1P and 3P, or the return and the {a.hurdle_rate:.0%} hurdle, are within "
                          f"{a.near_threshold_band:.0%} of each other, so test first",
        "1p_wins": f"1P makes more contribution per unit and the return on stock clears {a.hurdle_rate:.0%}",
        "3p_wins_margin_and_roc": "3P is worth more contribution per unit and the return on stock is below the hurdle",
        "3p_wins_margin": "3P is worth more contribution per unit",
        "roc_below_hurdle": f"1P makes more contribution per unit but the return on stock is below {a.hurdle_rate:.0%}",
    }.get(rule, rule)


def decision_rules(a: Assumptions | None = None) -> list[str]:
    a = a or Assumptions()
    return [
        f"If weekly demand swings by more than the volatility limit ({a.volatility_cv_threshold:.0%} of the average), test as 3P first.",
        f"If 1P and 3P contribution are within {a.near_threshold_band:.0%} of each other, or the return on stock is within {a.near_threshold_band:.0%} of the hurdle, test as 3P first.",
        f"If 1P makes more contribution per unit than 3P and the return on stock beats the {a.hurdle_rate:.0%} hurdle, bring it in-house.",
        "Otherwise keep it with the partner (3P).",
    ]


# Default wording, used where assumptions are the defaults.
DECISION_RULES = decision_rules()


HOLDING_SPLIT_TEXT = """
The cost of holding stock used to be treated twice. A 20% holding rate (which mixed the cost of the
money tied up with warehouse space, insurance and shrink) was subtracted from 1P contribution, and
then return on stock, which is that same contribution for a year divided by the stock value, was
tested against a 25% hurdle. The cost of money was in both steps, so the in-house test was stricter
than it needed to be.

The two things are now split:

- Contribution only takes off the physical cost of holding stock: warehouse space, insurance and
  shrink. The default is 8% of the cost of the goods, for the days the goods sit in stock. That 8%
  is an assumption you can edit. Markdowns already have their own line, so they are not inside the 8%.
- The cost of capital is handled only by the hurdle. Return on stock is a year's 1P contribution
  divided by the average stock value, and it has to beat the hurdle (25% by default, also an
  assumption you can edit).

The 8% is my judgement of the physical part of the old 20% bundle, not a measured split. A firm
would use its own warehouse and shrink figures.
""".strip()


HURDLE_TEXT = """
The 25% hurdle is an assumption, not a figure from The Range or from an industry rulebook. Firms set
their own bar, usually their cost of capital plus a cushion for risk. You can change it in the sidebar.

There is a related retail measure, GMROI (gross margin return on inventory investment): a year's
gross profit (sales less cost of goods only) divided by average stock at cost. A Shopify article
updated on 18 July 2026, which I opened, calculated GMROI from public company filings and the
figures ranged from 1.82 (Best Buy, consumer electronics) to 6.08 (Abercrombie & Fitch, apparel),
with Ulta Beauty at 2.36 and Home Depot at 2.23. Shopify does not give a single retail target; it
says a good GMROI depends on the category, and that a figure above 1 only means gross profit
exceeded average stock at cost. Source: https://www.shopify.com/blog/gmroi

GMROI is not the same as this tool's return on stock. GMROI uses gross profit. This tool uses
contribution after fulfilment, returns, markdowns and physical holding, so the figures are not
directly comparable and no published GMROI number is used as the hurdle. In this sample, listings
recommended in-house already show return on stock well above 100%, so 25%, 50% and 100% all give
the same recommendations. A bar in the region of 150% to 200% starts to change the answer. The
sensitivity table shows that.
""".strip()


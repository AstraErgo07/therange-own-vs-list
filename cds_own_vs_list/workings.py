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
    s.append(step("less cost of holding stock", f"{_gbp(c['cogs'])} x {a.holding_rate:.0%} a year x "
                  f"{c['stock_cover_days']:.0f} days / 365", "-" + _gbp(c["holding_cost_unit"]), ASSUMED))
    s.append(step("= 1P profit per unit", "the lines above", _gbp(c["contrib_1p_unit"]), WORKED))
    s.append(step("If the partner keeps selling it (3P): commission", f"{c['commission_rate']:.0%} of {_gbp(p)} "
                  f"(published rate) - {_gbp(a.marketplace_cost_per_unit)} cost to serve the sale",
                  _gbp(c["contrib_3p_unit"]), REAL + " and " + ASSUMED.lower()))
    sub = c["substitute_1p_contrib"]
    if sub > 0:
        sw = (f"{c['diversion_rate']:.0%} of these buyers would otherwise buy The Range's own similar item (median "
              f"price {_gbp(c['substitute_1p_price'])}), which makes {_gbp(sub)} a unit: {c['diversion_rate']:.0%} x "
              f"{_gbp(sub)}")
    else:
        sw = (f"The Range's own similar item (median price {_gbp(c['substitute_1p_price'])}) makes no profit "
              f"({_gbp(sub)} a unit), so the partner's sales cost The Range nothing")
    s.append(step("less sales taken from The Range's own range", sw,
                  ("-" + _gbp(c["diversion_rate"] * sub)) if sub > 0 else "£0.00", ASSUMED))
    s.append(step("= 3P value per unit", "commission less the lost own sales", _gbp(c["net_3p_unit"]), WORKED))
    s.append(step("1P advantage a year", f"({_gbp(c['contrib_1p_unit'])} - {_gbp(c['net_3p_unit'])}) x "
                  f"{wu * 52:,.0f} units", _gbp(c["advantage_1p_annual"], 0), WORKED))
    s.append(step("Return on the money tied up in stock", f"1P profit a year {_gbp(c['contrib_1p_unit'] * wu * 52, 0)} / "
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
        "1p_wins": f"1P makes more per unit and the return on stock clears {a.hurdle_rate:.0%}",
        "3p_wins_margin_and_roc": "3P is worth more per unit and the return on stock is below the hurdle",
        "3p_wins_margin": "3P is worth more per unit",
        "roc_below_hurdle": f"1P makes more per unit but the return on stock is below {a.hurdle_rate:.0%}",
    }.get(rule, rule)


DECISION_RULES = [
    "If weekly demand swings by more than the volatility limit (50% of the average), test as 3P first.",
    "If 1P and 3P are within 10% of each other, or the return on stock is within 10% of the hurdle, test as 3P first.",
    "If 1P makes more per unit than 3P and the return on stock beats the 25% hurdle, bring it in-house.",
    "Otherwise keep it with the partner (3P).",
]

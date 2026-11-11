"""
cds_own_vs_list/agent.py - explains each Own vs List recommendation for The Range.

The LLM receives the calculated numbers, told which are REAL and which are ESTIMATES,
and must use only those. No key / error / bad JSON -> rules-based explanation.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if not __package__:  # only when run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.llm import LLMUnavailable, call_llm, extract_json_object, validate_common  # noqa: E402
try:  # imported as part of a package (the Streamlit app)
    from .calc import (BRING_IN_HOUSE, KEEP_3P, RECOMMENDATIONS, TEST_3P_FIRST, Assumptions, ESTIMATED_FIELDS)
except ImportError:  # run directly: python agent.py
    from calc import (BRING_IN_HOUSE, KEEP_3P, RECOMMENDATIONS, TEST_3P_FIRST, Assumptions, ESTIMATED_FIELDS)

REQUIRED_KEYS = ["recommendation", "reason", "confidence", "additional_data", "seller_question"]
CONFIDENCE = ["low", "medium", "high"]


def _numbers(c: dict, a: Assumptions) -> dict:
    r2 = lambda x: None if x is None else round(float(x), 2)  # noqa: E731
    return {
        "sku": c["sku"], "title": c["title"], "category": c["category"], "marketplace_seller": c["sold_by"],
        "REAL": {"shelf_price_gbp_inc_vat": c["price"], "commission_rate_published": c["commission_rate"],
                 "range_own_1p_substitute_median_price_gbp": r2(c["substitute_1p_price"])},
        "ESTIMATED_from_category_benchmarks": {
            "cogs_gbp": r2(c["cogs"]), "fulfilment_cost_gbp": c["fulfilment_cost"], "return_rate": c["return_rate"],
            "markdown_rate": c["markdown_rate"], "stock_cover_days": c["stock_cover_days"],
            "weekly_units": r2(c["weekly_units"]), "weekly_units_cv": c["weekly_units_cv"]},
        "CALCULATED": {
            "price_ex_vat_gbp": r2(c["price_ex_vat"]), "contribution_1p_per_unit_gbp": r2(c["contrib_1p_unit"]),
            "contribution_3p_per_unit_gbp": r2(c["contrib_3p_unit"]),
            "substitute_1p_contribution_gbp": r2(c["substitute_1p_contrib"]),
            "net_3p_benefit_per_unit_gbp": r2(c["net_3p_unit"]), "return_on_capital": round(c["return_on_capital"], 3),
            "annual_gmv_gbp_estimate": round(c["gmv_annual"], 0),
            "rule_based_recommendation": c["recommendation"], "rule_fired": c["rule"]},
        "assumptions": {"vat_rate": a.vat_rate, "holding_rate": a.holding_rate, "hurdle_rate": a.hurdle_rate,
                        "marketplace_cost_per_unit_gbp": a.marketplace_cost_per_unit,
                        "diversion_rate": c["diversion_rate"], "volatility_cv_threshold": a.volatility_cv_threshold,
                        "near_threshold_band": a.near_threshold_band},
    }


def build_prompt(c: dict, a: Assumptions) -> str:
    nums = json.dumps(_numbers(c, a), indent=2, default=str)
    return f"""A category manager at The Range (CDS Superstores, UK) is deciding whether a product currently sold
by a marketplace partner (3P) should be bought and stocked by The Range itself (1P), kept on the marketplace,
or tested first. You support the decision; the manager makes it.

Definitions: 1P contribution = ex-VAT price - cogs - fulfilment - returns - markdown - holding cost.
3P contribution = shelf price x commission - marketplace cost. Net 3P = 3P contribution - diversion x the 1P
contribution of The Range's own substitute (median price of its own listings in the category).
Return on capital = annual 1P contribution / average stock value.

NUMBERS (use ONLY these; do not invent costs, sales, competitor or seller facts):
{nums}

Rules:
- Use only the numbers above. Make clear that cost, returns, markdown, units and stock cover are ESTIMATES.
- If the estimates drive the answer or the data is insufficient, say so and lower the confidence.

Reply with ONE JSON object and nothing else, with exactly these keys:
{{
  "recommendation": one of "Bring in-house", "Keep 3P", "Test as 3P first",
  "reason": "two short lines of plain-English commercial reasoning, separated by a newline",
  "confidence": one of "low", "medium", "high",
  "additional_data": "what additional data would change the answer",
  "seller_question": "one question the category manager should ask the seller"
}}"""


def parse_llm_json(text: str) -> dict:
    out = validate_common(extract_json_object(text), REQUIRED_KEYS,
                          {"recommendation": RECOMMENDATIONS, "confidence": CONFIDENCE})
    out["reason"] = "\n".join([ln.strip() for ln in out["reason"].splitlines() if ln.strip()][:2])
    return out


def _gbp(x):
    return f"£{x:,.2f}"


def rules_explanation(c: dict, a: Assumptions) -> dict:
    rec, rule = c["recommendation"], c["rule"]
    c1p, n3p, roc = c["contrib_1p_unit"], c["net_3p_unit"], c["return_on_capital"]
    cogs_note = f"cost price is an estimate ({_gbp(c['cogs'])}, {c['cogs'] / c['price_ex_vat']:.0%} of ex-VAT price)"
    if rec == BRING_IN_HOUSE:
        l1 = f"Owning it earns ~{_gbp(c1p)}/unit vs {_gbp(n3p)} net from commission, with ~{roc:.0%} return on stock."
        l2 = f"But the {cogs_note}; confirm it before buying."
        conf = "medium" if c1p > 1.5 * n3p else "low"
        more = "The real supplier cost price, MOQ and lead time; actual weekly sales from the seller."
        q = f"Would {c['sold_by']} (or their supplier) sell to The Range wholesale, and at what cost and minimum order?"
    elif rec == TEST_3P_FIRST:
        if rule == "volatile_demand":
            l1 = f"Demand in {c['category']} is treated as seasonal (cv {c['weekly_units_cv']:.2f} > {a.volatility_cv_threshold:.2f})."
            l2 = f"Keep it on the marketplace through a season: 1P {_gbp(c1p)} vs net 3P {_gbp(n3p)} per unit is not worth the stock risk yet."
            more = "Actual weekly sales across a full season from the seller."
            q = "What did this sell week by week last spring and summer?"
        else:
            l1 = f"Too close to call: 1P {_gbp(c1p)}/unit vs net 3P {_gbp(n3p)} is inside the {a.near_threshold_band:.0%} band."
            l2 = f"The {cogs_note}, so a small cost difference flips it - test first and get the real cost."
            more = "Real cost price and sell-through; a 1-2 point change in cost or returns changes the answer."
            q = "What landed cost could you offer if we bought in volume?"
        conf = "low"
    else:
        l1 = f"Commission earns ~{_gbp(n3p)}/unit net vs {_gbp(c1p)} if we owned it - the seller carries the stock and returns."
        l2 = (f"Fixed fulfilment (~{_gbp(c['fulfilment_cost'])}) eats the 1P margin at a {_gbp(c['price'])} price."
              if c["fulfilment_cost"] > 0.15 * c["price_ex_vat"] else f"Note: the {cogs_note}.")
        conf = "high" if n3p > 2 * max(c1p, 0.01) else "medium"
        more = "A much lower cost price or cheaper fulfilment would strengthen the 1P case."
        q = "Can you keep stock deep and delivery fast so the listing keeps converting?"
    return {"recommendation": rec, "reason": f"{l1}\n{l2}", "confidence": conf,
            "additional_data": more, "seller_question": q}


def explain(c: dict, a: Assumptions) -> dict:
    try:
        out = parse_llm_json(call_llm(build_prompt(c, a)))
        out.update(source="llm", note="")
    except LLMUnavailable as e:
        out = rules_explanation(c, a)
        out.update(source="rules", note=str(e))
    except (ValueError, json.JSONDecodeError) as e:
        out = rules_explanation(c, a)
        out.update(source="rules", note=f"LLM reply rejected ({e}); using rules-based explanation")
    except Exception as e:
        out = rules_explanation(c, a)
        out.update(source="rules", note=f"Unexpected error ({type(e).__name__}: {e})")
    out["rule_recommendation"] = c["recommendation"]
    return out


if __name__ == "__main__":
    from calc import evaluate_portfolio, load_listings
    a = Assumptions()
    res = evaluate_portfolio(load_listings(Path(__file__).parent / "range_listings.csv"), a)
    print("LLM key set:", bool(os.environ.get("OPENAI_API_KEY")))
    seen = set()
    for c in res.to_dict("records"):
        key = (c["recommendation"], c["rule"])
        if key in seen:
            continue
        seen.add(key)
        out = explain(c, a)
        print("\n" + "=" * 70)
        print(f"{c['sku']} {c['title']} (£{c['price']}, {c['sold_by']}) source={out['source']}")
        print(json.dumps({k: out[k] for k in REQUIRED_KEYS + ['rule_recommendation']}, indent=2, ensure_ascii=False))

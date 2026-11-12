"""
CDS Own vs List - should The Range bring a marketplace (3P) product in-house (1P), keep it 3P, or test first?
Numbers: cds_own_vs_list/calc.py. Explanations: cds_own_vs_list/agent.py. You accept or override.
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.decisions import load_decisions, now, save_decision  # noqa: E402
from common.text import VERSION  # noqa: E402
from cds_own_vs_list.agent import explain  # noqa: E402
from cds_own_vs_list.calc import (BRING_IN_HOUSE, CATEGORIES, COMMISSION_REAL, ESTIMATED_FIELDS,  # noqa: E402
                                  RECOMMENDATIONS, Assumptions, default_benchmarks, evaluate_portfolio,
                                  gmv_vs_contribution_flags, hurdle_sensitivity, load_listings, seller_summary,
                                  sensitivity, substitute_prices)
from cds_own_vs_list.insights import category_breakdown, insights  # noqa: E402
from cds_own_vs_list.workings import (DECISION_RULES, HOLDING_SPLIT_TEXT, HURDLE_TEXT,  # noqa: E402
                                      decision_rules, own_vs_list_workings)

DATA = ROOT / "cds_own_vs_list" / "range_listings.csv"
LOG = ROOT / "cds_own_vs_list" / "decisions.csv"
LOG_COLS = ["timestamp", "sku", "title", "category", "sold_by", "model_recommendation", "final_decision",
            "action", "reason", "explanation_source", "assumptions"]


def sidebar() -> Assumptions:
    d = Assumptions()
    sb = st.sidebar
    sb.header("Assumptions")
    sb.caption("🟢 = real/published  ·  🟠 = estimate (category benchmark)  ·  ⚙️ = policy")
    hurdle = sb.slider("🟠 Minimum yearly return on money tied up in stock (hurdle)", 0.0, 3.0, d.hurdle_rate, 0.01, format="%.2f")
    sb.caption("Assumption. Firms set their own bar (cost of capital plus a cushion). 25% is my starting point, not a published standard. See the hurdle note on the page.")
    holding = sb.slider("🟠 Physical holding rate (storage, insurance and shrink, % of stock cost a year)", 0.0, 0.5, d.holding_rate, 0.01, format="%.2f")
    sb.caption("Assumption. Cost of capital is not in this figure; it is tested only by the hurdle. See the method note on the page.")
    mkt = sb.slider("⚙️ Marketplace cost per 3P unit (£)", 0.0, 3.0, d.marketplace_cost_per_unit, 0.05)
    vat = sb.slider("🟢 VAT rate (shelf prices include it)", 0.0, 0.25, d.vat_rate, 0.01, format="%.2f")
    sb.subheader("⚙️ Diversion rate by category")
    sb.caption("Share of 3P sales that would otherwise buy The Range's own 1P substitute.")
    div = {c: sb.slider(c.title(), 0.0, 1.0, d.diversion_for(c), 0.05, key=f"cds_div_{c}") for c in CATEGORIES}
    with sb.expander("🟢 Commission (The Range published fees)"):
        com = {c: st.slider(c.title(), 0.0, 0.25, COMMISSION_REAL[c], 0.01, format="%.2f", key=f"cds_com_{c}")
               for c in CATEGORIES}
    sb.subheader("🟠 Category benchmarks (estimates)")
    bench = {}
    for c, b in default_benchmarks().items():
        with sb.expander(c.title()):
            bench[c] = replace(
                b,
                cogs_pct=st.slider("Cost price, % of ex-VAT price", 0.1, 0.9, b.cogs_pct, 0.01, key=f"b_cogs_{c}"),
                fulfilment_cost=st.slider("Fulfilment £/unit", 0.0, 80.0, b.fulfilment_cost, 0.25, key=f"b_ful_{c}"),
                return_rate=st.slider("Return rate", 0.0, 0.3, b.return_rate, 0.01, key=f"b_ret_{c}"),
                markdown_rate=st.slider("Markdown rate", 0.0, 0.4, b.markdown_rate, 0.01, key=f"b_md_{c}"),
                stock_cover_days=st.slider("Stock cover (days)", 7, 180, int(b.stock_cover_days), 1, key=f"b_cov_{c}"),
                ref_weekly_units=st.slider(f"Weekly units at £{b.ref_price:.0f}", 0.5, 100.0, float(b.ref_weekly_units), 0.5, key=f"b_u_{c}"),
                elasticity=st.slider("How fast units fall as price rises (1 = units halve when price doubles)", 0.0, 3.0, b.elasticity, 0.1, key=f"b_el_{c}"),
                weekly_units_cv=st.slider("Week-to-week demand swing (share of average)", 0.0, 1.5, b.weekly_units_cv, 0.05, key=f"b_cv_{c}"),
            )
    with sb.expander("Test-first triggers (policy)"):
        vol = st.slider("Test first if weekly demand swings by more than (share of average)", 0.0, 2.0, d.volatility_cv_threshold, 0.05)
        band = st.slider("Too close to call if within (share)", 0.0, 0.5, d.near_threshold_band, 0.01, format="%.2f")
    return Assumptions(holding_rate=holding, vat_rate=vat, hurdle_rate=hurdle, marketplace_cost_per_unit=mkt,
                       diversion_rates=div, volatility_cv_threshold=vol, near_threshold_band=band,
                       commission_rates=com, benchmarks=bench)


def get_expl(c: dict, a: Assumptions) -> dict:
    cache = st.session_state.setdefault("cds_expl", {})
    key = (c["sku"], a.to_json())
    if key not in cache:
        with st.spinner("Drafting the explanation..."):
            cache[key] = explain(c, a)
    return cache[key]


def table(res: pd.DataFrame) -> pd.DataFrame:
    units = res["weekly_units"] * 52
    return pd.DataFrame({
        "Rank": res["rank"], "SKU": res["sku"], "Product": res["title"].str.slice(0, 50),
        "Category": res["category"], "Seller (real)": res["sold_by"],
        "🟠 Est. units/year": units.round(0),
        "🟢 Avg selling price per unit (£)": res["price"].round(2),
        "🟠 Est. GMV/year (£)": res["gmv_annual"].round(0),
        "🟠 1P contribution £/unit": res["contrib_1p_unit"].round(2), "🟠 3P value £/unit": res["net_3p_unit"].round(2),
        "🟠 1P advantage £/yr": res["advantage_1p_annual"].round(0),
        "🟠 Return on stock money %": (res["return_on_capital"] * 100).round(0), "Recommendation": res["recommendation"],
    })

a = sidebar()
try:
    listings = load_listings(DATA)
    res = evaluate_portfolio(listings, a)
    subs = substitute_prices(listings)
except Exception:   # show the problem on the page instead of a blank or crashed app
    st.error("Something went wrong loading or calculating the data. Details:")
    st.code(traceback.format_exc())
    st.caption(f"Own vs List {VERSION}")
    st.stop()

st.title("Own vs List: The Range (CDS)")
st.caption(f"Own vs List {VERSION}")
st.markdown("Should The Range buy and stock (1P) a product that a marketplace partner currently sells (3P), keep it "
            "on the marketplace, or test first? Built on real The Range listings, with labelled estimates for the "
            "costs The Range does not publish. The calculations are plain-Python rules; an LLM, if configured, only "
            "drafts the explanation. You make the call. Small sample: a test of the method, not market sizing.")
st.info(f"Real: {len(listings)} therange.co.uk listings ({(listings.listing_type == '3P').sum()} marketplace, "
        f"{(listings.listing_type == '1P').sum()} sold by The Range): price, sold-by, seller (labelled); published commission "
        "rates; The Range's own substitute prices. Estimated (🟠): " + ", ".join(ESTIMATED_FIELDS) +
        ". Category benchmarks can be changed in the sidebar.", icon="ℹ️")

counts = res["recommendation"].value_counts()
for col, rec in zip(st.columns(3), RECOMMENDATIONS):
    col.metric(rec, int(counts.get(rec, 0)))

st.subheader("Insights from this sample")
st.caption("These observations are taken from the model at the default assumptions, not from the sliders. "
           "Every claim is worded as a finding in this sample under those assumptions, not as a business result.")
default_a = Assumptions()
for bullet in insights(listings, default_a):
    st.markdown(f"- {bullet}")
with st.expander("Counts by category at the default assumptions"):
    st.dataframe(category_breakdown(evaluate_portfolio(listings, default_a)), hide_index=True, width="stretch")
with st.expander("How holding cost and the hurdle are split (method)"):
    st.markdown(HOLDING_SPLIT_TEXT)
with st.expander("Why the hurdle is 25%, and what a typical bar looks like"):
    st.markdown(HURDLE_TEXT)

st.subheader("Ranked marketplace (3P) products")
st.caption("GMV = units × average selling price (the shelf price). Ranked by 1P advantage a year = (1P contribution "
           "per unit − 3P value per unit) × units a year. Click a row to see its workings and the drafted reasoning.")
with st.expander("How these numbers are worked out"):
    st.markdown("Decision rules, in order:")
    for r in decision_rules(a):
        st.markdown(f"- {r}")
    st.markdown("Worked example: the top-ranked product with the current sliders. Pick any product further down "
                "the page to see its own workings.")
    top = res.iloc[0].to_dict()
    st.markdown(f"{top['sku']}: {top['title']}")
    st.table(pd.DataFrame(own_vs_list_workings(top, a)).rename(columns=str.capitalize).set_index("Step"))
event = st.dataframe(table(res), hide_index=True, width="stretch", on_select="rerun",
                     selection_mode="single-row", key="cds_table",
                     column_config={"🟠 Return on stock money %": st.column_config.NumberColumn(format="%d%%"),
                                    "🟠 Est. GMV/year (£)": st.column_config.NumberColumn(format="£%d")})

flags = gmv_vs_contribution_flags(res, a)
st.subheader("Products with big sales where the contribution maths still says keep them 3P")
with st.container(border=True):
    st.caption(f"Estimated GMV in the top quartile (≥ £{res['gmv_annual'].quantile(a.gmv_flag_quantile):,.0f}/yr) "
               "but contribution per unit and return on stock do not recommend 'Bring in-house'.")
    if flags.empty:
        st.success("None at the current assumptions.")
    else:
        st.warning(f"{len(flags)} high-GMV product(s) where big sales don't translate into a 1P case.")
        st.dataframe(table(flags).drop(columns=["Rank"]), hide_index=True, width="stretch")

st.subheader("Sensitivity: how many recommendations flip?")
summ, flipped, _ = sensitivity(listings, a)
st.caption("Diversion rows set every category to that rate (the share of partner buyers who would otherwise buy "
           "The Range's own item). COGS (cost of goods) rows move every category's cost-price estimate by ±10 points. Cost is the biggest unknown without supplier data.")
st.dataframe(summ.rename(columns={"scenario": "Scenario", "flipped_vs_current": "Flipped vs current"}),
             hide_index=True, width="stretch")
st.markdown("**If only the return-on-stock hurdle changes**")
st.caption("25%, 50% and 100% are illustration points, not industry standards. 150% and 200% are included "
           "because in this sample the lower bars often do not change the answer. Compared with the hurdle "
           "currently set in the sidebar.")
hsumm, hflipped, _ = hurdle_sensitivity(listings, a, hurdles=(0.25, 0.50, 1.00, 1.50, 2.00))
st.dataframe(hsumm.drop(columns=["hurdle"]).rename(
    columns={"scenario": "Scenario", "flipped_vs_current": "Flipped vs current"}),
    hide_index=True, width="stretch")
with st.expander("Which products flip?"):
    for k, items in {**flipped, **hflipped}.items():
        st.markdown(f"**{k}:** " + (", ".join(items) if items else "no changes"))

# Detail ---------------------------------------------------------------------
st.subheader("Product detail and your decision")
skus = res["sku"].tolist()
rows = event.selection.rows if event is not None and hasattr(event, "selection") else []
picked = skus[rows[0]] if rows else None
if picked and st.session_state.get("_cds_last") != picked:
    st.session_state["cds_pick"] = picked
st.session_state["_cds_last"] = picked
names = dict(zip(res["sku"], res["title"]))
sku = st.selectbox("Product", skus, format_func=lambda s: f"{s}: {names[s]}", key="cds_pick")
c = res[res["sku"] == sku].iloc[0].to_dict()
expl = get_expl(c, a)

left, right = st.columns([3, 2])
with left:
    src = "🤖 LLM" if expl["source"] == "llm" else "📏 Rules-based (no LLM)"
    st.markdown(f"**Calculated:** {c['recommendation']}  \n**Drafted view:** {expl['recommendation']} · "
                f"confidence **{expl['confidence']}** · source {src}")
    if expl.get("note"):
        st.caption(expl["note"])
    if expl["recommendation"] != c["recommendation"]:
        st.info("The drafted explanation disagrees with the calculated recommendation. Worth a closer look.")
    st.markdown("**Why:**  \n" + expl["reason"].replace("\n", "  \n"))
    st.markdown(f"**What data would change the answer:** {expl['additional_data']}")
    st.markdown(f"**Ask the seller:** {expl['seller_question']}")
    st.markdown(f"[Open the listing on therange.co.uk]({c['url']})" + ("  ✓ page verified" if c["verified"] else
                "  (read from search-index snapshot)"))
with right:
    st.markdown("**Workings, step by step**")
    st.table(pd.DataFrame(own_vs_list_workings(c, a)).rename(columns=str.capitalize).set_index("Step"))

with st.container(border=True):
    st.markdown(f"**Your decision for {sku}**. The model recommends *{c['recommendation']}*")
    reason = st.text_area("Reason (required to override)", key=f"cds_reason_{sku}")
    alt = st.selectbox("If overriding, your decision", [r for r in RECOMMENDATIONS if r != c["recommendation"]],
                       key=f"cds_alt_{sku}")
    b1, b2 = st.columns(2)
    base = {"timestamp": now(), "sku": sku, "title": c["title"], "category": c["category"], "sold_by": c["sold_by"],
            "model_recommendation": c["recommendation"], "reason": reason.strip(),
            "explanation_source": expl["source"], "assumptions": a.to_json()}
    if b1.button("✅ Accept recommendation", key=f"cds_acc_{sku}", width="stretch"):
        save_decision(dict(base, final_decision=c["recommendation"], action="accept"), LOG, LOG_COLS)
        st.success(f"Saved: accepted '{c['recommendation']}' for {sku}.")
    if b2.button("✏️ Override", key=f"cds_ovr_{sku}", width="stretch"):
        if not reason.strip():
            st.error("Please give a reason for the override.")
        else:
            save_decision(dict(base, final_decision=alt, action="override"), LOG, LOG_COLS)
            st.success(f"Saved: overrode to '{alt}' for {sku}.")

st.subheader("Marketplace sellers in the sample")
ss = seller_summary(res)
units_y = res.assign(u=res["weekly_units"] * 52).groupby("sold_by")["u"].sum()
ss = ss.assign(units=ss["sold_by"].map(units_y))
ss = ss.assign(avg=ss["est_gmv_annual"] / ss["units"])
st.dataframe(pd.DataFrame({
    "Seller (real)": ss["sold_by"], "Listings": ss["listings"], "🟠 Est. units/year": ss["units"].round(0),
    "🟠 Avg selling price per unit (£)": ss["avg"].round(2), "🟠 Est. GMV/year (£)": ss["est_gmv_annual"].round(0),
    "Recommended in-house": ss["bring_in_house"], "Categories": ss["categories"]}),
    hide_index=True, width="stretch")
st.caption("Avg selling price per unit = the seller's GMV ÷ their units, so it is weighted by what sells.")

with st.expander("The Range's own (1P) listings used as substitutes (real)"):
    st.caption("Median price per category = the 1P substitute in the cannibalisation calculation.")
    st.write({k: f"£{v:.2f}" for k, v in subs.items()})
    st.dataframe(listings[listings.listing_type == "1P"][["sku", "category", "title", "price", "url"]],
                 hide_index=True, width="stretch")

with st.expander("Data sources and assumptions (short version; full page in the menu)"):
    st.markdown("""
- **Real (therange.co.uk, read 11 Nov 2026):** price, "Sold & Shipped by <partner>" vs "sold by The Range", seller (names replaced by labels).
  Pages were read with an automated page-reading tool, one at a time, no logins, robots.txt respected.
  Pages marked *verified* were read directly; the rest come from search-engine snapshots of the same product page
  and were cross-checked against the live category listing page where possible.
- **Real (published):** The Range marketplace commission, Feb 2026: Home Furnishings 13%, Cooking & Dining 15%,
  Outdoor Living 14%, Health & Beauty 13% (marketplacetherange.zendesk.com). UK VAT 20%.
- **Estimated (🟠):** cost price, fulfilment, returns, markdown, stock cover, weekly units, demand volatility:
  category benchmarks (my judgement for UK value home retail, not CDS data). The Range shows almost no review
  counts, so units come from a price curve, not reviews.
- **Assumptions (🟠):** physical holding rate (storage, insurance and shrink only; default 8%);
  hurdle on return on stock (default 25%, a firm's own bar, not a published standard); diversion rates;
  marketplace cost per unit. Cost of capital is not subtracted from contribution; it is tested only by the hurdle.
""")

st.subheader("Decision log (cds_own_vs_list/decisions.csv)")
log = load_decisions(LOG, LOG_COLS)
if log.empty:
    st.caption("No decisions saved yet.")
else:
    st.dataframe(log.drop(columns=["assumptions"]).iloc[::-1], hide_index=True, width="stretch")

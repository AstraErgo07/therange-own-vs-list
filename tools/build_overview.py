"""
tools/build_overview.py - writes docs/OVERVIEW.md, a plain markdown write-up of the Own vs List tool, from the code.

Every number comes from the same functions the app uses, at the default settings, so the document matches the app.
Run:
    python tools/build_overview.py                     # writes docs/OVERVIEW.md
    python tools/build_overview.py --pdf out.pdf       # also renders a PDF (needs the 'markdown' package and Chrome)
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cds_own_vs_list.calc import (RECOMMENDATIONS, Assumptions as RangeAssumptions, COMMISSION_REAL,  # noqa: E402
                                  default_benchmarks, evaluate_portfolio, load_listings,
                                  seller_summary, sensitivity)
from cds_own_vs_list.workings import DECISION_RULES, own_vs_list_workings  # noqa: E402
from common.text import FOOTER, VERSION  # noqa: E402

OUT = ROOT / "docs" / "OVERVIEW.md"
REPO = "https://github.com/AstraErgo07/therange-own-vs-list"


def steps_markdown(steps: list[dict]) -> str:
    """Markdown table (plain, readable without JavaScript)."""
    out = ["| Step | Working | Result | Source |", "|---|---|---|---|"]
    for st_ in steps:
        out.append(f"| {st_['step']} | {st_['working']} | {st_['result']} | {st_['source']} |")
    return "\n".join(out)


def md_table(df: pd.DataFrame) -> str:
    """Plain markdown table. Prices to the penny, monthly units to one decimal, other £ and counts whole."""
    def fmt(col):
        c = col.lower()
        if "price" in c or "/unit" in c:
            return 2
        if "units/month" in c:
            return 1
        return 0

    def cell(v, dp):
        if isinstance(v, (float, int)) and not isinstance(v, bool):
            if isinstance(v, float) and math.isnan(v):
                return ""
            return f"{v:,.{dp}f}" if isinstance(v, float) else f"{v:,}"
        return str(v).replace("|", "/")
    dps = [fmt(c) for c in df.columns]
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(cell(v, d) for v, d in zip(row, dps)) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)

def gbp(x, dp=0):
    return f"£{x:,.{dp}f}"


def range_section() -> list[str]:
    a = RangeAssumptions()
    listings = load_listings(ROOT / "cds_own_vs_list" / "range_listings.csv")
    res = evaluate_portfolio(listings, a)
    counts = res["recommendation"].value_counts()
    out = ["## Summary at the default settings", "",
           f"{len(listings)} therange.co.uk listings: {(listings.listing_type == '3P').sum()} sold by marketplace "
           f"partners (the candidates) and {(listings.listing_type == '1P').sum()} sold by The Range (used as the "
           "substitute a buyer might otherwise choose). Partner names are replaced with labels. Default settings: "
           + ", ".join(f"{r} {counts.get(r, 0)}" for r in RECOMMENDATIONS) + ".", "",
           "Decision rules, in order:", ""]
    out += [f"{i}. {r}" for i, r in enumerate(DECISION_RULES, 1)] + [""]
    top = res.iloc[0].to_dict()
    out += ["## Worked example: 1P against 3P", "",
            f"Top-ranked product: {top['sku']}, {top['title']} ({top['category']}, sold by {top['sold_by']}).", "",
            steps_markdown(own_vs_list_workings(top, a)), ""]
    t = res.head(10)
    out += ["## Top 10 partner products by 1P advantage", "", md_table(pd.DataFrame({
        "Rank": t["rank"], "Product": t["title"].str.slice(0, 45), "Category": t["category"], "Seller": t["sold_by"],
        "Est. units/year": (t["weekly_units"] * 52).round(0), "Avg selling price per unit (£)": t["price"].round(2),
        "Est. GMV/year (£)": t["gmv_annual"].round(0), "1P profit/unit (£)": t["contrib_1p_unit"].round(2),
        "3P value/unit (£)": t["net_3p_unit"].round(2), "Return on stock": (t["return_on_capital"] * 100).round(0)
        .astype(int).astype(str) + "%", "Recommendation": t["recommendation"]})), ""]
    ss = seller_summary(res)
    uy = res.assign(u=res["weekly_units"] * 52).groupby("sold_by")["u"].sum()
    ss = ss.assign(units=ss["sold_by"].map(uy))
    out += ["## Partners in the sample", "", md_table(pd.DataFrame({
        "Seller": ss["sold_by"], "Listings": ss["listings"], "Est. units/year": ss["units"].round(0),
        "Avg selling price per unit (£)": (ss["est_gmv_annual"] / ss["units"]).round(2),
        "Est. GMV/year (£)": ss["est_gmv_annual"].round(0), "Recommended in-house": ss["bring_in_house"],
        "Categories": ss["categories"]})), ""]
    summ, _, _ = sensitivity(listings, a)
    out += ["## How sensitive is the answer?", "",
            md_table(summ.rename(columns={"scenario": "Scenario", "flipped_vs_current": "Flipped vs default"})), "",
            "Diversion is the share of partner buyers who would otherwise buy The Range's own item; COGS is the cost "
            "of goods. Changing diversion flips few products; moving the cost-price estimate by 10 points flips many. "
            "Supplier cost is the number to get first.", "",
            "Note: where the price curve is set to 1 (home textiles, outdoor, beauty), units fall in exact proportion "
            "as price rises, so every item in that category gets the same GMV a year, for example £19,500 for home "
            "textiles. GMV is therefore not a useful ranking "
            "here; the ranking uses profit per unit and return on stock instead.", ""]
    b = default_benchmarks()
    out += ["## Category assumptions (my judgement for UK value home retail, not CDS data)", "", md_table(pd.DataFrame([{
        "Category": c, "Cost of goods, % of ex-VAT price": f"{v.cogs_pct:.0%}", "Pick, pack, deliver": f"£{v.fulfilment_cost:.2f}",
        "Returns": f"{v.return_rate:.0%}", "Markdowns": f"{v.markdown_rate:.0%}", "Days of stock": v.stock_cover_days,
        "Units a week at reference price": f"{v.ref_weekly_units:g} at £{v.ref_price:g}",
        "Week-to-week demand swing": f"{v.weekly_units_cv:.0%}",
        "Commission (published)": f"{COMMISSION_REAL[c]:.0%}"} for c, v in b.items()])), ""]
    return out


def build() -> str:
    a = RangeAssumptions()
    L = ["# Own vs List (The Range, part of CDS): overview", "",
         f"Version {VERSION}. Generated by `tools/build_overview.py` from the code, at the default settings, so the "
         f"numbers match the app. This is the plain-text version of the Streamlit app. Code: {REPO}.", "",
         "Portfolio project. Made by Ami Sata.", "",
         "## Purpose", "",
         "For each product a marketplace partner sells on therange.co.uk (3P), should The Range buy and stock it "
         "itself (1P), leave it with the partner, or test first? The tool compares the profit per unit of selling it "
         "1P with the value of the 3P sale (commission less marketplace cost, plus the 1P substitute sales it does "
         "not take away), checks the return on the money tied up in stock, and ranks the products. The calculations "
         "are plain Python rules. A person accepts or overrides every recommendation. An LLM is optional and only "
         "drafts the explanation.", "",
         "## What is real and what is assumed", "",
         "| Item | Source |", "|---|---|",
         "| Listings | Real: public therange.co.uk listings (prices, who sells them), partner names replaced with "
         "labels. |",
         "| Commission | Real, published: 13% to 15% by category. VAT 20%. |",
         "| Units sold | Assumed: from a price curve per category (The Range shows almost no reviews). |",
         "| Costs | Assumed: cost of goods, pick-pack-deliver, returns, markdowns, days of stock, units a week, "
         "week-to-week demand swing, share of buyers who would otherwise buy The Range's own item. |",
         "| Policy | Minimum yearly return on stock money " + f"{a.hurdle_rate:.0%}, holding cost {a.holding_rate:.0%} "
         "a year. |",
         "| Where to change them | Sidebar sliders. |", ""]
    L += range_section()
    L += ["## Limits", "",
          "- A small sample of listings: a test of the method, not market sizing.",
          "- Units come from a price curve, and the cost benchmarks are judgement, not CDS data. Every £ figure "
          "scales with them; supplier cost is the number to get first.",
          "- The Range's pages were read with an automated page-reading tool, one at a time, no logins, robots.txt "
          "respected. What The Range's terms say about reuse of content is quoted on the data and method page.", "",
          FOOTER, ""]
    text = "\n".join(L)
    for bad in ("\u2014", "\u2013"):
        assert bad not in text, "dash found"
    return text


def to_pdf(md_text: str, pdf: Path) -> None:
    import markdown  # pip install markdown
    body = markdown.markdown(md_text, extensions=["tables"])
    css = ("body{font-family:Arial,Helvetica,sans-serif;font-size:9.5pt;line-height:1.35;margin:0 6mm}"
           "h1{font-size:18pt}h2{font-size:13pt;margin-top:16pt;border-bottom:1px solid #ccc}h3{font-size:11pt}"
           "table{border-collapse:collapse;margin:6pt 0;font-size:8pt;page-break-inside:auto}"
           "td,th{border:1px solid #bbb;padding:2pt 4pt;vertical-align:top}th{background:#f0f0f0}"
           "tr{page-break-inside:avoid}")
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
    with tempfile.TemporaryDirectory() as d:
        h = Path(d) / "overview.html"
        h.write_text(html, encoding="utf-8")
        subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", h.as_uri()], check=True, capture_output=True, timeout=120)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--pdf", type=Path)
    args = ap.parse_args()
    text = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(text.splitlines())} lines)")
    if args.pdf:
        to_pdf(text, args.pdf)
        print(f"wrote {args.pdf}")


if __name__ == "__main__":
    main()

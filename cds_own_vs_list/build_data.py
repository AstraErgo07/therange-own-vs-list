"""
build_data.py - turn the raw The Range scrape (../data/raw/) into range_listings.csv.

Run once:  python build_data.py
REAL columns only (title, category, price, sold_by, 1P/3P, URL, scrape date, method).
The economics that The Range does not publish (cost, fulfilment, returns, markdown,
units, stock cover) are estimated in calc.py from editable category benchmarks, so
they can be changed in the app sidebar and are always flagged as estimates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
RAW = HERE.parent / "data" / "raw" / "range_products_raw.jsonl"
OUT = HERE / "range_listings.csv"
PREFIX = {"home textiles": "HT", "kitchen": "KT", "outdoor": "OD", "beauty": "BT", "furniture": "FU", "lighting": "LT", "pets": "PT", "crafts": "CR"}


def build() -> pd.DataFrame:
    rows, counters = [], {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        cat = r["category"]
        counters[cat] = counters.get(cat, 0) + 1
        rows.append({
            "sku": f"{PREFIX[cat]}-{'3P' if r['is_3p'] else '1P'}-{counters[cat]:02d}",
            "category": cat,
            "subcategory": r["subcategory"],
            "title": r["title"],
            "brand": r.get("brand") or "",
            "price": float(r["price"]),
            "sold_by": r["sold_by"],
            "listing_type": "3P" if r["is_3p"] else "1P",
            "verified": "verified" in r["method"].lower(),
            "url": r["url"],
            "scrape_date": r["scrape_date"],
            "method": re.sub(r"\s+", " ", r["method"]),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build()
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(df)} real The Range listings "
          f"({(df.listing_type == '3P').sum()} marketplace/3P, {(df.listing_type == '1P').sum()} sold by The Range/1P)")

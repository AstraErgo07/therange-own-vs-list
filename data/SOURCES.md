# Own vs List (The Range, part of CDS): data sources and method

Snapshot date: 11 Nov 2026. This is a portfolio prototype. The outputs show a method on a small sample, not the size
of any market.

## How The Range pages were read

- Publicly visible product and category pages only, read with an automated page-reading tool, one page at a time.
  No logins, no accounts, no checkout.
- robots.txt respected: search, basket, account and other disallowed paths were not used. Product page addresses were
  found through ordinary web search.
- Every row keeps its source URL, the snapshot date and how it was read (`url`, `scrape_date`, `method` columns).
- Marketplace partner names are replaced with labels (Seller A, Seller B and so on), assigned per category in order of
  first appearance. The same label in two categories does not mean the same seller. The name to label mapping is kept
  locally and is not part of the repository.
- Product titles, brands and page addresses are kept as published. Where a partner sells its own brand, the brand can
  still point to the partner.

## Data

- 44 therange.co.uk listings: 25 sold by marketplace partners (3P), which are the decision candidates, and 19 sold by
  The Range (1P), used as substitutes. Pages were read with an automated page-reading tool, one at a time, no logins,
  robots.txt respected. 6 product pages were read directly ("verified"). The rest come from
  search-engine snapshots of the product page. 10 snapshot prices were checked against the live hair stylers and duvet
  cover category pages: 9 matched and 1 was out of date (Scallop Edge Duvet Set, £6.59 in the snapshot, £6.99 live).
  A page read directly also corrected the Keplin 9L from £69.99 to £59.41. Live prices are used wherever available.
- Files: `data/raw/range_products_raw.jsonl`, `cds_own_vs_list/range_listings.csv`,
  `data/raw/range_category_listing_raw.csv`.
- Published commission on The Range marketplace (percentage of the total sale including shipping, updated 24 Feb 2026):
  Home Furnishings 13%, Cooking and Dining 15%, Outdoor Living 14%, Health and Beauty 13%.
  Source: https://marketplacetherange.zendesk.com/hc/en-gb/articles/360018475658-Commission-Based-Fees.
  The marketplace runs on Mirakl (migration completed March 2026, per ChannelEngine and e-tailize).
- CDS (Superstores International) Ltd (company no. 02699203) owns The Range, wilko and Homebase
  (therange.co.uk/cds-family; Companies House via retailsector.co.uk).
- The same CDS product codes appear on wilko and Homebase (for example Kitchen Master Dual Stack 11L, code 8449326),
  so the group sells the same items across its brands. wilko was not used as a source of rows, because much of its
  online range is dropship.

## Estimates (category benchmarks, my judgement for UK value home retail, not CDS data)

| Category | Cost % of ex-VAT price | Fulfilment £ | Returns | Markdown | Stock cover (days) | Units a week at reference price | Elasticity | Demand cv |
|---|---|---|---|---|---|---|---|---|
| Home textiles | 40% | 3.00 | 5% | 15% | 75 | 25 at £15 | 1.0 | 0.35 |
| Kitchen (small electricals) | 65% | 7.50 | 8% | 7% | 45 | 12 at £50 | 1.2 | 0.30 |
| Outdoor (solar lighting) | 40% | 3.50 | 6% | 20% | 90 | 15 at £15 | 1.0 | 0.55 (seasonal) |
| Beauty (hair electricals) | 65% | 3.00 | 6% | 8% | 50 | 6 at £40 | 1.0 | 0.30 |

Policy settings: hurdle 25%, holding cost 20%, diversion 30% per category, marketplace cost £0.50 a unit, volatility
threshold cv 0.5, near-threshold band 10%.

## Interpretation choices

1. VAT: UK shelf prices include 20% VAT. 1P revenue uses the ex-VAT price. The Range's commission is a percentage of
   what the customer pays, so 3P commission uses the shelf price.
2. The substitute is real: the lost 1P contribution uses the median price of The Range's own 1P listings in the same
   category, run through the same benchmarks.
3. Demand: The Range shows almost no reviews, so units come from a price curve. This is an estimate.
4. Economics are online only. Fulfilment is per online order and store sales of 1P substitutes are not modelled.
5. One listing was left out: a "Tectake 12 LED Solar Garden Lights" at £999.00 (search snapshot), which looks like a
   price or pack-size error.
6. Partner names are replaced with labels per category (see above).

## Website terms

The Range's Terms and Conditions (therange.co.uk/terms-and-conditions, read 11 Nov 2026) have no clause that names
scraping or automated collection. Clause 11 covers reuse of content:

> 11.2 You may not reproduce, copy, distribute, sell, rent, sub-licence, store, or in any other manner re-use Content
> from Our Websites unless given express written permission to do so by Us.

> 11.5 You may not use any Content saved or downloaded from Our Websites for commercial purposes without first
> obtaining a licence from Us (or Our licensors, as appropriate) to do so. This does not prohibit the normal access,
> viewing and use of Our Websites for general information purposes whether by business users or consumers.

Clause 11.3 allows viewing, caching, printing, downloading extracts and saving pages for offline viewing. Clause 11.6
keeps the Copyright, Designs and Patents Act 1988 exceptions, including "the making of copies for text and data
analysis for non-commercial research".

## Labels used in the app

- 🟢 published or shown: a published price list, or a field shown on the listing.
- 🟠 estimate: an assumption or a number derived from one. Every estimate can be changed in the sidebar.
- ⚙️ policy: a business setting, such as the minimum return on stock money.

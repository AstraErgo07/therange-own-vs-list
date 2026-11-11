# Own vs List: The Range (CDS)

A decision-support prototype for The Range's marketplace. For each product that a marketplace partner sells on
therange.co.uk (3P), it asks whether The Range should buy and stock it itself (1P), keep it on the marketplace, or
test first. It compares the profit per unit of selling the product 1P with the value of the 3P sale (commission less
marketplace cost, allowing for sales of The Range's own similar items), checks the yearly return on the money tied
up in stock against a hurdle, and ranks the products. A person accepts or overrides every recommendation, with a
reason for an override, and each decision is logged.

Built on 44 public therange.co.uk listings (partner names replaced with labels), The Range's published marketplace
commission and labelled estimates for the costs The Range does not publish. A small sample: a test of the method, not
market sizing.

Portfolio project. Made by Ami Sata.

## Run it

```
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Python 3.12 or newer. To host it on Streamlit Community Cloud: Create app, pick this repository, branch `main`, main
file `streamlit_app.py`, and choose Python 3.12 or newer under Advanced settings.

A plain-text write-up with every number at the default settings is in `docs/OVERVIEW.md`, generated from the code by
`python tools/build_overview.py`.

## How it works

- 1P profit per unit = ex-VAT price less cost of goods, pick-pack-deliver, returns, markdowns and the cost of holding
  stock.
- 3P value per unit = commission on the shelf price less the marketplace cost per unit, plus the profit on The Range's
  own substitute for the share of buyers who would otherwise buy it.
- Units a year come from a price curve per category, because The Range shows almost no reviews.
- Decision rules, in order: test first if demand swings a lot or the answer is too close to call; bring in-house if
  1P makes more per unit and the return on stock beats the hurdle; otherwise keep it 3P.
- An LLM is optional (`OPENAI_API_KEY`) and only drafts the explanation. Without a key the rules write it.

## Layout

| Path | What it is |
|---|---|
| `streamlit_app.py` | entry point |
| `app_pages/cds_own_vs_list_page.py` | the tool |
| `app_pages/method_page.py` | data and method page |
| `cds_own_vs_list/calc.py` | the calculations and assumptions |
| `cds_own_vs_list/range_listings.csv` | the listings used |
| `data/raw/` | the listings as read, with source URL and date |
| `data/SOURCES.md` | sources, published fees, estimates and what The Range's terms say |
| `tools/build_overview.py` | writes `docs/OVERVIEW.md` |

## Tests

```
python -m unittest discover -s cds_own_vs_list -p "test_*.py"
python smoke_test_app.py
```

Independent portfolio project using public data. Not affiliated with The Range or CDS.

"""
cds_own_vs_list/test_calc.py - hand-checkable tests.  Run:  python -m unittest -v
"""
import unittest

import pandas as pd

from calc import (Assumptions, Benchmark, BRING_IN_HOUSE, KEEP_3P, contribution_3p, ex_vat,
                  estimate_fields, estimate_weekly_units, evaluate_portfolio, net_3p_benefit,
                  substitute_prices, unit_contribution_1p, decide)

# Easy benchmark: cogs 40% of ex-VAT price, £5 fulfilment, 5% returns, 5% markdown,
# 73 days cover, 10 units/week at £50, elasticity 1, cv 0.2
B = Benchmark(cogs_pct=0.40, fulfilment_cost=5.0, return_rate=0.05, markdown_rate=0.05,
              stock_cover_days=73, ref_weekly_units=10, ref_price=50.0, elasticity=1.0, weekly_units_cv=0.2)


class TestCdsCalc(unittest.TestCase):

    def test_1_vat_estimates_and_1p_contribution(self):
        # £120 shelf price / 1.20 VAT = £100 ex-VAT
        self.assertAlmostEqual(ex_vat(120, 0.20), 100.0)
        e = estimate_fields(120, B, 0.20)
        self.assertAlmostEqual(e["cogs"], 40.0)          # 100 x 40%
        # 1P = 100 - 40 - 5 - 5 - 5 - holding (40 x 20% x 73/365 = 1.60) = 43.40
        self.assertAlmostEqual(unit_contribution_1p(120, B, 0.20, 0.20), 43.40)

    def test_2_real_substitute_and_cannibalisation(self):
        listings = pd.DataFrame({"category": ["kitchen"] * 4, "listing_type": ["1P", "1P", "1P", "3P"],
                                 "price": [60.0, 84.0, 120.0, 120.0]})
        # median 1P price = £84 -> the substitute
        self.assertAlmostEqual(substitute_prices(listings)["kitchen"], 84.0)
        # substitute 1P: ex-VAT 70 - cogs 28 - 5 - 3.50 - 3.50 - holding 1.12 = 28.88
        sub = unit_contribution_1p(84, B, 0.20, 0.20)
        self.assertAlmostEqual(sub, 28.88)
        # 3P = 120 x 15% - 0.50 = 17.50 ; net 3P = 17.50 - 30% x 28.88 = 8.836
        c3p = contribution_3p(120, 0.15, 0.50)
        self.assertAlmostEqual(c3p, 17.50)
        self.assertAlmostEqual(net_3p_benefit(c3p, 0.30, sub), 8.836)

    def test_3_units_estimate_and_full_decision(self):
        self.assertAlmostEqual(estimate_weekly_units(100, B), 5.0)        # 10 x (50/100)^1
        self.assertAlmostEqual(estimate_weekly_units(0.01, B), 200.0)     # clamped at 200
        a = Assumptions(benchmarks={"kitchen": B}, commission_rates={"kitchen": 0.15},
                        diversion_rates={"kitchen": 0.30})
        listings = pd.DataFrame([
            {"sku": "S1", "category": "kitchen", "title": "t", "sold_by": "X", "price": 60.0, "listing_type": "1P"},
            {"sku": "S2", "category": "kitchen", "title": "t", "sold_by": "X", "price": 84.0, "listing_type": "1P"},
            {"sku": "S3", "category": "kitchen", "title": "t", "sold_by": "X", "price": 120.0, "listing_type": "1P"},
            {"sku": "C1", "category": "kitchen", "title": "t", "sold_by": "Seller", "price": 120.0, "listing_type": "3P"}])
        r = evaluate_portfolio(listings, a).iloc[0]
        # only the 3P listing is a candidate
        self.assertEqual(r["sku"], "C1")
        self.assertAlmostEqual(r["contrib_1p_unit"], 43.40)
        self.assertAlmostEqual(r["net_3p_unit"], 8.836)
        # units 10 x 50/120 = 4.1667 ; ROC = 43.40 x 4.1667 x 52 / (40 x 4.1667 x 73/7) = 5.41
        self.assertAlmostEqual(r["return_on_capital"], 43.40 * 52 / (40 * 73 / 7), places=4)
        self.assertEqual(r["recommendation"], BRING_IN_HOUSE)
        # and the core rule still works: 1P 2.0 < net 3P 5.0, ROC 0.1 -> Keep 3P
        self.assertEqual(decide(2.0, 5.0, 0.10, 0.2, a)[0], KEEP_3P)


    def test_9_plain_workings_match_the_engine(self):
        from pathlib import Path
        from calc import evaluate_portfolio, load_listings
        from workings import _gbp, own_vs_list_workings
        a = Assumptions()
        res = evaluate_portfolio(load_listings(Path(__file__).parent / "range_listings.csv"), a)
        for c in res.to_dict("records"):
            steps = {x["step"]: x["result"] for x in own_vs_list_workings(c, a)}
            self.assertEqual(steps["= 1P profit per unit"], _gbp(c["contrib_1p_unit"]))
            self.assertEqual(steps["= 3P value per unit"], _gbp(c["net_3p_unit"]))
            self.assertEqual(steps["Decision"], c["recommendation"])
            # the lines add up to the 1P profit
            parts = c["price_ex_vat"] - c["cogs"] - c["fulfilment_cost"] - c["price_ex_vat"] * (
                c["return_rate"] + c["markdown_rate"]) - c["holding_cost_unit"]
            self.assertAlmostEqual(parts, c["contrib_1p_unit"], places=9)



if __name__ == "__main__":
    unittest.main()

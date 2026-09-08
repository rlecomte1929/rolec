"""AIQ-1516 — the best-value recommendation engine.

Pure function, so these are fast and exhaustive. They pin the HONESTY rules, which are the whole
point: never rank when it would mislead, never impute a signal we don't have, always say what the
ranking rests on. Scenarios map to the task brief's verification protocol, minus the ones the data
model can't support (per-line scope coverage — quote_lines carry no rfq_item_id).
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.rfq_evaluation_service import (  # noqa: E402
    recommend, HIGH, MEDIUM, LOW, REFUSED,
)


def _q(qid, vendor, total, currency="EUR", name=None):
    return {"id": qid, "vendor_id": vendor, "total_amount": total, "currency": currency,
            "supplier_name": name or vendor}


def _snap(avg_cost_eur=None, avg_rating=None, review_count=None):
    return {"avg_cost_eur": avg_cost_eur, "avg_rating": avg_rating, "review_count": review_count}


class RecommendTests(unittest.TestCase):
    def test_single_offer_is_LOW_no_comparison(self):
        r = recommend([_q("q1", "v1", 2000)], {})
        self.assertEqual(r["confidence"], LOW)
        self.assertEqual(r["recommended_quote_id"], "q1")
        self.assertIn("one offer", r["headline"].lower())

    def test_currency_mismatch_is_REFUSED(self):
        r = recommend([_q("q1", "v1", 2000, "EUR"), _q("q2", "v2", 1800, "GBP")], {})
        self.assertEqual(r["confidence"], REFUSED)
        self.assertIn("currency", r["refused_reason"].lower())
        self.assertIsNone(r["recommended_quote_id"])

    def test_no_priced_quote_is_REFUSED(self):
        r = recommend([{"id": "q1", "vendor_id": "v1", "total_amount": None, "currency": "EUR"}], {})
        self.assertEqual(r["confidence"], REFUSED)

    def test_price_only_two_offers_is_LOW_and_says_so(self):
        # No snapshots => no quality => the ranking must admit it rests on price alone.
        r = recommend([_q("q1", "v1", 2100), _q("q2", "v2", 1800)], {})
        self.assertEqual(r["confidence"], LOW)
        self.assertEqual(r["recommended_quote_id"], "q2")  # cheaper wins on price-only
        self.assertTrue(any("price alone" in x or "price is the only" in x.lower()
                            for x in r["reasons"] + r["trade_offs"]))

    def test_price_plus_quality_is_MEDIUM_and_cites_snapshot(self):
        snaps = {
            "v1": _snap(avg_cost_eur=2400, avg_rating=4.6, review_count=120),
            "v2": _snap(avg_cost_eur=2400, avg_rating=3.1, review_count=40),
        }
        # v1 slightly pricier but far better rated; v2 cheaper. Winner is by price then quality —
        # here v2 is cheaper so it wins on price, but quality must be CITED for the trade-off.
        r = recommend([_q("q1", "v1", 2000), _q("q2", "v2", 1900)], snaps)
        self.assertEqual(r["confidence"], MEDIUM)
        self.assertTrue(any("benchmark" in x.lower() or "review" in x.lower() for x in r["reasons"]))

    def test_below_market_benchmark_is_surfaced(self):
        snaps = {"v1": _snap(avg_cost_eur=2300, avg_rating=4.4, review_count=98)}
        r = recommend([_q("q1", "v1", 2000), _q("q2", "v2", 2500)], snaps)
        self.assertEqual(r["recommended_quote_id"], "q1")
        self.assertIn("market", r["headline"].lower())

    def test_above_market_is_a_tradeoff_not_a_reason(self):
        # The winner can still be cheapest of the offers yet above the market benchmark. That is a
        # mark AGAINST it, never dressed up as a reason to pick it.
        snaps = {"v1": _snap(avg_cost_eur=1375, avg_rating=4.4, review_count=98),
                 "v2": _snap(avg_cost_eur=1375, avg_rating=4.6, review_count=120)}
        r = recommend([_q("q1", "v1", 4250), _q("q2", "v2", 5120)], snaps)
        self.assertEqual(r["recommended_quote_id"], "q1")
        joined_reasons = " ".join(r["reasons"]).lower()
        self.assertNotIn("above", joined_reasons)
        self.assertTrue(any("above the market" in t.lower() for t in r["trade_offs"]))

    def test_thin_reviews_do_not_count_as_quality(self):
        # review_count < 5 -> quality absent -> LOW, not MEDIUM.
        snaps = {"v1": _snap(avg_cost_eur=2100, avg_rating=5.0, review_count=2)}
        r = recommend([_q("q1", "v1", 2000), _q("q2", "v2", 2200)], snaps)
        self.assertEqual(r["confidence"], LOW)

    def test_over_cap_is_flagged_as_a_tradeoff_not_excluded(self):
        r = recommend([_q("q1", "v1", 2300), _q("q2", "v2", 2600)], {}, cap_amount=2000)
        self.assertEqual(r["recommended_quote_id"], "q1")  # still recommended
        self.assertTrue(any("cap" in x.lower() for x in r["trade_offs"]))

    def test_reasons_always_cite_a_source(self):
        snaps = {"v1": _snap(avg_cost_eur=2300, avg_rating=4.4, review_count=98)}
        r = recommend([_q("q1", "v1", 2000), _q("q2", "v2", 2400)], snaps)
        # every reason should reference where the number came from
        self.assertTrue(all(("(" in x and ")" in x) or "EUR" in x for x in r["reasons"]))
        self.assertNotIn("composite", " ".join(r["reasons"]).lower())  # never leak the score


if __name__ == "__main__":
    unittest.main()

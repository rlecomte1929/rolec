"""
Unit tests for the RAG eval harness metric functions (P3-01b-FU4 / AIQ-778).

`scripts/rag_eval_harness.py` is the shared harness behind every RAG eval
report (context-precision, factual-consistency, …). Its three metric functions
are tiny but load-bearing: a silent off-by-one in ``precision_at_k`` would skew
every nightly run. These tests are deliberately fixture-free — hand-rolled
inputs only, no JSONL load, no DB, no retriever — so they run in well under a
second and pin the exact edge-case behaviour:

  - ``precision_at_k`` divides by ``len(top_k)`` (NOT ``k``), so ``k`` larger
    than the retrieved list does not deflate the score.
  - ``recall_at_k`` returns 1.0 for an empty expected set (nothing to miss).
  - ``f1`` guards the p+r==0 division.
  - ``aggregate_report`` skips ``None`` metrics, rounds means to 4 dp, and
    sorts ``lowest_queries`` ascending.
"""
from __future__ import annotations

import os
import sys
import unittest

# backend/ on sys.path so `from scripts.rag_eval_harness import ...` resolves
# regardless of the invocation directory (mirrors the eval scripts).
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from scripts.rag_eval_harness import (  # noqa: E402
    GoldenQuery,
    QueryResult,
    aggregate_report,
    f1,
    precision_at_k,
    recall_at_k,
)


class PrecisionAtKTests(unittest.TestCase):
    def test_full_hit(self):
        """All top-k retrieved ids are expected → 1.0."""
        self.assertEqual(precision_at_k(["a", "b", "c"], ["a", "b", "c"], 3), 1.0)

    def test_partial_hit(self):
        """2 of the 3 top-k ids are expected → 2/3."""
        self.assertAlmostEqual(
            precision_at_k(["a", "x", "b"], ["a", "b", "c"], 3), 2 / 3, places=4
        )

    def test_no_hit(self):
        """No top-k id is expected → 0.0."""
        self.assertEqual(precision_at_k(["x", "y"], ["a"], 2), 0.0)

    def test_k_equals_one_truncates_to_first(self):
        """k=1 only considers the first retrieved id (a miss here)."""
        self.assertEqual(precision_at_k(["a", "b"], ["b"], 1), 0.0)
        self.assertEqual(precision_at_k(["b", "z"], ["b"], 1), 1.0)

    def test_k_larger_than_retrieved_divides_by_len_not_k(self):
        """k=5 but only 2 retrieved → denominator is 2, not 5."""
        self.assertEqual(precision_at_k(["a", "b"], ["a", "b"], 5), 1.0)
        self.assertEqual(precision_at_k(["a", "x", "b", "y"], ["a", "b"], 5), 0.5)

    def test_empty_retrieved_is_zero(self):
        self.assertEqual(precision_at_k([], ["a"], 3), 0.0)

    def test_empty_expected_is_zero(self):
        """Nothing can be a hit when nothing is expected."""
        self.assertEqual(precision_at_k(["a", "b"], [], 3), 0.0)


class RecallAtKTests(unittest.TestCase):
    def test_full_recall(self):
        """Every expected id appears in top-k → 1.0."""
        self.assertEqual(recall_at_k(["a", "b", "c"], ["a", "b"], 3), 1.0)

    def test_partial_recall(self):
        """1 of 2 expected ids retrieved → 0.5."""
        self.assertEqual(recall_at_k(["a", "x"], ["a", "b"], 2), 0.5)

    def test_no_hit(self):
        self.assertEqual(recall_at_k(["x"], ["a"], 1), 0.0)

    def test_k_truncation_can_drop_an_expected_id(self):
        """k=1 cuts off the expected id sitting at position 2 → 0.0."""
        self.assertEqual(recall_at_k(["x", "a"], ["a"], 1), 0.0)

    def test_k_larger_than_retrieved(self):
        """k>len(retrieved): 1 of 2 expected found → 0.5."""
        self.assertEqual(recall_at_k(["a"], ["a", "b"], 5), 0.5)

    def test_empty_expected_is_perfect_recall(self):
        """No expected ids → nothing to miss → 1.0 (documented convention)."""
        self.assertEqual(recall_at_k(["a"], [], 3), 1.0)

    def test_empty_retrieved_is_zero(self):
        self.assertEqual(recall_at_k([], ["a"], 3), 0.0)


class F1Tests(unittest.TestCase):
    def test_both_zero_guards_division(self):
        self.assertEqual(f1(0.0, 0.0), 0.0)

    def test_perfect(self):
        self.assertEqual(f1(1.0, 1.0), 1.0)

    def test_balanced_half(self):
        self.assertEqual(f1(0.5, 0.5), 0.5)

    def test_one_side_zero(self):
        """p=1, r=0 → harmonic mean is 0."""
        self.assertEqual(f1(1.0, 0.0), 0.0)
        self.assertEqual(f1(0.0, 0.8), 0.0)

    def test_asymmetric(self):
        """p=0.5, r=1.0 → 2*0.5*1/1.5 = 2/3."""
        self.assertAlmostEqual(f1(0.5, 1.0), 2 / 3, places=4)


class AggregateReportTests(unittest.TestCase):
    def _results(self):
        q1 = GoldenQuery("q1", "US→FR", "eligibility", "t1", ["a"], difficulty="easy")
        q2 = GoldenQuery("q2", "US→FR", "fact_lookup", "t2", ["b"], difficulty="hard")
        q3 = GoldenQuery("q3", "IN→DE", "eligibility", "t3", ["c"], difficulty="hard")
        return [
            QueryResult(q1, {"precision_at_k": 1.0}, ["a"]),
            QueryResult(q2, {"precision_at_k": 0.5}, ["b"]),
            QueryResult(q3, {"precision_at_k": 0.0}, []),
        ]

    def test_aggregate_and_threshold(self):
        report = aggregate_report(self._results(), "precision_at_k", threshold=0.85)
        self.assertEqual(report["metric"], "precision_at_k")
        self.assertEqual(report["aggregate"], 0.5)  # mean(1.0, 0.5, 0.0)
        self.assertEqual(report["queries_evaluated"], 3)
        self.assertFalse(report["passes_threshold"])  # 0.5 < 0.85

    def test_threshold_met(self):
        report = aggregate_report(self._results(), "precision_at_k", threshold=0.4)
        self.assertTrue(report["passes_threshold"])  # 0.5 >= 0.4

    def test_breakdowns(self):
        report = aggregate_report(self._results(), "precision_at_k", threshold=0.85)
        self.assertEqual(report["by_corridor"], {"IN→DE": 0.0, "US→FR": 0.75})
        self.assertEqual(report["by_intent"], {"eligibility": 0.5, "fact_lookup": 0.5})
        self.assertEqual(report["by_difficulty"], {"easy": 1.0, "hard": 0.25})

    def test_lowest_queries_sorted_ascending(self):
        report = aggregate_report(self._results(), "precision_at_k", threshold=0.85)
        lowest = report["lowest_queries"]
        self.assertEqual(len(lowest), 3)
        self.assertEqual([q["query_id"] for q in lowest], ["q3", "q2", "q1"])
        self.assertEqual(lowest[0]["value"], 0.0)
        self.assertEqual(lowest[0]["corridor"], "IN→DE")

    def test_missing_metric_is_skipped_from_aggregate_but_counted(self):
        """A result lacking the metric is excluded from the mean, yet still
        counted in queries_evaluated."""
        q1 = GoldenQuery("q1", "US→FR", "eligibility", "t1", ["a"])
        q2 = GoldenQuery("q2", "US→FR", "eligibility", "t2", ["b"])
        results = [
            QueryResult(q1, {"precision_at_k": 1.0}, ["a"]),
            QueryResult(q2, {}, ["b"]),  # no precision_at_k key
        ]
        report = aggregate_report(results, "precision_at_k", threshold=0.5)
        self.assertEqual(report["aggregate"], 1.0)  # mean of the single present value
        self.assertEqual(report["queries_evaluated"], 2)

    def test_empty_results_raises(self):
        with self.assertRaises(ValueError):
            aggregate_report([], "precision_at_k", threshold=0.5)


if __name__ == "__main__":
    unittest.main()

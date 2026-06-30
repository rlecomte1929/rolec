"""
P4 — unit tests for the HR-policy lexical reranker and its flag wiring.

Covers:
  - rerank_chunks pure-function correctness on a tiny known case
    (a lexically-matching, lower-scored chunk is promoted over a higher-scored
    one with no lexical overlap), determinism, annotation, no input mutation.
  - the OFF path of policy_chunk_retriever._apply_quality_gates is byte-identical
    whether or not a query is supplied, as long as POLICY_RAG_RERANK is unset;
    flipping the flag ON actually changes the order (proving the gate works).
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_rerank import rerank_chunks  # noqa: E402
from backend.app.services import policy_chunk_retriever as pcr  # noqa: E402

_NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


class TestRerankPureFunction(unittest.TestCase):
    def test_lexical_match_promotes_lower_scored_chunk(self):
        # A has a slightly LOWER first-pass score but matches every query term;
        # B scores higher but shares no terms. Blend (alpha=0.6) must rank A first.
        query = "monthly housing allowance cap"
        chunks = [
            {"id": "B", "adjusted_score": 0.55, "chunk_text": "dental insurance coverage details"},
            {"id": "A", "adjusted_score": 0.50, "chunk_text": "the monthly housing allowance cap is 2500"},
        ]
        out = rerank_chunks(query, chunks)
        self.assertEqual([c["id"] for c in out], ["A", "B"])
        a = next(c for c in out if c["id"] == "A")
        self.assertGreater(a["lexical_score"], 0.0)
        self.assertAlmostEqual(a["rerank_score"], 0.6 * 0.50 + 0.4 * a["lexical_score"], places=6)
        # First-pass score preserved.
        self.assertEqual(a["adjusted_score"], 0.50)

    def test_no_lexical_overlap_keeps_first_pass_order(self):
        # Neither chunk shares query terms -> lexical 0 -> order by adjusted_score.
        query = "zzz qqq"
        chunks = [
            {"id": "lo", "adjusted_score": 0.40, "chunk_text": "housing"},
            {"id": "hi", "adjusted_score": 0.80, "chunk_text": "flights"},
        ]
        out = rerank_chunks(query, chunks)
        self.assertEqual([c["id"] for c in out], ["hi", "lo"])

    def test_deterministic_tiebreak_by_id(self):
        query = "housing"
        chunks = [
            {"id": "zzz", "adjusted_score": 0.5, "chunk_text": "housing"},
            {"id": "aaa", "adjusted_score": 0.5, "chunk_text": "housing"},
        ]
        out = rerank_chunks(query, chunks)
        self.assertEqual([c["id"] for c in out], ["aaa", "zzz"])  # equal score -> id asc

    def test_does_not_mutate_input(self):
        chunks = [{"id": "A", "adjusted_score": 0.5, "chunk_text": "housing cap"}]
        rerank_chunks("housing cap", chunks)
        self.assertNotIn("rerank_score", chunks[0])
        self.assertNotIn("lexical_score", chunks[0])

    def test_empty_query_returns_unchanged(self):
        chunks = [{"id": "A", "adjusted_score": 0.5, "chunk_text": "x"}]
        self.assertIs(rerank_chunks("   ", chunks), chunks)


class TestFlagGateByteIdentical(unittest.TestCase):
    """OFF path must be byte-identical; flag ON must take effect."""

    def _chunks(self):
        # Crafted so lexical rerank WOULD change the order if enabled:
        # 'lo' matches the query, 'hi' has a higher adjusted_score but no overlap.
        return [
            {"id": "hi", "score": 0.80, "chunk_metadata": {}, "created_at": _NOW,
             "chunk_text": "flights and airport transfers"},
            {"id": "lo", "score": 0.60, "chunk_metadata": {}, "created_at": _NOW,
             "chunk_text": "monthly housing allowance cap rules"},
        ]
        # adjusted_score == score here (neutral tier + fresh).

    def setUp(self):
        os.environ.pop("POLICY_RAG_RERANK", None)

    def tearDown(self):
        os.environ.pop("POLICY_RAG_RERANK", None)

    def test_off_is_identical_with_and_without_query(self):
        baseline = pcr._apply_quality_gates(
            self._chunks(), min_similarity_score=0.0, top_k=2, now=_NOW
        )
        with_query = pcr._apply_quality_gates(
            self._chunks(), min_similarity_score=0.0, top_k=2, now=_NOW,
            query="monthly housing allowance cap",
        )
        self.assertEqual([c["id"] for c in baseline], ["hi", "lo"])  # by adjusted_score
        self.assertEqual(
            [c["id"] for c in baseline], [c["id"] for c in with_query]
        )
        # No rerank annotations leak onto the OFF path.
        self.assertNotIn("rerank_score", with_query[0])

    def test_flag_on_reorders(self):
        os.environ["POLICY_RAG_RERANK"] = "1"
        out = pcr._apply_quality_gates(
            self._chunks(), min_similarity_score=0.0, top_k=2, now=_NOW,
            query="monthly housing allowance cap",
        )
        self.assertEqual([c["id"] for c in out], ["lo", "hi"])  # lexical promotes 'lo'
        self.assertIn("rerank_score", out[0])


if __name__ == "__main__":
    unittest.main()

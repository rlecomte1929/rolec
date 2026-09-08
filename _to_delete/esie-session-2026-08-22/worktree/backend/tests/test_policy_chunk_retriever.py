"""
Tests for W2/AIQ-836 retrieval quality gates in policy_chunk_retriever.

The ranking logic is exercised through the pure helper `_apply_quality_gates`
(no DB, no embedder, no network) so the floor / trust-tier boost / freshness
decay are deterministic.

Schema note: policy_assistant_chunks has NO trust_tier or fetched_at column
(the original brief was wrong). Tier comes from chunk_metadata->>'source_tier'
(string, null for HR matrix_benefit chunks) and freshness from created_at.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("POLICY_ASSISTANT_EMBEDDER", "hash")
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

from backend.app.services.policy_chunk_retriever import (  # noqa: E402
    _apply_quality_gates,
    _parse_tier,
    _retrieve_postgres,
)

_NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _chunk(score, *, tier=None, created=None, cid="x"):
    meta = {}
    if tier is not None:
        meta["source_tier"] = tier
    return {"id": cid, "score": score, "chunk_metadata": meta, "created_at": created}


class TestQualityGates(unittest.TestCase):
    def test_floor_excludes_below_min(self):
        chunks = [_chunk(0.20, cid="lo"), _chunk(0.30, cid="hi")]
        out = _apply_quality_gates(chunks, min_similarity_score=0.25, top_k=10, now=_NOW)
        ids = [c["id"] for c in out]
        self.assertEqual(ids, ["hi"])  # 0.20 dropped, 0.30 kept

    def test_floor_disabled_with_zero(self):
        chunks = [_chunk(0.10, cid="lo"), _chunk(0.30, cid="hi")]
        out = _apply_quality_gates(chunks, min_similarity_score=0.0, top_k=10, now=_NOW)
        self.assertEqual({c["id"] for c in out}, {"lo", "hi"})  # nothing dropped

    def test_tier_boost_reranks_tier1_over_higher_raw_tier3(self):
        # tier1 raw 0.80 -> 0.80 ; tier3 raw 0.82 -> 0.615 ; tier1 must win.
        t1 = _chunk(0.80, tier="1", created=_NOW, cid="t1")
        t3 = _chunk(0.82, tier="3", created=_NOW, cid="t3")
        out = _apply_quality_gates([t3, t1], min_similarity_score=0.0, top_k=10, now=_NOW)
        self.assertEqual(out[0]["id"], "t1")
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.80, places=3)
        self.assertAlmostEqual(
            next(c for c in out if c["id"] == "t3")["adjusted_score"], 0.615, places=3
        )

    def test_null_tier_is_neutral(self):
        # HR matrix_benefit chunks have no source_tier -> boost 1.0, score unchanged.
        out = _apply_quality_gates(
            [_chunk(0.50, tier=None, created=_NOW)], min_similarity_score=0.0, top_k=10, now=_NOW
        )
        self.assertIsNone(out[0]["source_tier"])
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.50, places=3)

    def test_freshness_decay_and_stale_flag(self):
        stale = _chunk(0.90, tier="1", created=_NOW - timedelta(days=200), cid="old")
        out = _apply_quality_gates([stale], min_similarity_score=0.0, top_k=10, now=_NOW)
        self.assertTrue(out[0]["is_stale"])
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.90 * 0.70, places=3)  # >180d decay

    def test_fresh_chunk_not_stale(self):
        fresh = _chunk(0.90, tier="1", created=_NOW - timedelta(days=10), cid="new")
        out = _apply_quality_gates([fresh], min_similarity_score=0.0, top_k=10, now=_NOW)
        self.assertFalse(out[0]["is_stale"])
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.90, places=3)  # no decay

    def test_preserves_legacy_score_field(self):
        out = _apply_quality_gates([_chunk(0.42, created=_NOW)], min_similarity_score=0.0, top_k=10, now=_NOW)
        self.assertEqual(out[0]["score"], 0.42)
        self.assertEqual(out[0]["raw_score"], 0.42)

    def test_parse_tier_coercions(self):
        self.assertEqual(_parse_tier("1"), 1)
        self.assertEqual(_parse_tier("2"), 2)
        self.assertIsNone(_parse_tier(None))
        self.assertIsNone(_parse_tier(""))
        self.assertIsNone(_parse_tier("not-a-number"))


class TestNonUuidCompanyGuard(unittest.TestCase):
    """F3: policy_assistant_chunks.company_id is a uuid column. A non-UUID
    company id (legacy seed slug) must yield no chunks rather than raise
    InvalidTextRepresentation (which 500'd the assistant once F3 ran the query
    as the relopass_api role)."""

    def test_non_uuid_company_returns_empty(self):
        # Returns early before any DB / embedder access.
        out = _retrieve_postgres("seed-emp-testingapril", [0.1] * 8, 8, None)
        self.assertEqual(out, [])

    def test_empty_company_returns_empty(self):
        out = _retrieve_postgres("", [0.1] * 8, 8, None)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()

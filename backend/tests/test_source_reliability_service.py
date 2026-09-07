"""
N8 / AIQ-848 — tests for the rolling source_reliability_score service and its
fold-in to the immigration retriever ranking.

In-memory SQLite (StaticPool) mirrors the three live tables: immigration_corpus_chunks
(with the new reliability columns), policy_assistant_traces, ai_human_feedback.
No network, no DB config — the engine is injected.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import source_reliability_config as cfg
from backend.app.services.immigration_retriever import _apply_quality_gates
from backend.app.services.source_reliability_config import reliability_factor
from backend.app.services.source_reliability_service import (
    recompute_reliability_scores,
    reliability_score,
)

_CHUNKS_SCHEMA = (
    "CREATE TABLE immigration_corpus_chunks ("
    "id TEXT PRIMARY KEY, corridor TEXT NOT NULL DEFAULT 'FR_NO', source_url TEXT, "
    "chunk_text TEXT, chunk_metadata TEXT DEFAULT '{}', trust_tier INTEGER DEFAULT 1, "
    "fetched_at TEXT, embedding TEXT, content_hash TEXT, is_active INTEGER DEFAULT 1, "
    "reliability_score REAL DEFAULT 0.5, citation_count INTEGER DEFAULT 0, "
    "rejection_count INTEGER DEFAULT 0, last_reliability_update TEXT)"
)
_TRACES_SCHEMA = (
    "CREATE TABLE policy_assistant_traces ("
    "id TEXT PRIMARY KEY, feature_key TEXT, cited_chunk_ids TEXT DEFAULT '[]')"
)
_FEEDBACK_SCHEMA = (
    "CREATE TABLE ai_human_feedback ("
    "id TEXT PRIMARY KEY, trace_session_id TEXT, verdict TEXT)"
)


def _engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as c:
        c.execute(text(_CHUNKS_SCHEMA))
        c.execute(text(_TRACES_SCHEMA))
        c.execute(text(_FEEDBACK_SCHEMA))
    return eng


def _seed_chunk(eng, cid):
    with eng.begin() as c:
        c.execute(text("INSERT INTO immigration_corpus_chunks (id) VALUES (:id)"), {"id": cid})


def _seed_trace(eng, tid, cited, feature_key="immigration_answer"):
    with eng.begin() as c:
        c.execute(text("INSERT INTO policy_assistant_traces (id, feature_key, cited_chunk_ids) "
                       "VALUES (:id,:fk,:cc)"),
                  {"id": tid, "fk": feature_key, "cc": json.dumps(cited)})


def _seed_feedback(eng, tid, verdict):
    with eng.begin() as c:
        c.execute(text("INSERT INTO ai_human_feedback (id, trace_session_id, verdict) "
                       "VALUES (:id,:t,:v)"),
                  {"id": f"fb-{tid}", "t": tid, "v": verdict})


def _row(eng, cid):
    with eng.begin() as c:
        return c.execute(text(
            "SELECT reliability_score, citation_count, rejection_count, last_reliability_update "
            "FROM immigration_corpus_chunks WHERE id=:id"), {"id": cid}).mappings().one()


class ReliabilityMathTests(unittest.TestCase):
    def test_zero_citations_is_neutral(self):
        self.assertEqual(reliability_score(0, 0), 0.5)

    def test_high_rejection_large_sample_is_low(self):
        # 10 citations, 8 rejections -> simple ratio 1 - 0.8 = 0.2
        self.assertLessEqual(reliability_score(10, 8), 0.3)

    def test_clean_chunk_is_one(self):
        self.assertEqual(reliability_score(10, 0), 1.0)

    def test_low_sample_uses_wilson_not_naive_rate(self):
        # 5 citations, 1 rejection: naive rate 0.8, but Wilson lower bound is much lower.
        score = reliability_score(5, 1)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 0.8)


class RecomputeServiceTests(unittest.TestCase):
    def test_criterion1_chunk_cited_10_rejected_8_scores_below_03(self):
        eng = _engine()
        _seed_chunk(eng, "X")
        for i in range(10):
            _seed_trace(eng, f"t{i}", ["X"])
        for i in range(8):
            _seed_feedback(eng, f"t{i}", "rejected")
        recompute_reliability_scores(engine=eng)
        row = _row(eng, "X")
        self.assertEqual(row["citation_count"], 10)
        self.assertEqual(row["rejection_count"], 8)
        self.assertLess(row["reliability_score"], 0.3)
        self.assertIsNotNone(row["last_reliability_update"])

    def test_criterion2_uncited_chunk_stays_neutral(self):
        eng = _engine()
        _seed_chunk(eng, "Y")
        # default before recompute
        self.assertEqual(_row(eng, "Y")["reliability_score"], 0.5)
        recompute_reliability_scores(engine=eng)
        row = _row(eng, "Y")
        self.assertEqual(row["reliability_score"], 0.5)
        self.assertEqual(row["citation_count"], 0)

    def test_criterion5_idempotent(self):
        eng = _engine()
        _seed_chunk(eng, "X")
        for i in range(6):
            _seed_trace(eng, f"t{i}", ["X"])
        for i in range(3):
            _seed_feedback(eng, f"t{i}", "rejected")
        recompute_reliability_scores(engine=eng)
        first = dict(_row(eng, "X"))
        recompute_reliability_scores(engine=eng)
        second = dict(_row(eng, "X"))
        self.assertEqual(first["reliability_score"], second["reliability_score"])
        self.assertEqual(first["citation_count"], second["citation_count"])
        self.assertEqual(first["rejection_count"], second["rejection_count"])

    def test_only_rejected_verdict_counts_as_rejection(self):
        eng = _engine()
        _seed_chunk(eng, "X")
        _seed_trace(eng, "t1", ["X"]); _seed_feedback(eng, "t1", "approved")
        _seed_trace(eng, "t2", ["X"]); _seed_feedback(eng, "t2", "edited")
        _seed_trace(eng, "t3", ["X"]); _seed_feedback(eng, "t3", "rejected")
        recompute_reliability_scores(engine=eng)
        row = _row(eng, "X")
        self.assertEqual(row["citation_count"], 3)
        self.assertEqual(row["rejection_count"], 1)

    def test_non_immigration_traces_are_ignored(self):
        eng = _engine()
        _seed_chunk(eng, "X")
        _seed_trace(eng, "p1", ["X"], feature_key="policy_assistant")
        _seed_feedback(eng, "p1", "rejected")
        recompute_reliability_scores(engine=eng)
        row = _row(eng, "X")
        self.assertEqual(row["citation_count"], 0)   # policy trace did not count
        self.assertEqual(row["reliability_score"], 0.5)

    def test_chunk_ref_wrapper_and_dedup(self):
        eng = _engine()
        _seed_chunk(eng, "X")
        # "[chunk:X]" wrapper normalises to X; X cited twice in one trace counts once.
        _seed_trace(eng, "t1", ["[chunk:X]", "X"])
        recompute_reliability_scores(engine=eng)
        self.assertEqual(_row(eng, "X")["citation_count"], 1)


class ReliabilityFactorBlendTests(unittest.TestCase):
    """The RELIABILITY_WEIGHT blend: factor = (1-w) + w*reliability."""

    def setUp(self):
        self._orig = cfg.RELIABILITY_WEIGHT
        self.addCleanup(lambda: setattr(cfg, "RELIABILITY_WEIGHT", self._orig))

    def test_weight_zero_is_dormant(self):
        cfg.RELIABILITY_WEIGHT = 0.0
        self.assertEqual(reliability_factor(0.2), 1.0)   # bad chunk -> no effect
        self.assertEqual(reliability_factor(0.9), 1.0)

    def test_weight_one_is_full_effect(self):
        cfg.RELIABILITY_WEIGHT = 1.0
        self.assertAlmostEqual(reliability_factor(0.2), 0.2)
        self.assertAlmostEqual(reliability_factor(None), cfg.NEUTRAL_RELIABILITY)

    def test_weight_half_is_midpoint(self):
        cfg.RELIABILITY_WEIGHT = 0.5
        # (1-0.5) + 0.5*0.2 = 0.6
        self.assertAlmostEqual(reliability_factor(0.2), 0.6)


class RetrieverRankingTests(unittest.TestCase):
    # Pin ranking "now" to the fixture fetched_at so freshness stays 1.0.
    # Wall-clock now after 90 days applies a 0.85 decay (CI 2026-09-06: 0.68 vs 0.8).
    _NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)

    def setUp(self):
        self._orig = cfg.RELIABILITY_WEIGHT
        self.addCleanup(lambda: setattr(cfg, "RELIABILITY_WEIGHT", self._orig))

    def _chunk(self, cid, reliability):
        return {"id": cid, "score": 0.8, "trust_tier": 1,
                "fetched_at": "2026-06-06T00:00:00+00:00", "reliability_score": reliability}

    def test_default_weight_is_dormant_no_reranking(self):
        # Ships safe: at the default weight (0), reliability does NOT change ranking.
        cfg.RELIABILITY_WEIGHT = 0.0
        low = self._chunk("low", 0.2)
        high = self._chunk("high", 0.9)
        ranked = _apply_quality_gates(
            [low, high], min_similarity=0.0, top_k=2, now=self._NOW)
        # Equal raw/tier/freshness, reliability ignored -> equal adjusted scores.
        self.assertAlmostEqual(ranked[0]["adjusted_score"], ranked[1]["adjusted_score"])
        self.assertAlmostEqual(ranked[0]["adjusted_score"], 0.8)  # 0.8 * 1 * 1 * 1

    def test_criterion3_high_reliability_ranks_first_when_enabled(self):
        cfg.RELIABILITY_WEIGHT = 1.0
        low = self._chunk("low", 0.2)
        high = self._chunk("high", 0.9)
        ranked = _apply_quality_gates(
            [low, high], min_similarity=0.0, top_k=2, now=self._NOW)
        self.assertEqual(ranked[0]["id"], "high")
        self.assertGreater(ranked[0]["adjusted_score"], ranked[1]["adjusted_score"])

    def test_full_weight_missing_reliability_uses_neutral(self):
        cfg.RELIABILITY_WEIGHT = 1.0
        c = {"id": "c", "score": 0.8, "trust_tier": 1, "fetched_at": "2026-06-06T00:00:00+00:00"}
        ranked = _apply_quality_gates(
            [c], min_similarity=0.0, top_k=1, now=self._NOW)
        # 0.8 raw * 1.0 tier * 1.0 freshness * 0.5 neutral = 0.4
        self.assertAlmostEqual(ranked[0]["adjusted_score"], 0.4)


if __name__ == "__main__":
    unittest.main()

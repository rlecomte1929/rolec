"""
Task 5 / Admin-Hardening — gate the daily source-reliability recompute.

Covers two requirements:
  (a) When ``source_reliability_autoapply`` setting is ``"0"`` the apply
      step is skipped entirely — no immigration_corpus_chunks rows are
      mutated; a proposal/audit record is emitted instead.
  (b) When the setting is ``"1"`` (default) the behavior is identical to
      the original service (scores are written, summary has no
      ``proposed_only`` key).

Uses unittest.mock.patch to control the platform setting rather than
inserting rows, because the test SQLite DB has no ``platform_settings``
table (the migration is committed-not-applied).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services.source_reliability_service import recompute_reliability_scores

# ── Shared schema helpers (mirrors test_source_reliability_service.py) ──────

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

_PATCH_TARGET = "backend.app.services.source_reliability_service.get_setting"


def _engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with eng.begin() as c:
        c.execute(text(_CHUNKS_SCHEMA))
        c.execute(text(_TRACES_SCHEMA))
        c.execute(text(_FEEDBACK_SCHEMA))
    return eng


def _seed_chunk(eng, cid):
    with eng.begin() as c:
        c.execute(
            text("INSERT INTO immigration_corpus_chunks (id) VALUES (:id)"), {"id": cid}
        )


def _seed_trace(eng, tid, cited, feature_key="immigration_answer"):
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO policy_assistant_traces (id, feature_key, cited_chunk_ids) "
                "VALUES (:id, :fk, :cc)"
            ),
            {"id": tid, "fk": feature_key, "cc": json.dumps(cited)},
        )


def _seed_feedback(eng, tid, verdict):
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO ai_human_feedback (id, trace_session_id, verdict) "
                "VALUES (:id, :t, :v)"
            ),
            {"id": f"fb-{tid}", "t": tid, "v": verdict},
        )


def _row(eng, cid):
    with eng.begin() as c:
        return c.execute(
            text(
                "SELECT reliability_score, citation_count, rejection_count, "
                "last_reliability_update "
                "FROM immigration_corpus_chunks WHERE id = :id"
            ),
            {"id": cid},
        ).mappings().one()


# ── Tests ────────────────────────────────────────────────────────────────────


class GateOffTests(unittest.TestCase):
    """Requirement (a): setting='0' → apply is SKIPPED, scores unchanged."""

    def test_gate_off_does_not_mutate_reliability_score(self):
        eng = _engine()
        _seed_chunk(eng, "A")
        for i in range(5):
            _seed_trace(eng, f"t{i}", ["A"])
        for i in range(3):
            _seed_feedback(eng, f"t{i}", "rejected")

        with patch(_PATCH_TARGET, return_value="0"):
            result = recompute_reliability_scores(engine=eng)

        row = _row(eng, "A")
        self.assertEqual(
            row["reliability_score"], 0.5,
            "reliability_score must stay neutral — no mutation allowed when gate=off",
        )

    def test_gate_off_does_not_mutate_citation_count(self):
        eng = _engine()
        _seed_chunk(eng, "A2")
        for i in range(5):
            _seed_trace(eng, f"s{i}", ["A2"])

        with patch(_PATCH_TARGET, return_value="0"):
            recompute_reliability_scores(engine=eng)

        row = _row(eng, "A2")
        self.assertEqual(
            row["citation_count"], 0,
            "citation_count must stay 0 when gate=off",
        )
        self.assertIsNone(
            row["last_reliability_update"],
            "last_reliability_update must not be written when gate=off",
        )

    def test_gate_off_summary_marks_proposed_only(self):
        eng = _engine()
        _seed_chunk(eng, "A3")

        with patch(_PATCH_TARGET, return_value="0"):
            result = recompute_reliability_scores(engine=eng)

        self.assertEqual(
            result.get("autoapply"), "0",
            "summary must carry autoapply='0' in propose-only mode",
        )
        self.assertTrue(
            result.get("proposed_only"),
            "summary must have proposed_only=True in propose-only mode",
        )


class GateOnTests(unittest.TestCase):
    """Requirement (b): setting='1' (default) → behavior unchanged, scores written."""

    def test_gate_on_writes_reliability_score(self):
        eng = _engine()
        _seed_chunk(eng, "B")
        for i in range(10):
            _seed_trace(eng, f"u{i}", ["B"])
        for i in range(8):
            _seed_feedback(eng, f"u{i}", "rejected")

        with patch(_PATCH_TARGET, return_value="1"):
            result = recompute_reliability_scores(engine=eng)

        row = _row(eng, "B")
        self.assertEqual(row["citation_count"], 10)
        self.assertEqual(row["rejection_count"], 8)
        self.assertLess(row["reliability_score"], 0.3)
        self.assertIsNotNone(row["last_reliability_update"])

    def test_gate_on_summary_has_no_proposed_only(self):
        eng = _engine()
        _seed_chunk(eng, "B2")

        with patch(_PATCH_TARGET, return_value="1"):
            result = recompute_reliability_scores(engine=eng)

        self.assertNotIn(
            "proposed_only", result,
            "summary must NOT have proposed_only when gate=on",
        )


class GateDefaultTests(unittest.TestCase):
    """When no setting exists at all (table absent, no env var), default='1' applies."""

    def test_no_setting_table_applies_as_before(self):
        """get_setting falls through to default='1' when platform_settings absent."""
        eng = _engine()
        # No platform_settings table in SQLite test DB → get_setting returns "1".
        _seed_chunk(eng, "C")
        for i in range(10):
            _seed_trace(eng, f"v{i}", ["C"])

        result = recompute_reliability_scores(engine=eng)

        row = _row(eng, "C")
        self.assertEqual(row["citation_count"], 10)
        self.assertEqual(row["reliability_score"], 1.0)
        self.assertNotIn("proposed_only", result)


if __name__ == "__main__":
    unittest.main()

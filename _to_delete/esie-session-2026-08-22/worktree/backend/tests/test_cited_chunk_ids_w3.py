"""
W3 / AIQ-837 — cited_chunk_ids persisted on policy_assistant_traces and
joinable to ai_human_feedback.

Prod-safe: this checkout's .env points DATABASE_URL at prod, so the trace DB
write is mocked (no prod write) and the round-trip + join is validated on an
isolated in-memory SQLite engine (never the shared `db`).
"""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("POLICY_ASSISTANT_EMBEDDER", "hash")
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

from sqlalchemy import create_engine, text

import backend.database as dbmod
from backend.app.services.ai_trace_logger import TraceSession


class TestCitedChunkIdsWiring(unittest.TestCase):
    def test_flush_passes_cited_chunk_ids_to_db(self):
        ts = TraceSession(
            session_id="s1", query="q", company_id="co1", feature_key="policy_assistant"
        )
        ts.record_citations(["c1", "c2"])
        with patch.object(dbmod.db, "insert_policy_assistant_trace") as m:
            ts.flush()
        self.assertTrue(m.called)
        self.assertEqual(m.call_args.kwargs["cited_chunk_ids"], ["c1", "c2"])

    def test_flush_defaults_to_empty_list(self):
        ts = TraceSession(
            session_id=None, query="q", company_id="co1", feature_key="policy_assistant"
        )
        with patch.object(dbmod.db, "insert_policy_assistant_trace") as m:
            ts.flush()  # no record_citations call
        self.assertEqual(m.call_args.kwargs["cited_chunk_ids"], [])

    def test_record_citations_coerces_to_str(self):
        ts = TraceSession(
            session_id=None, query="q", company_id="co1", feature_key="policy_assistant"
        )
        ts.record_citations(None)
        self.assertEqual(ts.cited_chunk_ids, [])
        ts.record_citations(["a", 2])
        self.assertEqual(ts.cited_chunk_ids, ["a", "2"])


class TestCitedChunkIdsJoin(unittest.TestCase):
    """Validates the storage shape + feedback->trace join recipe on isolated SQLite."""

    def test_roundtrip_and_join_to_feedback(self):
        eng = create_engine("sqlite://")
        with eng.begin() as c:
            c.execute(text(
                "CREATE TABLE policy_assistant_traces "
                "(id TEXT PRIMARY KEY, cited_chunk_ids TEXT NOT NULL DEFAULT '[]')"
            ))
            c.execute(text(
                "CREATE TABLE ai_human_feedback (trace_session_id TEXT, verdict TEXT)"
            ))
            c.execute(
                text("INSERT INTO policy_assistant_traces (id, cited_chunk_ids) VALUES (:i, :c)"),
                {"i": "trace-1", "c": json.dumps(["c1", "c2"])},
            )
            c.execute(text(
                "INSERT INTO ai_human_feedback (trace_session_id, verdict) VALUES ('trace-1', 'reject')"
            ))
            # The W3 join recipe: chunks cited in rejected answers.
            row = c.execute(text(
                "SELECT t.cited_chunk_ids FROM ai_human_feedback f "
                "JOIN policy_assistant_traces t ON t.id = f.trace_session_id "
                "WHERE f.verdict = 'reject'"
            )).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row[0]), ["c1", "c2"])


if __name__ == "__main__":
    unittest.main()

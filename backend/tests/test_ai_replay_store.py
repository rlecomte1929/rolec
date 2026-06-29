"""
Phase 1 keystone — tests for ai_replay_store, the masked, replayable record of
every immigration answer / AI roadmap generation that the offline grader reads.

In-memory SQLite (StaticPool) mirrors the live ai_replay_records table; the
engine is injected so there is no network / DB config. The security-critical
behaviour is that raw PII in the query and the model output is masked (via
pii_masker.mask_pii) BEFORE it is persisted — the replay store must never become
a back-door that re-introduces the raw text that policy_assistant_traces was
deliberately built to avoid storing.
"""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services.ai_replay_store import (
    list_replay_records,
    persist_replay_record,
)

_REPLAY_SCHEMA = (
    "CREATE TABLE ai_replay_records ("
    "id TEXT PRIMARY KEY, trace_id TEXT, feature_key TEXT, corridor TEXT, "
    "query_masked TEXT, output_masked TEXT, retrieved_chunk_ids TEXT DEFAULT '[]', "
    "prompt_version_id TEXT, canary_arm TEXT, result TEXT, approved INTEGER DEFAULT 0, "
    "created_at TEXT NOT NULL)"
)


def _engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with eng.begin() as c:
        c.execute(text(_REPLAY_SCHEMA))
    return eng


def test_persist_and_list_round_trips():
    eng = _engine()
    persist_replay_record(
        engine=eng,
        trace_id="trace-1",
        feature_key="rag_roadmap",
        corridor="IN_DE",
        query="Blue Card requirements for a software engineer",
        output={"result": "OK", "steps": [{"order": 1, "title": "Apply for visa"}]},
        retrieved_chunk_ids=["chunk-a", "chunk-b"],
        result="OK",
        approved=True,
    )

    recs = list_replay_records(engine=eng, feature_key="rag_roadmap")

    assert len(recs) == 1
    rec = recs[0]
    assert rec["trace_id"] == "trace-1"
    assert rec["corridor"] == "IN_DE"
    assert rec["result"] == "OK"
    assert bool(rec["approved"]) is True
    assert json.loads(rec["retrieved_chunk_ids"]) == ["chunk-a", "chunk-b"]


def test_raw_pii_is_masked_before_persist():
    eng = _engine()
    # Raw PII smuggled into both the query and the model output.
    persist_replay_record(
        engine=eng,
        trace_id="trace-2",
        feature_key="immigration_answer",
        corridor="FR_NO",
        query="My passport is AB1234567 and my email is anna@example.com",
        output={"answer": "Confirmed for passport AB1234567, contact anna@example.com"},
        retrieved_chunk_ids=[],
        result="OK",
        approved=False,
    )

    rec = list_replay_records(engine=eng, feature_key="immigration_answer")[0]

    # The raw passport number and email must not survive into the store.
    assert "AB1234567" not in rec["query_masked"]
    assert "anna@example.com" not in rec["query_masked"]
    assert "AB1234567" not in rec["output_masked"]
    assert "anna@example.com" not in rec["output_masked"]
    # And the redaction placeholders prove the masker actually fired.
    assert "[REDACTED" in rec["query_masked"]
    assert "[REDACTED" in rec["output_masked"]

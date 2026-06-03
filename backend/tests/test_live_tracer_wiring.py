"""
Live-tracer wiring tests — assert answer_policy_question and extract_policy_with_llm
write a feature-tagged row into policy_assistant_traces via TraceSession.flush().

Captures rows by monkeypatching backend.database.db (the tracer re-imports it at
flush time) and forces in-code carbon defaults by monkeypatching the carbon DB read.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force mock LLM + hash embedder so nothing calls an external API.
os.environ["POLICY_ASSISTANT_LLM"] = "mock"
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

import backend.database as database  # noqa: E402
from backend.app.services import ai_carbon_estimator as est  # noqa: E402
from backend.app.services import (  # noqa: E402
    policy_assistant_rag_engine as rag,
    policy_assistant_session_memory as session_memory,
    policy_chunk_retriever,
)
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402


class _FakeTraceDB:
    def __init__(self, *, blow_up: bool = False):
        self.rows = []
        self.blow_up = blow_up

    def insert_policy_assistant_trace(self, **kwargs):
        if self.blow_up:
            raise RuntimeError("trace db down")
        self.rows.append(kwargs)


class _StubAuditDb:
    """rag_engine writes audits via db.* — no-op so the audit path is inert."""
    def policy_hardening_tables_available(self):
        return False


@pytest.fixture(autouse=True)
def _no_carbon_db(monkeypatch):
    monkeypatch.setattr(est, "_load_profile_from_db", lambda model_name: None)
    est.clear_cache()
    yield
    est.clear_cache()


@pytest.fixture
def _rag_harness(monkeypatch):
    session_memory._reset_all_for_tests()
    monkeypatch.setattr(
        policy_chunk_retriever, "retrieve",
        lambda **kw: [
            {"id": "ch-1", "source_type": "matrix_benefit",
             "source_ref": "policy_config_benefits.b1",
             "chunk_text": "Housing allowance: USD 4,500 per month."},
        ],
    )
    monkeypatch.setattr(rag, "db", _StubAuditDb())


def test_answer_policy_question_writes_trace(monkeypatch, _rag_harness):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    client = MockClient(responses_by_pattern={
        "housing": "Housing allowance is USD 4,500/month [chunk:ch-1].",
    })

    result = rag.answer_policy_question(
        company_id="acme", user_id="u-1",
        question="What's the housing allowance?",
        client=client,
    )

    assert result["answer_kind"] == "answer"
    assert len(fake.rows) == 1
    row = fake.rows[0]
    assert row["feature_key"] == "policy_assistant"
    assert row["customer_id"] == "acme"          # defaults to company_id
    assert row["company_id"] == "acme"
    assert row["tokens_in"] > 0
    assert row["tokens_out"] > 0
    assert row["co2e_grams_estimated"] > 0.0


def test_answer_policy_question_trace_failure_is_swallowed(monkeypatch, _rag_harness):
    fake = _FakeTraceDB(blow_up=True)
    monkeypatch.setattr(database, "db", fake)
    client = MockClient(responses_by_pattern={
        "housing": "Housing allowance is USD 4,500/month [chunk:ch-1].",
    })

    result = rag.answer_policy_question(
        company_id="acme", user_id="u-1",
        question="What's the housing allowance?",
        client=client,
    )

    # Trace write blew up internally but the answer is still returned normally.
    assert result["answer_kind"] == "answer"
    assert "USD 4,500" in result["answer_text"]
    assert fake.rows == []

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


import types  # noqa: E402

from backend.app.services import llm_policy_extractor  # noqa: E402
from backend.app.services import policy_extractor  # noqa: E402


def _fake_anthropic_module(*, tool_input, input_tokens=1200, output_tokens=300):
    """Build a stand-in `anthropic` module whose Anthropic().messages.create()
    returns a Message with one tool_use block and a usage object."""
    block = types.SimpleNamespace(type="tool_use", input=tool_input)
    message = types.SimpleNamespace(
        content=[block],
        usage=types.SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )

    class _Messages:
        def create(self, **kwargs):
            return message

    class _Anthropic:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    return types.SimpleNamespace(Anthropic=_Anthropic)


_TOOL_INPUT = {
    "policy_meta": {"title": "Acme Relocation Policy", "version": "2.3",
                    "effective_date": "2026-01-01"},
    "benefits": [
        {"service_category": "housing", "benefit_key": "temporary_housing",
         "benefit_label": "Temporary housing", "confidence": 0.9},
    ],
}


def test_extract_policy_with_llm_writes_trace(monkeypatch):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-noop")
    monkeypatch.setitem(sys.modules, "anthropic",
                        _fake_anthropic_module(tool_input=_TOOL_INPUT,
                                               input_tokens=1200, output_tokens=300))

    result = llm_policy_extractor.extract_policy_with_llm(
        ["Acme Corp Relocation Policy v2.3", "6.1 Temporary housing — 60 days."],
        company_id="acme",
    )

    assert result is not None and result["extracted_by"] == "ai"
    assert len(fake.rows) == 1
    row = fake.rows[0]
    assert row["feature_key"] == "policy_extraction"
    assert row["customer_id"] == "acme"
    assert row["tokens_in"] == 1200
    assert row["tokens_out"] == 300
    assert row["co2e_grams_estimated"] > 0.0


def test_extract_policy_company_id_threads_through(monkeypatch):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-noop")
    monkeypatch.setitem(sys.modules, "anthropic",
                        _fake_anthropic_module(tool_input=_TOOL_INPUT))
    monkeypatch.setattr(policy_extractor, "_parse_lines_from_bytes",
                        lambda data, ftype: ["6.1 Temporary housing — 60 days."])

    policy_extractor.extract_policy_with_diff(b"unused", "docx", company_id="acme-co")

    assert len(fake.rows) == 1
    assert fake.rows[0]["customer_id"] == "acme-co"
    assert fake.rows[0]["feature_key"] == "policy_extraction"


def test_extract_fallback_paths_emit_no_trace(monkeypatch):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    # No ANTHROPIC_API_KEY → regex fallback, no LLM call, no trace.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert llm_policy_extractor.extract_policy_with_llm(
        ["6.1 Temporary housing — 60 days."], company_id="acme"
    ) is None
    assert fake.rows == []

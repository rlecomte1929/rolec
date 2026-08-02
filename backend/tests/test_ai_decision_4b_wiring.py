"""AIQ-1694·4b — the coordinator and precedent-insight paths record a masked
'produced' row to the human-oversight audit trail.

These tests spy on ``record_ai_recommendation`` (the shared audit helper, already
covered end-to-end by test_ai_decision_logger / test_ai_decision_audit_e2e) and
assert each production path calls it with the right feature, tenant, and — for the
coordinator's free-text answer — masked output. No DB is stood up here; the helper's
own masking/insert behaviour is proven in its dedicated tests.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.app.services import ai_decision_logger
from backend.app.services import coordinator_agent
from backend.app.routers import exception_requests


@pytest.fixture
def spy(monkeypatch) -> List[Dict[str, Any]]:
    """Capture every record_ai_recommendation kwargs dict; patch the source module
    so the lazy `from ..services.ai_decision_logger import record_ai_recommendation`
    in both call sites resolves to the spy."""
    calls: List[Dict[str, Any]] = []

    def _spy(**kwargs):
        calls.append(kwargs)
        return "rec-id"

    monkeypatch.setattr(ai_decision_logger, "record_ai_recommendation", _spy)
    return calls


# --------------------------------------------------------------------------- #
# Coordinator
# --------------------------------------------------------------------------- #
def test_coordinator_turn_logs_masked_answer(monkeypatch, spy):
    ctx = {"case": {"company_id": "company-a"}}

    class _DummyTrace:
        def __init__(self, *a, **k): ...
        def record_llm_call(self, *a, **k): ...
        def flush(self, *a, **k): ...

    monkeypatch.setattr(coordinator_agent, "coordinator_enabled", lambda **k: True)
    monkeypatch.setattr(coordinator_agent, "build_coordinator_context_for_case", lambda *a, **k: ctx)
    monkeypatch.setattr(coordinator_agent.store, "get_or_create", lambda *a, **k: {"model": "claude-sonnet-4-6"})
    monkeypatch.setattr(coordinator_agent, "_breaker_model", lambda *a, **k: "claude-sonnet-4-6")
    monkeypatch.setattr(coordinator_agent, "_render", lambda *a, **k: "prompt")
    monkeypatch.setattr(coordinator_agent, "TraceSession", _DummyTrace)
    monkeypatch.setattr(coordinator_agent, "_persist_turn", lambda *a, **k: None)

    # The model answer echoes a phone number — it MUST be masked before it lands in
    # the audit row (a conversational answer is free text, unlike structured recs).
    answer = "Call your relocation lead at +33 6 12 34 56 78 to confirm."

    class _Client:
        def complete(self, *a, **k):
            return {"text": answer, "usage": {}, "model": "claude-sonnet-4-6"}

    monkeypatch.setattr(coordinator_agent, "get_default_client", lambda: _Client())

    out = coordinator_agent.respond("case-1", "when do I move?", employee_id="emp-9")

    assert out and out["answer"] == answer  # the human still gets the real answer
    assert len(spy) == 1
    call = spy[0]
    assert call["feature"] == "ai_coordinator"
    assert call["company_id"] == "company-a"
    assert call["actor_id"] == "emp-9"
    assert call["skip_if_exists"] is True
    # the stored answer is masked — the raw phone number is gone
    assert "+33 6 12 34 56 78" not in call["ai_output"]["answer"]
    assert "612345678".replace(" ", "") not in call["ai_output"]["answer"].replace(" ", "")


def test_coordinator_skips_log_when_no_company(monkeypatch, spy):
    monkeypatch.setattr(coordinator_agent, "coordinator_enabled", lambda **k: True)
    monkeypatch.setattr(coordinator_agent, "build_coordinator_context_for_case", lambda *a, **k: {"case": {}})
    monkeypatch.setattr(coordinator_agent.store, "get_or_create", lambda *a, **k: {"model": "m"})
    monkeypatch.setattr(coordinator_agent, "_breaker_model", lambda *a, **k: "m")
    monkeypatch.setattr(coordinator_agent, "_render", lambda *a, **k: "p")

    class _DummyTrace:
        def __init__(self, *a, **k): ...
        def record_llm_call(self, *a, **k): ...
        def flush(self, *a, **k): ...

    monkeypatch.setattr(coordinator_agent, "TraceSession", _DummyTrace)
    monkeypatch.setattr(coordinator_agent, "_persist_turn", lambda *a, **k: None)
    monkeypatch.setattr(coordinator_agent, "get_default_client",
                        lambda: type("C", (), {"complete": lambda self, *a, **k: {"text": "hi", "usage": {}, "model": "m"}})())

    coordinator_agent.respond("case-1", "hi", employee_id="emp-9")
    assert spy == []  # no tenant → nothing logged (can't scope the audit row)


# --------------------------------------------------------------------------- #
# Precedent insight
# --------------------------------------------------------------------------- #
def test_precedent_insight_logs_with_stable_id(monkeypatch, spy):
    insight = {"source_version": "precedent_v1", "recommended_action": "approve",
               "confidence": 0.6, "rationale": "2 of 3 similar requests approved",
               "similar_case_ids": ["c1", "c2"]}
    monkeypatch.setattr(exception_requests, "compute_precedent_insight", lambda *a, **k: dict(insight))

    row = {"status": "pending", "id": "req-42", "organization_id": "company-a",
           "category": "cap_override", "benefit_key": "international_school"}
    out = exception_requests._attach_precedent_insight(object(), row)

    assert out["precedent_insight"]["recommendation_id"] == "precedent_v1:req-42"
    assert len(spy) == 1
    call = spy[0]
    assert call["feature"] == "precedent_insight"
    assert call["company_id"] == "company-a"
    assert call["recommendation_id"] == "precedent_v1:req-42"  # stable per request
    assert call["skip_if_exists"] is True  # re-render writes at most one row
    assert call["input_context"]["exception_request_id"] == "req-42"


def test_precedent_insight_no_log_for_decided_row(monkeypatch, spy):
    # decided rows are skipped before the insight is even computed
    row = {"status": "approved", "id": "req-9", "organization_id": "company-a"}
    exception_requests._attach_precedent_insight(object(), row)
    assert spy == []

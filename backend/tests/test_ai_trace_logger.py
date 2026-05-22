"""
Tests for backend/services/ai_trace_logger.py — P5-8.

Verifies:
- TraceSession records steps correctly
- query_hash is SHA-256 derived and never the raw query
- PII policy: raw query never appears in flush output
- flush() never raises even on broken DB
- record_retrieval, record_llm_call, record_step helpers all work
- mark_fallback sets fallback_triggered
"""
from __future__ import annotations

import hashlib
import json
import logging
from unittest.mock import MagicMock, patch

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.ai_trace_logger import TraceSession, TraceStep  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

RAW_QUERY = "What is my housing allowance cap?"
COMPANY_ID = "test-company-abc"
SESSION_ID = "sess-123"


def make_tracer(**kwargs) -> TraceSession:
    defaults = dict(session_id=SESSION_ID, query=RAW_QUERY, company_id=COMPANY_ID)
    defaults.update(kwargs)
    return TraceSession(**defaults)


# --------------------------------------------------------------------------- #
# PII policy                                                                   #
# --------------------------------------------------------------------------- #

def test_query_hash_is_sha256_not_raw_query():
    tracer = make_tracer()
    expected_hash = hashlib.sha256(RAW_QUERY.encode("utf-8")).hexdigest()[:16]
    assert tracer.query_hash == expected_hash
    assert RAW_QUERY not in tracer.query_hash


def test_raw_query_not_in_trace_id():
    tracer = make_tracer()
    assert RAW_QUERY not in tracer.trace_id


# --------------------------------------------------------------------------- #
# Step recording                                                               #
# --------------------------------------------------------------------------- #

def test_record_retrieval():
    tracer = make_tracer()
    tracer.record_retrieval(top_scores=[0.92, 0.87, 0.81, 0.75, 0.70, 0.60], latency_ms=210)
    assert len(tracer._steps) == 1
    step = tracer._steps[0]
    assert step.step == "retrieval"
    assert step.latency_ms == 210
    assert step.payload["top_5_scores"] == [0.92, 0.87, 0.81, 0.75, 0.70]  # capped at 5


def test_record_llm_call():
    tracer = make_tracer()
    tracer.record_llm_call(
        model="claude-sonnet-4-6",
        input_tokens=2100,
        output_tokens=340,
        latency_ms=1800,
    )
    assert len(tracer._steps) == 1
    step = tracer._steps[0]
    assert step.step == "llm_call"
    assert step.latency_ms == 1800
    assert step.payload["model"] == "claude-sonnet-4-6"
    assert step.payload["input_tokens"] == 2100
    assert step.payload["output_tokens"] == 340


def test_record_step_generic():
    tracer = make_tracer()
    tracer.record_step("input_guardrails", latency_ms=12, triggers=[], passed=True)
    step = tracer._steps[0]
    assert step.step == "input_guardrails"
    assert step.latency_ms == 12
    assert step.payload["triggers"] == []
    assert step.payload["passed"] is True


def test_start_step_finish():
    tracer = make_tracer()
    step = tracer.start_step("classifier")
    step.finish(decision="hr_policy")
    assert step.step == "classifier"
    assert step.latency_ms >= 0
    assert step.payload["decision"] == "hr_policy"


def test_mark_fallback():
    tracer = make_tracer()
    assert tracer.fallback_triggered is False
    tracer.mark_fallback(reason="validation_failed_twice")
    assert tracer.fallback_triggered is True
    # mark_fallback with reason adds a step
    assert any(s.step == "fallback" for s in tracer._steps)


def test_to_dict_includes_all_fields():
    tracer = make_tracer()
    tracer.record_retrieval(top_scores=[0.9], latency_ms=100)
    step = tracer._steps[0]
    d = step.to_dict()
    assert d["step"] == "retrieval"
    assert d["latency_ms"] == 100
    assert "top_5_scores" in d


# --------------------------------------------------------------------------- #
# flush — never raises                                                         #
# --------------------------------------------------------------------------- #

def test_flush_never_raises_on_broken_db(caplog):
    tracer = make_tracer()
    tracer.record_retrieval(top_scores=[0.9], latency_ms=100)
    tracer.record_llm_call(
        model="claude-sonnet-4-6", input_tokens=500, output_tokens=100, latency_ms=400
    )

    # Patch the DB write to explode.
    with patch("backend.services.ai_trace_logger._write_to_db", side_effect=RuntimeError("db down")):
        # Should not raise.
        tracer.flush()


def test_flush_emits_structured_log(caplog):
    tracer = make_tracer()
    tracer.record_retrieval(top_scores=[0.87], latency_ms=200)
    tracer.record_llm_call(
        model="claude-haiku-4-5-20251001", input_tokens=800, output_tokens=120, latency_ms=600
    )

    with caplog.at_level(logging.INFO, logger="backend.services.ai_trace_logger"):
        with patch("backend.services.ai_trace_logger._write_to_db"):
            with patch("backend.services.ai_trace_logger._forward_to_langsmith"):
                tracer.flush()

    # At least one log record should contain "ai_trace"
    assert any("ai_trace" in r.message for r in caplog.records)


def test_flush_log_does_not_contain_raw_query(caplog):
    query = "My secret salary question £££"
    tracer = TraceSession(session_id=None, query=query, company_id=COMPANY_ID)
    tracer.record_step("validation", latency_ms=5, passed=True)

    with caplog.at_level(logging.INFO, logger="backend.services.ai_trace_logger"):
        with patch("backend.services.ai_trace_logger._write_to_db"):
            with patch("backend.services.ai_trace_logger._forward_to_langsmith"):
                tracer.flush()

    log_text = " ".join(r.message for r in caplog.records)
    assert query not in log_text, "Raw query must NOT appear in trace logs"


def test_flush_payload_structure(caplog):
    tracer = make_tracer()
    tracer.record_retrieval(top_scores=[0.9, 0.8], latency_ms=150)
    tracer.record_llm_call(
        model="claude-sonnet-4-6", input_tokens=1000, output_tokens=200, latency_ms=900
    )
    tracer.record_step("validation", latency_ms=5, passed=True, answer_kind="answer")

    with caplog.at_level(logging.INFO, logger="backend.services.ai_trace_logger"):
        with patch("backend.services.ai_trace_logger._write_to_db"):
            with patch("backend.services.ai_trace_logger._forward_to_langsmith"):
                tracer.flush()

    ai_trace_log = next(r.message for r in caplog.records if "ai_trace" in r.message)
    json_part = ai_trace_log[len("ai_trace "):]
    data = json.loads(json_part)

    assert data["session_id"] == SESSION_ID
    assert data["query_hash"] == tracer.query_hash
    assert data["fallback_triggered"] is False
    assert data["total_latency_ms"] >= 0

    step_names = [s["step"] for s in data["steps"]]
    assert "retrieval" in step_names
    assert "llm_call" in step_names
    assert "validation" in step_names


# --------------------------------------------------------------------------- #
# LangSmith skips gracefully when not installed                               #
# --------------------------------------------------------------------------- #

def test_langsmith_forward_skips_when_no_key():
    """When LANGSMITH_API_KEY is unset, forward is a no-op."""
    import os
    os.environ.pop("LANGSMITH_API_KEY", None)

    from backend.services.ai_trace_logger import _forward_to_langsmith
    # Should not raise even if langsmith is not installed.
    _forward_to_langsmith({"trace_id": "abc", "steps": [], "fallback_triggered": False})

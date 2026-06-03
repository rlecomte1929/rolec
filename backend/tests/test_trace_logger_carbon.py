"""
Tests for TraceSession unit-economics on flush — Parker Step G.

flush() must sum tokens, USD cost (router costs.yaml) and estimated CO₂e across the
trace's llm_call steps and persist them via insert_policy_assistant_trace. A fake db
captures the kwargs; the carbon DB read is monkeypatched out (in-code defaults).
"""
from __future__ import annotations

import logging
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as database  # noqa: E402
from backend.app.services import ai_carbon_estimator as est  # noqa: E402
from backend.app.services.ai_trace_logger import TraceSession  # noqa: E402


class _FakeDB:
    def __init__(self, *, blow_up: bool = False):
        self.rows = []
        self.blow_up = blow_up

    def insert_policy_assistant_trace(self, **kwargs):
        if self.blow_up:
            raise RuntimeError("db down")
        self.rows.append(kwargs)


@pytest.fixture(autouse=True)
def _no_carbon_db(monkeypatch):
    monkeypatch.setattr(est, "_load_profile_from_db", lambda model_name: None)
    est.clear_cache()
    yield
    est.clear_cache()


def test_flush_persists_cost_carbon_and_tokens(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(database, "db", fake)

    t = TraceSession(
        session_id="s-1", query="q", company_id="acme",
        feature_key="policy_assistant", customer_id="cust-1",
    )
    t.record_llm_call(model="gpt-4o", input_tokens=1000, output_tokens=500, latency_ms=100)
    t.flush()

    assert len(fake.rows) == 1
    row = fake.rows[0]
    assert row["feature_key"] == "policy_assistant"
    assert row["customer_id"] == "cust-1"
    assert row["tokens_in"] == 1000
    assert row["tokens_out"] == 500
    # gpt-4o costs.yaml: 2.50/M in, 10.00/M out → 0.0025 + 0.005 = 0.0075.
    assert row["cost_usd_estimated"] == pytest.approx(0.0075, abs=1e-6)
    assert row["co2e_grams_estimated"] == pytest.approx(0.088889, abs=1e-6)


def test_customer_id_defaults_to_company_id(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(database, "db", fake)
    t = TraceSession(session_id=None, query="q", company_id="acme", feature_key="policy_extraction")
    assert t.customer_id == "acme"
    t.record_llm_call(model="gpt-4o", input_tokens=10, output_tokens=10, latency_ms=1)
    t.flush()
    assert fake.rows[0]["customer_id"] == "acme"


def test_unknown_model_still_flushes_with_zero_cost_and_warns(monkeypatch, caplog):
    fake = _FakeDB()
    monkeypatch.setattr(database, "db", fake)
    t = TraceSession(session_id=None, query="q", company_id="acme", feature_key="passport_ocr")
    with caplog.at_level(logging.WARNING):
        t.record_llm_call(model="mystery-model", input_tokens=100, output_tokens=50, latency_ms=5)
        t.flush()
    row = fake.rows[0]
    # No costs.yaml entry → cost 0.0; carbon still computed from the global default.
    assert row["cost_usd_estimated"] == 0.0
    assert row["co2e_grams_estimated"] > 0.0
    assert any("no energy profile" in r.message for r in caplog.records)


def test_flush_never_raises_when_db_write_fails(monkeypatch):
    fake = _FakeDB(blow_up=True)
    monkeypatch.setattr(database, "db", fake)
    t = TraceSession(session_id=None, query="q", company_id="acme", feature_key="policy_assistant")
    t.record_llm_call(model="gpt-4o", input_tokens=10, output_tokens=10, latency_ms=1)
    t.flush()  # must not raise
    assert fake.rows == []


def test_no_llm_call_yields_zeroed_economics(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(database, "db", fake)
    t = TraceSession(session_id=None, query="q", company_id="acme", feature_key="policy_assistant")
    t.record_step("classifier", latency_ms=5, decision="x")
    t.flush()
    row = fake.rows[0]
    assert row["tokens_in"] == 0
    assert row["tokens_out"] == 0
    assert row["cost_usd_estimated"] == 0.0
    assert row["co2e_grams_estimated"] == 0.0

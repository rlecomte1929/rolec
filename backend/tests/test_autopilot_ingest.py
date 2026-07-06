"""Autopilot Phase 1 — ingest + dedup + auto-dispatch.

Governor, DB, LLM, Notion and cost-tracing are all monkeypatched; no network/DB writes.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.app.services import autopilot_ingest as ing
from backend.app.services.autopilot_governor import GateDecision


# ── dedup / cluster ──────────────────────────────────────────────────────────

def test_dedup_key_prefers_fingerprint():
    row = {"category": "bug", "page_url": "/a",
           "client_context": {"recentErrors": [{"fingerprint": "abc123"}]}}
    assert ing.dedup_key(row) == "fp:abc123"


def test_dedup_key_falls_back_to_attrs():
    row = {"category": "bug", "page_url": "/journey?x=1", "client_context": {}}
    k1 = ing.dedup_key(row)
    k2 = ing.dedup_key({"category": "bug", "page_url": "/journey?y=2", "client_context": {}})
    assert k1.startswith("attr:") and k1 == k2  # query-stripped route → same cluster


def test_cluster_groups_and_picks_richest_representative():
    rows = [
        {"id": "1", "category": "bug", "page_url": "/a",
         "client_context": {"recentErrors": [{"fingerprint": "fp1"}]}},
        {"id": "2", "category": "bug", "page_url": "/a",
         "client_context": {"recentErrors": [{"fingerprint": "fp1"}],
                            "recentFailedRequests": [{"path": "/api/x", "status": 500}]}},
        {"id": "3", "category": "idea", "page_url": "/b", "client_context": {}},
    ]
    clusters = ing.cluster(rows)
    by_key = {c["key"]: c for c in clusters}
    assert by_key["fp:fp1"]["size"] == 2
    assert by_key["fp:fp1"]["representative"]["id"] == "2"   # richest diagnostics wins


def test_build_failure_evidence_carries_signal():
    row = {"page_url": "/journey", "client_context": {
        "route": "/journey", "appVersion": "abc",
        "recentErrors": [{"failingFrame": "saveCase", "message": "boom", "fingerprint": "fp1"}],
        "recentFailedRequests": [{"method": "GET", "path": "/api/x", "status": 500, "requestId": "r1"}],
    }}
    fe = ing.build_failure_evidence(row, 3)
    assert "Reported 3×" in fe and "saveCase" in fe and "/api/x → 500" in fe and "req r1" in fe


# ── orchestrator ─────────────────────────────────────────────────────────────

class _FakeResult:
    def fetchall(self):
        return []


class _FakeSession:
    def __init__(self):
        self.executed = []

    def execute(self, *a, **k):
        self.executed.append((a, k))
        return _FakeResult()

    def commit(self):
        pass

    def close(self):
        pass


_ROWS = [
    {"id": "1", "message": "save broke", "category": "bug", "page_url": "/journey", "reporter_name": None,
     "client_context": {"recentErrors": [{"fingerprint": "fp1", "failingFrame": "save"}]}},
    {"id": "2", "message": "save broke too", "category": "bug", "page_url": "/journey", "reporter_name": None,
     "client_context": {"recentErrors": [{"fingerprint": "fp1"}]}},
    {"id": "3", "message": "other bug", "category": "bug", "page_url": "/hr", "reporter_name": None,
     "client_context": {"recentErrors": [{"fingerprint": "fp2"}]}},
]


def _allow(monkeypatch, allowed=True):
    monkeypatch.setattr(ing, "gate",
                        lambda stage, session=None: GateDecision(allowed, "ok" if allowed else "off", 1.0, 25.0))
    monkeypatch.setattr(ing, "_query_candidates", lambda s, lookback_hours: list(_ROWS))


def test_run_ingest_halts_when_gate_denied(monkeypatch):
    _allow(monkeypatch, allowed=False)
    out = ing.run_ingest(session=_FakeSession())
    assert out["halted"] is True and out["dispatched"] == 0


def test_run_ingest_dry_run_dedups_without_side_effects(monkeypatch):
    _allow(monkeypatch)
    # engineer_task / create_work_queue_task must NOT be called in dry-run.
    monkeypatch.setattr(ing, "engineer_task", lambda **k: pytest.fail("LLM called in dry-run"))
    out = ing.run_ingest(dry_run=True, session=_FakeSession())
    assert out["halted"] is False and out["dry_run"] is True
    assert out["raw"] == 3 and out["unique_clusters"] == 2   # fp1 collapses 2 → 1
    assert out["planned"] == 2 and out["dispatched"] == 0


def test_run_ingest_dispatches_representatives(monkeypatch):
    _allow(monkeypatch)
    calls = {"engineer": 0, "notion": 0}

    def _fake_engineer(**k):
        calls["engineer"] += 1
        return {"title": "t", "complexity": "Low", "layer": "UI"}

    monkeypatch.setattr(ing, "engineer_task", _fake_engineer)
    monkeypatch.setattr(ing.nwq, "create_work_queue_task",
                        lambda task, **k: (calls.__setitem__("notion", calls["notion"] + 1) or "https://notion.so/pg"))

    class _StubTracer:
        def __init__(self, *a, **k): pass
        def record_llm_call(self, **k): pass
        def flush(self): pass

    monkeypatch.setattr(ing, "TraceSession", _StubTracer)

    sess = _FakeSession()
    out = ing.run_ingest(dry_run=False, session=sess)
    assert out["unique_clusters"] == 2 and out["dispatched"] == 2 and out["errors"] == 0
    assert calls["engineer"] == 2 and calls["notion"] == 2
    # one feedback_status UPSERT per dispatched representative
    assert len(sess.executed) == 2


# ── endpoint ─────────────────────────────────────────────────────────────────

def test_ingest_endpoint_requires_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    from backend.main import app
    r = TestClient(app).post("/api/crons/autopilot-ingest", json={"dry_run": True})
    assert r.status_code == 401


def test_ingest_endpoint_calls_run_ingest(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    monkeypatch.setattr(ing, "run_ingest", lambda **k: {"halted": False, "dry_run": k.get("dry_run"), "dispatched": 0})
    from backend.main import app
    r = TestClient(app).post("/api/crons/autopilot-ingest",
                             headers={"Authorization": "Bearer s3cret"}, json={"dry_run": True})
    assert r.status_code == 200, r.text
    assert r.json()["dry_run"] is True

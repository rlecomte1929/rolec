"""Parker-J: NLG router — auth, payload, env-flag gating."""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app.routers.nlg as nlg  # noqa: E402
from backend.app.auth_deps import get_current_user, require_admin_or_hr  # noqa: E402
from backend.app.services.nlg.data_to_text import KPI, KPISet  # noqa: E402


HR_USER = {"id": "hr-1", "role": "HR", "is_admin": False, "company_id": "co-1"}


def _make_client(user):
    app = FastAPI()
    app.include_router(nlg.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_admin_or_hr] = lambda: user
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(nlg.EXEC_SUMMARY_PROVIDER_ENV, raising=False)


# ── exec-summary ──────────────────────────────────────────────────────────

def test_exec_summary_unauth_401():
    app = FastAPI()
    app.include_router(nlg.router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/hr/co-1/exec-summary")
    assert resp.status_code == 401


def test_exec_summary_hr_own_company(monkeypatch):
    monkeypatch.setattr(
        nlg, "load_company_kpis",
        lambda cid: KPISet("Q2 2026", [KPI("active", "Active assignments", 140, prior=120)]),
    )
    client = _make_client(HR_USER)
    resp = client.get("/api/hr/co-1/exec-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "data_to_text"
    assert "Active assignments" in body["summary"]
    assert body["company_id"] == "co-1"


def test_exec_summary_cross_company_403(monkeypatch):
    monkeypatch.setattr(nlg, "load_company_kpis", lambda cid: KPISet("Q2", []))
    client = _make_client(HR_USER)
    resp = client.get("/api/hr/co-OTHER/exec-summary")
    assert resp.status_code == 403


def test_exec_summary_admin_any_company(monkeypatch):
    admin = {"id": "a", "role": "ADMIN", "is_admin": True, "company_id": None}
    monkeypatch.setattr(
        nlg, "load_company_kpis",
        lambda cid: KPISet("Q2", [KPI("active", "Active assignments", 5)]),
    )
    client = _make_client(admin)
    resp = client.get("/api/hr/any-co/exec-summary")
    assert resp.status_code == 200


def test_exec_summary_llm_flag_defers(monkeypatch):
    monkeypatch.setenv(nlg.EXEC_SUMMARY_PROVIDER_ENV, "llm")
    client = _make_client(HR_USER)
    resp = client.get("/api/hr/co-1/exec-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "llm"
    assert body["summary"] is None


# ── load_company_kpis (regression: was querying a non-existent column) ──────

def test_load_company_kpis_builds_nonempty_set(monkeypatch):
    """load_company_kpis must source from get_command_center_kpis and yield
    real KPIs — the old hand-rolled query referenced case_assignments.company_id
    (no such column), threw, and rendered a misleading 'no KPIs' summary."""
    monkeypatch.setattr(
        nlg.db, "get_command_center_kpis",
        lambda company_id=None, hr_user_id=None: {
            "activeCases": 22, "atRiskCount": 1,
            "attentionNeededCount": 3, "completedCount": 0,
        },
    )
    kpis = nlg.load_company_kpis("co-1")
    labels = {k.label: k.current for k in kpis.kpis}
    assert labels["Active cases"] == 22
    assert labels["At-risk cases"] == 1
    assert labels["Cases needing attention"] == 3
    assert labels["Completed this year"] == 0
    summary = nlg.d2t.summarise_kpis(kpis, audience="exec")
    assert "No KPIs were reported" not in summary
    assert "Active cases" in summary


def test_load_company_kpis_uses_behind_schedule_when_risk_flags_are_zero(monkeypatch):
    monkeypatch.setattr(
        nlg.db, "get_command_center_kpis",
        lambda company_id=None, hr_user_id=None: {
            "activeCases": 30, "atRiskCount": 0,
            "attentionNeededCount": 0, "completedCount": 0,
        },
    )
    monkeypatch.setattr(
        "backend.app.services.case_health_scan.list_behind_cases_for_company",
        lambda company_id: [{"case_id": "a"}, {"case_id": "b"}, {"case_id": "c"}],
    )
    kpis = nlg.load_company_kpis("co-1")
    labels = {k.label: k.current for k in kpis.kpis}
    assert labels["At-risk cases"] == 3
    assert labels["Cases needing attention"] == 3


def test_load_company_kpis_failure_is_safe(monkeypatch):
    """A failure in the aggregator degrades to an empty set, never raises."""
    def _boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(nlg.db, "get_command_center_kpis", _boom)
    kpis = nlg.load_company_kpis("co-1")
    assert list(kpis.kpis) == []


# ── policy tldr ───────────────────────────────────────────────────────────

def test_tldr_unauth_401():
    app = FastAPI()
    app.include_router(nlg.router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/policies/p-1/tldr")
    assert resp.status_code == 401


def test_tldr_returns_summary(monkeypatch):
    long_doc = " ".join(
        f"Sentence {i} about housing budgets and tax equalisation for tier caps."
        for i in range(40)
    ) + " The cafeteria serves lunch at noon."
    monkeypatch.setattr(nlg, "load_policy_text", lambda pid: long_doc)
    client = _make_client(HR_USER)
    resp = client.get("/api/policies/p-1/tldr")
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_id"] == "p-1"
    assert body["sentence_count"] <= 5
    assert body["source_chars"] == len(long_doc)
    assert len(body["summary"]) > 0


def test_tldr_unknown_policy_404(monkeypatch):
    monkeypatch.setattr(nlg, "load_policy_text", lambda pid: None)
    client = _make_client(HR_USER)
    resp = client.get("/api/policies/missing/tldr")
    assert resp.status_code == 404

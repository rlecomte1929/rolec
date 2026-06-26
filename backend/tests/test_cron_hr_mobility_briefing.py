"""[AIQ-1220] Tests for the weekly HR mobility-briefing cron + service.

Validation Criteria:
  * cron-secret enforcement: 503 (unset) / 401 (wrong) / 200 (correct),
  * the service composes the right per-company payload (active-assignment counts,
    at-risk count = risk-flagged + behind-schedule, deadline count),
  * dry_run composes payloads but sends NO email,
  * to_override redirects every send to one address,
  * a company with no admin email is skipped (not sent),
  * NO LLM is invoked in the cron path.

All data-source helpers and the Resend send are mocked — no DB/network is hit.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app.routers.crons as crons  # noqa: E402
import backend.app.services.hr_mobility_briefing_service as svc  # noqa: E402

_SECRET = "test-cron-secret"
_PATH = "/api/crons/hr-mobility-briefing"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(crons.router)
    return TestClient(app, raise_server_exceptions=False)


# ── fixtures: mock every data source so no DB/network is touched ─────────────

@pytest.fixture
def _mock_sources(monkeypatch):
    companies = [
        {"company_id": "co-1", "company_name": "Acme", "admin_email": "admin@acme.test"},
        {"company_id": "co-2", "company_name": "NoEmailCo", "admin_email": None},
    ]
    monkeypatch.setattr(svc, "list_active_companies", lambda: list(companies))
    monkeypatch.setattr(
        svc, "_assignments_by_status",
        lambda cid: [{"status": "assigned", "count": 5}, {"status": "awaiting_intake", "count": 2}],
    )
    monkeypatch.setattr(
        svc, "_risk_flagged_assignments",
        lambda cid: [{"id": "a1", "case_id": "c1", "employee_name": "Jane Doe",
                      "status": "assigned", "risk_status": "yellow", "expected_start_date": "2026-07-01"}],
    )
    monkeypatch.setattr(
        svc, "_behind_schedule_cases",
        lambda cid: [{"case_id": "c9", "stage": "visa_decision", "days_behind": 8}],
    )
    monkeypatch.setattr(
        svc, "_upcoming_deadlines",
        lambda cid, win: [{"form_id": "f1", "form_name": "Visa application",
                           "authority_name": "Ausländerbehörde", "deadline": "2026-07-10", "status": "in_progress"}],
    )
    return companies


@pytest.fixture
def _capture_send(monkeypatch):
    sent = []
    monkeypatch.setattr(svc, "_deliver", lambda to, subject, html, text: sent.append((to, subject)) or True)
    return sent


# ── cron-secret enforcement ─────────────────────────────────────────────────

def test_cron_secret_unset_returns_503(monkeypatch, _mock_sources, _capture_send):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    resp = _client().post(_PATH, headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 503


def test_cron_secret_wrong_returns_401(monkeypatch, _mock_sources, _capture_send):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    resp = _client().post(_PATH, headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_cron_secret_correct_returns_200(monkeypatch, _mock_sources, _capture_send):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    resp = _client().post(_PATH, headers={"Authorization": f"Bearer {_SECRET}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── payload composition ─────────────────────────────────────────────────────

def test_build_company_briefing_counts(_mock_sources):
    payload = svc.build_company_briefing(_mock_sources[0])
    assert payload["company_id"] == "co-1"
    assert payload["active_assignments"]["total"] == 7  # 5 + 2
    assert payload["active_assignments"]["by_status"][0]["status"] == "assigned"
    # at-risk = 1 risk-flagged + 1 behind-schedule
    assert payload["at_risk"]["count"] == 2
    assert payload["upcoming_deadlines"]["count"] == 1
    # rendered both formats; key facts present in plain text
    assert "Jane Doe" in payload["text"]
    assert "Visa application" in payload["text"]
    assert payload["subject"] == "Weekly mobility briefing — Acme"
    assert payload["html"].startswith("<!DOCTYPE html>")


# ── send / skip / dry_run / to_override behaviour ───────────────────────────

def test_send_skips_company_without_admin_email(_mock_sources, _capture_send):
    result = svc.run_hr_mobility_briefing()
    assert result["companies"] == 2
    assert result["emails_sent"] == 1   # only Acme
    assert result["skipped"] == 1       # NoEmailCo
    assert result["errors"] == 0
    assert _capture_send == [("admin@acme.test", "Weekly mobility briefing — Acme")]


def test_dry_run_sends_nothing_but_returns_payloads(_mock_sources, _capture_send):
    result = svc.run_hr_mobility_briefing(dry_run=True)
    assert result["dry_run"] is True
    assert result["emails_sent"] == 0
    assert _capture_send == []          # _deliver never called
    assert len(result["previews"]) == 1  # only the company with a recipient
    preview = result["previews"][0]
    assert preview["to"] == "admin@acme.test"
    assert preview["active_total"] == 7
    assert preview["at_risk_count"] == 2


def test_to_override_redirects_all_sends(_mock_sources, _capture_send):
    # to_override makes even the no-admin-email company deliverable, to one inbox.
    result = svc.run_hr_mobility_briefing(to_override="beta@relopass.com")
    assert result["emails_sent"] == 2
    assert result["skipped"] == 0
    assert {to for to, _ in _capture_send} == {"beta@relopass.com"}


def test_only_company_id_restricts_run(_mock_sources, _capture_send):
    result = svc.run_hr_mobility_briefing(only_company_id="co-1")
    assert result["companies"] == 1
    assert result["emails_sent"] == 1


# ── delivery fallback: no RESEND_API_KEY → logs, does not call network ───────

def test_deliver_logs_when_no_resend_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    called = {"post": False}
    monkeypatch.setattr(svc.http_requests, "post", lambda *a, **k: called.__setitem__("post", True))
    ok = svc._deliver("x@y.test", "subj", "<p>h</p>", "h")
    assert ok is True
    assert called["post"] is False  # logged, no network call


# ── guardrail: cron path imports/uses no LLM client ─────────────────────────

def test_no_llm_in_service_module():
    import inspect
    source = inspect.getsource(svc)
    for needle in ("llm_client", "openai", "anthropic", "complete_text", "roadmap_generator"):
        assert needle not in source, f"LLM reference {needle!r} must not appear in the briefing cron path"

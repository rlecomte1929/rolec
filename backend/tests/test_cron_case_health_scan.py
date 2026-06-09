"""AIQ-378b (AIQ-817) — tests for the nightly case-health scan cron + dispatch.

Validation Criteria:
  * cron-secret enforcement: 503 (unset) / 401 (wrong) / 200 (correct),
  * a behind-schedule case produces exactly one ops_notification,
  * re-running uses the same per-case dedupe key (so ops_notifications dedupes).
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app.routers.crons as crons  # noqa: E402
import backend.app.services.case_health_scan as chs  # noqa: E402
import backend.app.services.ops_notification_service as ops  # noqa: E402
import backend.app.services.monitoring_alerts as alerts  # noqa: E402

_SECRET = "test-cron-secret"
_PATH = "/api/crons/case-health-scan"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(crons.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def _no_flagged(monkeypatch):
    monkeypatch.setattr(chs, "scan_active_cases", lambda *a, **k: [])


# ── cron-secret enforcement ─────────────────────────────────────────────────

def test_cron_secret_unset_returns_503(monkeypatch, _no_flagged):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    resp = _client().post(_PATH, headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 503


def test_cron_secret_wrong_returns_401(monkeypatch, _no_flagged):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    resp = _client().post(_PATH, headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_cron_secret_correct_returns_200(monkeypatch, _no_flagged):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    resp = _client().post(_PATH, headers={"Authorization": f"Bearer {_SECRET}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["flagged"] == 0 and body["notifications"] == 0


# ── dispatch: one deduped notification per behind case ──────────────────────

def _flagged_one():
    return [{
        "case_id": "case-123", "stage": "visa_decision",
        "expected_date": "2026-06-01", "days_behind": 8, "severity": "critical",
    }]


def test_behind_case_creates_exactly_one_notification(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    monkeypatch.setattr(chs, "scan_active_cases", lambda *a, **k: _flagged_one())
    calls = []
    monkeypatch.setattr(
        ops, "create_or_update_notification",
        lambda ntype, sev, title, msg, dedupe_key, **kw: calls.append((ntype, sev, dedupe_key, kw)) or {"id": "n1"},
    )
    monkeypatch.setattr(alerts, "dispatch_monitoring_alert", lambda *a, **k: {"slack": False, "email": False})

    resp = _client().post(_PATH, headers={"Authorization": f"Bearer {_SECRET}"})
    assert resp.status_code == 200
    assert resp.json()["notifications"] == 1
    assert len(calls) == 1
    ntype, sev, dedupe_key, kw = calls[0]
    assert ntype == "case_behind_schedule"
    assert sev == "critical"
    assert dedupe_key == "case_behind_schedule|case:case-123"   # one notification per case
    assert kw.get("payload", {}).get("days_behind") == 8


def test_rerun_uses_same_dedupe_key(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    monkeypatch.setattr(chs, "scan_active_cases", lambda *a, **k: _flagged_one())
    keys = []
    monkeypatch.setattr(
        ops, "create_or_update_notification",
        lambda ntype, sev, title, msg, dedupe_key, **kw: keys.append(dedupe_key) or {"id": "n1"},
    )
    monkeypatch.setattr(alerts, "dispatch_monitoring_alert", lambda *a, **k: {})

    c = _client()
    c.post(_PATH, headers={"Authorization": f"Bearer {_SECRET}"})
    c.post(_PATH, headers={"Authorization": f"Bearer {_SECRET}"})
    # Same stable per-case key on both runs → ops_notification_service dedupes.
    assert keys == ["case_behind_schedule|case:case-123", "case_behind_schedule|case:case-123"]


def test_notification_failure_does_not_abort_scan(monkeypatch):
    """A notification error for one case is counted and the cron stays 200."""
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    monkeypatch.setattr(chs, "scan_active_cases", lambda *a, **k: _flagged_one())

    def _boom(*a, **k):
        raise RuntimeError("supabase down")
    monkeypatch.setattr(ops, "create_or_update_notification", _boom)
    monkeypatch.setattr(alerts, "dispatch_monitoring_alert", lambda *a, **k: {})

    resp = _client().post(_PATH, headers={"Authorization": f"Bearer {_SECRET}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["notifications"] == 0 and body["errors"] == 1

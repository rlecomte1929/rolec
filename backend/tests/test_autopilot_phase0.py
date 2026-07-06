"""Autopilot Phase 0 — safety-rail primitives (all additive, flag-gated OFF, unwired).

Covers: PII residue scrub in engineer_task, Final Validation Result writer, the governor
kill-switch/budget gate (fail-closed), the diagnostics-replay canary, and the read-only
/api/crons/autopilot-canary endpoint. No network/Notion/DB is touched (all monkeypatched).
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.app.services import autopilot_canary as canary
from backend.app.services import autopilot_governor as gov
from backend.app.services import feedback_task_engineer as fte
from backend.app.services import notion_work_queue as nwq


# ── PII hardening ────────────────────────────────────────────────────────────

def test_scrub_redacts_email_and_long_digits():
    out = fte._scrub("mail jane@acme.com id 123456789")
    assert "jane@acme.com" not in out
    assert "123456789" not in out


def test_scrub_residue_guard_covers_mask_fail_open(monkeypatch):
    # Simulate mask_pii failing open (returning raw text): the residue sweep must still redact.
    monkeypatch.setattr(fte, "mask_pii", lambda t: t)
    out = fte._scrub("reach me at jane@acme.com or 0612345678")
    assert "jane@acme.com" not in out
    assert "0612345678" not in out
    assert "[REDACTED]" in out


def test_engineer_task_masks_message_and_reporter(monkeypatch):
    captured = {}

    def _fake_llm(*, system, user, **_k):
        captured["user"] = user
        return ('{"title":"Fix save","strategic_objective":"x","execution_prompt":"y",'
                '"expected_output":"z","validation_criteria":"v","test_command":"",'
                '"technical_constraints":"","files_to_touch":"","risk_rollback":"",'
                '"priority":"P2","complexity":"Low","task_type":"Frontend Implementation",'
                '"layer":"UI","product_area":"Core Product"}')

    monkeypatch.setattr(fte, "claude_complete_text_sync", _fake_llm)
    task = fte.engineer_task(
        text="broke, email me jane@acme.com or 0612345678",
        category="bug", page_url="/journey", severity="medium", area="ui",
        has_screenshot=False, reporter_name="jane@acme.com", admin_context="see logs",
    )
    assert task["status"] == "Ready for AI"
    assert "jane@acme.com" not in captured["user"]      # message + reporter both scrubbed
    assert "0612345678" not in captured["user"]


# ── Final Validation Result writer ───────────────────────────────────────────

def test_set_validation_result_rejects_bad_value():
    with pytest.raises(ValueError):
        nwq.set_validation_result("pg-1", "Maybe")


def test_set_validation_result_patches_notion(monkeypatch):
    seen = {}
    monkeypatch.setattr(nwq, "_notion_api", lambda method, url, payload=None: seen.update(method=method, url=url, payload=payload))
    nwq.set_validation_result("pg-1", "Passed", notes="canary ok")
    assert seen["method"] == "PATCH"
    assert seen["payload"]["properties"]["Final Validation Result"]["select"]["name"] == "Passed"
    assert "Execution Notes" in seen["payload"]["properties"]


# ── Governor: kill-switch + budget (fail-safe) ───────────────────────────────

def _flags(**vals):
    return lambda key, env_default=False: vals.get(key, False)


def test_gate_master_flag_off(monkeypatch):
    monkeypatch.setattr(gov, "resolve_flag_safe", _flags())  # everything off
    d = gov.gate("dispatch")
    assert d.allowed is False and "master flag off" in d.reason


def test_gate_stage_flag_off(monkeypatch):
    monkeypatch.setattr(gov, "resolve_flag_safe", _flags(AUTOPILOT_ENABLED=True))
    d = gov.gate("dispatch")
    assert d.allowed is False and "stage flag" in d.reason


def test_gate_allows_under_budget(monkeypatch):
    monkeypatch.setattr(gov, "resolve_flag_safe",
                        _flags(AUTOPILOT_ENABLED=True, AUTOPILOT_DISPATCH_ENABLED=True))
    monkeypatch.setattr(gov, "month_to_date_spend_usd", lambda session=None: 1.0)
    monkeypatch.setenv("AUTOPILOT_MONTHLY_USD_CAP", "25")
    d = gov.gate("dispatch")
    assert d.allowed is True and d.remaining_usd == pytest.approx(24.0)


def test_gate_halts_at_budget(monkeypatch):
    monkeypatch.setattr(gov, "resolve_flag_safe",
                        _flags(AUTOPILOT_ENABLED=True, AUTOPILOT_DISPATCH_ENABLED=True))
    monkeypatch.setattr(gov, "month_to_date_spend_usd", lambda session=None: 30.0)
    monkeypatch.setenv("AUTOPILOT_MONTHLY_USD_CAP", "25")
    d = gov.gate("dispatch")
    assert d.allowed is False and "budget reached" in d.reason


def test_gate_fails_closed_on_spend_error(monkeypatch):
    monkeypatch.setattr(gov, "resolve_flag_safe",
                        _flags(AUTOPILOT_ENABLED=True, AUTOPILOT_DISPATCH_ENABLED=True))

    def _boom(session=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(gov, "month_to_date_spend_usd", _boom)
    d = gov.gate("dispatch")
    assert d.allowed is False and "fail-closed" in d.reason


# ── Canary: diagnostics replay (idempotent-only, honest inconclusive) ────────

def test_canary_passes_when_signal_resolved(monkeypatch):
    def _status(method, url, *, auth_token=None, timeout=10):
        return 200 if url.endswith("/health") else 200

    monkeypatch.setattr(canary, "_http_status", _status)
    res = canary.run_canary(base_url="https://x", failing_requests=[{"method": "GET", "path": "/api/a", "status": 500}])
    assert res.passed is True and res.conclusive is True


def test_canary_fails_when_still_5xx(monkeypatch):
    monkeypatch.setattr(canary, "_http_status",
                        lambda m, u, *, auth_token=None, timeout=10: 200 if u.endswith("/health") else 500)
    res = canary.run_canary(base_url="https://x", failing_requests=[{"method": "GET", "path": "/api/a", "status": 500}])
    assert res.passed is False


def test_canary_skips_non_idempotent(monkeypatch):
    monkeypatch.setattr(canary, "_http_status", lambda m, u, *, auth_token=None, timeout=10: 200)
    res = canary.run_canary(base_url="https://x", failing_requests=[{"method": "POST", "path": "/api/a", "status": 500}])
    assert res.passed is True and res.checks[1].ok is None and "non-idempotent" in res.checks[1].detail


def test_canary_auth_wall_is_inconclusive(monkeypatch):
    monkeypatch.setattr(canary, "_http_status",
                        lambda m, u, *, auth_token=None, timeout=10: 200 if u.endswith("/health") else 401)
    res = canary.run_canary(base_url="https://x", failing_requests=[{"method": "GET", "path": "/api/a", "status": 500}])
    assert res.passed is True and res.checks[1].ok is None and res.conclusive is False


def test_failing_requests_from_context_filters_actionable():
    ctx = {"recentFailedRequests": [
        {"method": "GET", "path": "/a", "status": 500},
        {"method": "GET", "path": "/b", "status": 404},   # client error → not actionable
        {"method": "GET", "path": "/c", "status": 0},     # network error → actionable
    ]}
    picked = canary.failing_requests_from_context(ctx)
    assert [r["path"] for r in picked] == ["/a", "/c"]


# ── Endpoint: /api/crons/autopilot-canary (cron-secret gated, read-only) ─────

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    from backend.main import app
    return TestClient(app)


def test_canary_endpoint_requires_secret(client):
    r = client.post("/api/crons/autopilot-canary", json={"failing_requests": []})
    assert r.status_code == 401


def test_canary_endpoint_dry_run(client):
    r = client.post(
        "/api/crons/autopilot-canary",
        headers={"Authorization": "Bearer s3cret"},
        json={"dry_run": True, "base_url": "https://x",
              "failing_requests": [{"method": "get", "path": "/api/a", "status": 500}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["would_replay"][0] == {"method": "GET", "path": "/api/a", "was": 500}


def test_canary_endpoint_runs(client, monkeypatch):
    monkeypatch.setattr(canary, "_http_status", lambda m, u, *, auth_token=None, timeout=10: 200)
    r = client.post(
        "/api/crons/autopilot-canary",
        headers={"Authorization": "Bearer s3cret"},
        json={"base_url": "https://x", "failing_requests": [{"method": "GET", "path": "/api/a", "status": 500}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is True

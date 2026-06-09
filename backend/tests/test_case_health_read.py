"""AIQ-378d (AIQ-819) — tests for the tenant-scoped case-health read layer.

list_behind_cases_for_company must return ONLY the company's own behind-schedule
cases (an alert for another company's case is excluded), project the payload
fields, and degrade to [] safely.
"""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import case_health_scan as chs  # noqa: E402
from backend.app.services import ops_notification_service as ops  # noqa: E402


def _notif(case_id, days_behind=8, stage="visa_decision", severity="critical"):
    return {
        "notification_type": "case_behind_schedule",
        "status": "open",
        "payload_json": json.dumps({
            "case_id": case_id, "stage": stage, "days_behind": days_behind,
            "expected_date": "2026-06-01", "severity": severity,
            "suggested_action": "Follow up with the authority.",
            "draft_reminder": "Quick check-in...",
        }),
    }


def test_empty_when_company_has_no_cases(monkeypatch):
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: set())
    assert chs.list_behind_cases_for_company("co-1") == []


def test_empty_company_id_returns_empty():
    assert chs.list_behind_cases_for_company("") == []


def test_only_this_companys_cases_are_returned(monkeypatch):
    # company owns case-A and case-C; case-B belongs to another tenant.
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: {"case-A", "case-C"})
    monkeypatch.setattr(
        ops, "list_ops_notifications",
        lambda **kw: {"items": [_notif("case-A", 5), _notif("case-B", 99), _notif("case-C", 12)], "total": 3},
    )
    out = chs.list_behind_cases_for_company("co-1")
    ids = [c["case_id"] for c in out]
    assert "case-B" not in ids                 # tenant isolation
    assert set(ids) == {"case-A", "case-C"}
    assert ids == ["case-C", "case-A"]         # sorted most-behind first
    # payload fields projected
    assert out[0]["days_behind"] == 12
    assert out[0]["stage"] == "visa_decision"
    assert out[0]["suggested_action"] == "Follow up with the authority."


def test_list_failure_degrades_to_empty(monkeypatch):
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: {"case-A"})

    def _boom(**kw):
        raise RuntimeError("supabase down")
    monkeypatch.setattr(ops, "list_ops_notifications", _boom)
    assert chs.list_behind_cases_for_company("co-1") == []


def test_requests_only_open_case_behind_schedule(monkeypatch):
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: {"case-A"})
    captured = {}
    monkeypatch.setattr(
        ops, "list_ops_notifications",
        lambda **kw: captured.update(kw) or {"items": [_notif("case-A")], "total": 1},
    )
    chs.list_behind_cases_for_company("co-1")
    assert captured.get("notification_type") == "case_behind_schedule"
    assert captured.get("open_only") is True

"""AIQ-378d (AIQ-819) — tests for the tenant-scoped case-health read layer.

list_behind_cases_for_company must return ONLY the company's own behind-schedule
cases (another tenant's case is excluded), project the signal fields, and degrade
to [] safely.

[AIQ-2041] The source changed: this used to read back the ops-notifications raised
by the nightly scan, which made the HR panel depend on a cron gated behind
CASE_HEALTH_CRON_ENABLED — a repo variable
`docs/findings/AIQ-2012-cron-gates-never-set.md` records as never set. It now
computes live from the delay signal, so these tests drive `scan_active_cases`
rather than `list_ops_notifications`. Every invariant the old tests asserted
(tenant isolation, most-behind-first ordering, field projection, safe degradation)
is preserved below.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import case_delay_monitor as cdm  # noqa: E402
from backend.app.services import case_health_scan as chs  # noqa: E402
from backend.app.services import ops_notification_service as ops  # noqa: E402


def _sig(case_id, days_behind=8, stage="visa_decision", severity="critical",
         title="", owner=""):
    """One scan_active_cases() row (DelaySignal.as_dict shape)."""
    return {
        "case_id": case_id,
        "stage": stage,
        "expected_date": "2026-06-01",
        "days_behind": days_behind,
        "severity": severity,
        "title": title,
        "owner": owner,
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
        cdm, "scan_active_cases",
        lambda *a, **k: [_sig("case-A", 5), _sig("case-B", 99), _sig("case-C", 12)],
    )
    out = chs.list_behind_cases_for_company("co-1")
    ids = [c["case_id"] for c in out]
    assert "case-B" not in ids                 # tenant isolation
    assert set(ids) == {"case-A", "case-C"}
    assert ids == ["case-C", "case-A"]         # sorted most-behind first
    assert out[0]["days_behind"] == 12
    assert out[0]["stage"] == "visa_decision"
    # suggested_action is derived here now, not carried in from a notification
    assert out[0]["suggested_action"]


def test_scan_failure_degrades_to_empty(monkeypatch):
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: {"case-A"})

    def _boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(cdm, "scan_active_cases", _boom)
    assert chs.list_behind_cases_for_company("co-1") == []


def test_read_does_not_depend_on_the_notification_pipeline(monkeypatch):
    """The point of AIQ-2041: the panel must not go dark because a cron never ran.

    If this read ever queries ops_notifications again, the HR surface silently
    re-acquires a dependency on CASE_HEALTH_CRON_ENABLED being set.
    """
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: {"case-A"})
    monkeypatch.setattr(cdm, "scan_active_cases", lambda *a, **k: [_sig("case-A", 4)])

    def _must_not_be_called(**kw):
        raise AssertionError("read layer queried ops_notifications")
    monkeypatch.setattr(ops, "list_ops_notifications", _must_not_be_called)

    out = chs.list_behind_cases_for_company("co-1")
    assert [c["case_id"] for c in out] == ["case-A"]


def test_milestone_title_and_owner_are_projected(monkeypatch):
    """`stage` alone is an opaque key for most milestone types — see AIQ-2041."""
    monkeypatch.setattr(chs, "_company_case_ids", lambda c: {"case-A"})
    monkeypatch.setattr(
        cdm, "scan_active_cases",
        lambda *a, **k: [_sig("case-A", 6, stage="pre_departure_ai_01",
                              title="Gather core identity and employment documents",
                              owner="employee")],
    )
    row = chs.list_behind_cases_for_company("co-1")[0]
    assert row["milestone_title"] == "Gather core identity and employment documents"
    assert row["owner"] == "employee"
    assert "Gather core identity" in row["suggested_action"]

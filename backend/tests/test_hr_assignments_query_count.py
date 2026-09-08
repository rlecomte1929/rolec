"""WS2 Task 2.3 — query-count characterisation for GET /api/hr/assignments.

The 2025-03 list optimisation dropped per-row ``get_latest_compliance_report``
and returned ``complianceStatus=None`` (see docs/performance/hr-list-optimization-results.md).
The remaining work is to bulk-load the latest report per assignment in one
SELECT and restore ``overallStatus`` on the summary.

Auth is overridden; the recorder wraps backend.database.db / backend.main.db.
The handler still issues two inline ``db.engine.connect()`` SELECTs (cases +
wizard profiles); those are not db-method calls and are stubbed via a fake engine.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient

import backend.database as database_mod
import backend.main as bm
from backend.main import app, get_current_user

HR = {
    "id": "hr-1",
    "email": "hr@example.test",
    "role": "HR",
    "is_admin": False,
}

COMPANY_ID = "co-1"

# Three rows so a per-row get_latest_compliance_report would be visible (N=3).
ASSIGNMENTS = [
    {
        "id": "asg-1",
        "case_id": "case-1",
        "canonical_case_id": "case-1",
        "employee_identifier": "a@example.test",
        "status": "assigned",
        "submitted_at": "2026-01-01T00:00:00",
        "employee_first_name": "Ada",
        "employee_last_name": "One",
    },
    {
        "id": "asg-2",
        "case_id": "case-2",
        "canonical_case_id": "case-2",
        "employee_identifier": "b@example.test",
        "status": "assigned",
        "submitted_at": "2026-01-02T00:00:00",
        "employee_first_name": "Bob",
        "employee_last_name": "Two",
    },
    {
        "id": "asg-3",
        "case_id": "case-3",
        "canonical_case_id": "case-3",
        "employee_identifier": "c@example.test",
        "status": "assigned",
        "submitted_at": "2026-01-03T00:00:00",
        "employee_first_name": "Cara",
        "employee_last_name": "Three",
    },
]

REPORTS = {
    "asg-1": {"overallStatus": "COMPLIANT"},
    "asg-2": {"overallStatus": "NEEDS_REVIEW"},
    "asg-3": {"overallStatus": "NON_COMPLIANT"},
}


class _FakeResult:
    def fetchall(self):
        return []


class _FakeConn:
    def execute(self, *args, **kwargs):
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeEngine:
    def connect(self):
        return _FakeConn()


class RecordingHrAssignmentsDb:
    """Stub db whose every public method records its name."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.engine = _FakeEngine()

    def _rec(self, name: str) -> None:
        self.calls.append(name)

    def get_hr_company_id(self, hr_user_id):
        self._rec("get_hr_company_id")
        return COMPANY_ID

    def get_profile_record(self, user_id):
        self._rec("get_profile_record")
        return {"id": user_id, "company_id": COMPANY_ID}

    def list_assignments_for_company_paginated(
        self,
        company_id,
        limit=25,
        offset=0,
        search=None,
        status=None,
        destination=None,
        request_id=None,
    ):
        self._rec("list_assignments_for_company_paginated")
        return [dict(a) for a in ASSIGNMENTS], len(ASSIGNMENTS)

    def next_open_milestone_deadlines_for_cases(self, relocation_case_ids, request_id=None):
        self._rec("next_open_milestone_deadlines_for_cases")
        return {}

    def get_latest_compliance_report(self, assignment_id):
        self._rec("get_latest_compliance_report")
        return dict(REPORTS.get(str(assignment_id) or "", {}) or {}) or None

    def get_latest_compliance_reports_by_assignment_ids(self, assignment_ids):
        self._rec("get_latest_compliance_reports_by_assignment_ids")
        wanted = {str(a) for a in (assignment_ids or []) if a}
        return {aid: dict(REPORTS[aid]) for aid in wanted if aid in REPORTS}


def _client_with_recording_db(monkeypatch):
    rec = RecordingHrAssignmentsDb()
    monkeypatch.setattr(database_mod, "db", rec)
    monkeypatch.setattr(bm, "db", rec)
    app.dependency_overrides[get_current_user] = lambda: dict(HR)
    client = TestClient(app)
    return rec, client


def test_hr_assignments_list_query_count_with_three_assignments(monkeypatch):
    rec, client = _client_with_recording_db(monkeypatch)
    try:
        response = client.get("/api/hr/assignments", params={"limit": 25, "offset": 0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["assignments"]) == 3
    assert body["total"] == 3

    # Before this task: 3 db-method calls (company, page, deadlines). Compliance
    # was omitted (partial fix). After: one bulk latest-report SELECT.
    assert rec.calls.count("get_latest_compliance_report") == 0, rec.calls
    assert rec.calls.count("get_latest_compliance_reports_by_assignment_ids") == 1, rec.calls
    assert rec.calls.count("list_assignments_for_company_paginated") == 1, rec.calls
    assert rec.calls.count("next_open_milestone_deadlines_for_cases") == 1, rec.calls
    assert rec.calls.count("get_hr_company_id") == 1, rec.calls
    assert len(rec.calls) == 4, rec.calls

    by_id = {row["id"]: row["complianceStatus"] for row in body["assignments"]}
    assert by_id == {
        "asg-1": "COMPLIANT",
        "asg-2": "NEEDS_REVIEW",
        "asg-3": "NON_COMPLIANT",
    }

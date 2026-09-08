"""WS2 Task 2.1 — query-count characterisation for GET /api/employee/policy/caps.

Handler (backend/main.py get_employee_policy_caps) db. calls on the published-policy
happy path, with three company-id candidates (case / HR owner / employee profile)
and a resolved-assignment-policy cache hit:

1. get_assignment_for_employee
2. get_assignment_by_id          (_require_assignment_visibility)
3. get_relocation_case
4. get_hr_company_id
5. get_profile_record
6. get_employee_profile
7. get_company_policy_with_published_version  × N candidates
   (find_first_published_company_policy — the N+1 this test pins)
8. get_resolved_assignment_policy
9. get_policy_version            (evaluate_version_comparison_readiness)
10. list_policy_benefit_rules
11. list_hr_benefit_rule_overrides
12. list_policy_exclusions
13. get_company

Auth is overridden; the recorder wraps backend.database.db / backend.main.db.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient

import backend.database as database_mod
import backend.main as bm
from backend.main import app, get_current_user

EMPLOYEE = {
    "id": "emp-1",
    "email": "emp@example.test",
    "role": "EMPLOYEE",
    "is_admin": False,
}

ASSIGNMENT = {
    "id": "asg-1",
    "case_id": "case-1",
    "employee_user_id": "emp-1",
    "hr_user_id": "hr-1",
}

POLICY = {"id": "pol-1", "title": "Acme mobility", "effective_date": "2026-01-01"}
VERSION = {"id": "ver-1", "status": "published", "version_number": 1}

# Three distinct candidates so the per-company loop is visible.
CASE_COMPANY = "co-case"  # miss
HR_COMPANY = "co-hr"  # miss
PROFILE_COMPANY = "co-profile"  # hit


class RecordingPolicyCapsDb:
    """Stub db whose every public method records its name."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _rec(self, name: str) -> None:
        self.calls.append(name)

    def get_assignment_for_employee(self, employee_user_id, request_id=None):
        self._rec("get_assignment_for_employee")
        return dict(ASSIGNMENT)

    def get_assignment_by_id(self, assignment_id):
        self._rec("get_assignment_by_id")
        if str(assignment_id) == ASSIGNMENT["id"]:
            return dict(ASSIGNMENT)
        return None

    def get_assignment_by_case_id(self, case_id):
        self._rec("get_assignment_by_case_id")
        return None

    def get_relocation_case(self, case_id):
        self._rec("get_relocation_case")
        return {
            "id": case_id,
            "company_id": CASE_COMPANY,
            "hr_user_id": "hr-1",
            "profile_json": {},
        }

    def get_hr_company_id(self, hr_user_id):
        self._rec("get_hr_company_id")
        return HR_COMPANY

    def get_profile_record(self, user_id):
        self._rec("get_profile_record")
        return {"id": user_id, "company_id": PROFILE_COMPANY, "email": "emp@example.test", "role": "EMPLOYEE"}

    def get_employee_profile(self, assignment_id):
        self._rec("get_employee_profile")
        return {}

    def get_company_policy_with_published_version(self, company_id):
        self._rec("get_company_policy_with_published_version")
        if str(company_id) == PROFILE_COMPANY:
            return (dict(POLICY), dict(VERSION))
        return None

    def get_company_policy_with_published_version_bulk(self, company_ids):
        self._rec("get_company_policy_with_published_version_bulk")
        out = {}
        for cid in company_ids or []:
            if str(cid) == PROFILE_COMPANY:
                out[str(cid)] = (dict(POLICY), dict(VERSION))
        return out

    def get_latest_published_policy_config_version(self, company_id, config_key):
        self._rec("get_latest_published_policy_config_version")
        return None

    def get_latest_published_policy_config_version_bulk(self, company_ids, config_key):
        self._rec("get_latest_published_policy_config_version_bulk")
        return {}

    def get_resolved_assignment_policy(self, assignment_id):
        self._rec("get_resolved_assignment_policy")
        return {
            "id": "rap-1",
            "policy_version_id": VERSION["id"],
            "policy": dict(POLICY),
            "version": dict(VERSION),
            "resolution_context": {},
            "resolution_company_id": PROFILE_COMPANY,
            "resolved_at": "2026-01-01T00:00:00Z",
        }

    def get_policy_version(self, version_id):
        self._rec("get_policy_version")
        return dict(VERSION)

    def list_policy_benefit_rules(self, policy_version_id):
        self._rec("list_policy_benefit_rules")
        return []

    def list_hr_benefit_rule_overrides(self, policy_version_id):
        self._rec("list_hr_benefit_rule_overrides")
        return []

    def list_policy_exclusions(self, policy_version_id):
        self._rec("list_policy_exclusions")
        return []

    def list_resolved_policy_benefits(self, resolved_id):
        self._rec("list_resolved_policy_benefits")
        return []

    def list_resolved_policy_exclusions(self, resolved_id):
        self._rec("list_resolved_policy_exclusions")
        return []

    def get_company(self, company_id):
        self._rec("get_company")
        return {"id": company_id, "name": "Acme"}

    def list_company_ids_with_published_policy(self):
        self._rec("list_company_ids_with_published_policy")
        return []


def _client_with_recording_db(monkeypatch):
    rec = RecordingPolicyCapsDb()
    monkeypatch.setattr(database_mod, "db", rec)
    monkeypatch.setattr(bm, "db", rec)
    app.dependency_overrides[get_current_user] = lambda: dict(EMPLOYEE)
    client = TestClient(app)
    return rec, client


def test_policy_caps_query_count_on_published_policy_cache_hit(monkeypatch):
    rec, client = _client_with_recording_db(monkeypatch)
    try:
        response = client.get("/api/employee/policy/caps")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_policy"] is True

    # Before: 15 calls (3× get_company_policy_with_published_version, no bulk).
    # After: 13 calls (1× get_company_policy_with_published_version_bulk).
    assert rec.calls.count("get_company_policy_with_published_version") == 0, rec.calls
    assert rec.calls.count("get_company_policy_with_published_version_bulk") == 1, rec.calls
    assert len(rec.calls) == 13, rec.calls

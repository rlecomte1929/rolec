"""WS2 Task 2.2 — query-count characterisation for employee assignment GETs.

Handlers (backend/main.py):
  GET /api/employee/assignments/current  → get_employee_assignment
  GET /api/employee/assignments/overview → get_employee_assignments_overview

Both run _best_effort_reconcile_employee_assignments then a small read set.
Reconcile used to N+1: list_unassigned / (optional) list_pending_claim per
contact, then get_assignment_by_id + is_assignment_auto_claim_blocked per
assignment. This fixture uses 3 contacts × 2 unassigned assignments (revoked
invites, so attach is skipped) so the loop is visible.

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
    "username": None,
    "role": "EMPLOYEE",
    "is_admin": False,
}

CONTACT_IDS = ["ec-1", "ec-2", "ec-3"]
# Two unassigned assignments per contact (6 total) — the N in the N+1.
ASSIGNMENTS = [
    {"id": f"asg-{c[-1]}{n}", "employee_contact_id": c, "employee_identifier": "emp@example.test", "employee_user_id": None, "status": "assigned"}
    for c in CONTACT_IDS
    for n in (1, 2)
]


class RecordingAssignmentDb:
    """Stub db whose every public method records its name."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _rec(self, name: str) -> None:
        self.calls.append(name)

    def is_auth_email_confirmed(self, email):
        self._rec("is_auth_email_confirmed")
        return False

    def list_employee_contacts_matching_signup_email(self, ident, request_id=None):
        self._rec("list_employee_contacts_matching_signup_email")
        return [{"id": cid, "linked_auth_user_id": EMPLOYEE["id"]} for cid in CONTACT_IDS]

    def list_employee_contacts_by_invite_key(self, ident, request_id=None):
        self._rec("list_employee_contacts_by_invite_key")
        return []

    def link_employee_contact_to_auth_user(self, cid, uid, request_id=None):
        self._rec("link_employee_contact_to_auth_user")

    def list_unassigned_assignments_for_employee_contact(self, cid, request_id=None):
        self._rec("list_unassigned_assignments_for_employee_contact")
        return [dict(a) for a in ASSIGNMENTS if a["employee_contact_id"] == cid]

    def list_unassigned_assignments_for_employee_contacts(self, cids, request_id=None):
        self._rec("list_unassigned_assignments_for_employee_contacts")
        wanted = {str(c) for c in (cids or [])}
        return [dict(a) for a in ASSIGNMENTS if a["employee_contact_id"] in wanted]

    def list_pending_claim_assignments_for_employee_contact(self, cid, request_id=None):
        self._rec("list_pending_claim_assignments_for_employee_contact")
        return []

    def list_pending_claim_assignments_for_employee_contacts(self, cids, request_id=None):
        self._rec("list_pending_claim_assignments_for_employee_contacts")
        return []

    def list_unassigned_assignments_legacy_for_identifiers(self, idents, request_id=None):
        self._rec("list_unassigned_assignments_legacy_for_identifiers")
        return []

    def get_assignment_by_id(self, assignment_id, request_id=None, include_archived=False):
        self._rec("get_assignment_by_id")
        for a in ASSIGNMENTS:
            if a["id"] == str(assignment_id):
                return dict(a)
        return None

    def get_assignments_by_ids(self, assignment_ids, request_id=None, include_archived=False):
        self._rec("get_assignments_by_ids")
        wanted = {str(a) for a in (assignment_ids or [])}
        return {a["id"]: dict(a) for a in ASSIGNMENTS if a["id"] in wanted}

    def is_assignment_auto_claim_blocked_by_revoked_invites(self, aid):
        self._rec("is_assignment_auto_claim_blocked_by_revoked_invites")
        return True

    def map_claim_invite_statuses_by_assignments(self, assignment_ids, request_id=None):
        self._rec("map_claim_invite_statuses_by_assignments")
        return {str(aid): ["revoked"] for aid in (assignment_ids or []) if aid}

    def list_linked_assignments_for_employee(self, employee_user_id, request_id=None):
        self._rec("list_linked_assignments_for_employee")
        return [
            {
                "id": "asg-linked",
                "case_id": "case-1",
                "employee_user_id": employee_user_id,
                "status": "assigned",
            }
        ]

    def list_pending_claim_assignments_for_auth_user(self, auth_user_id, request_id=None):
        self._rec("list_pending_claim_assignments_for_auth_user")
        return []

    def list_employee_linked_assignment_overview(self, employee_user_id, request_id=None):
        self._rec("list_employee_linked_assignment_overview")
        return [
            {
                "assignment_id": "asg-linked",
                "case_id": "case-1",
                "company_id": "co-1",
                "company_name": "Acme",
                "host_country": "DE",
                "home_country": "NO",
                "assignment_status": "assigned",
            }
        ]

    def list_employee_pending_assignment_overview(self, auth_user_id, request_id=None):
        self._rec("list_employee_pending_assignment_overview")
        return []


def _client_with_recording_db(monkeypatch):
    rec = RecordingAssignmentDb()
    monkeypatch.setattr(database_mod, "db", rec)
    monkeypatch.setattr(bm, "db", rec)
    app.dependency_overrides[get_current_user] = lambda: dict(EMPLOYEE)
    client = TestClient(app)
    return rec, client


def test_assignments_current_query_count_with_three_contacts(monkeypatch):
    rec, client = _client_with_recording_db(monkeypatch)
    try:
        response = client.get("/api/employee/assignments/current")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignment"]["id"] == "asg-linked"

    # Before: 24 calls (list_unassigned × 3, get_assignment_by_id × 6,
    # is_assignment_auto_claim_blocked × 6). After: bulk list + get_assignments_by_ids
    # + map_claim_invite_statuses_by_assignments, total 12.
    assert rec.calls.count("list_unassigned_assignments_for_employee_contact") == 0, rec.calls
    assert rec.calls.count("list_unassigned_assignments_for_employee_contacts") == 1, rec.calls
    assert rec.calls.count("get_assignment_by_id") == 0, rec.calls
    assert rec.calls.count("get_assignments_by_ids") == 1, rec.calls
    assert rec.calls.count("is_assignment_auto_claim_blocked_by_revoked_invites") == 0, rec.calls
    assert rec.calls.count("map_claim_invite_statuses_by_assignments") == 1, rec.calls
    assert rec.calls.count("link_employee_contact_to_auth_user") == 3, rec.calls
    assert len(rec.calls) == 12, rec.calls


def test_assignments_overview_query_count_with_three_contacts(monkeypatch):
    rec, client = _client_with_recording_db(monkeypatch)
    try:
        response = client.get("/api/employee/assignments/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["linked"]) == 1

    # Same reconcile as /current (10) plus overview reads: linked, pending,
    # map_claim (empty pending ids). Before: 25. After: 13.
    assert rec.calls.count("list_unassigned_assignments_for_employee_contact") == 0, rec.calls
    assert rec.calls.count("list_unassigned_assignments_for_employee_contacts") == 1, rec.calls
    assert rec.calls.count("get_assignment_by_id") == 0, rec.calls
    assert rec.calls.count("get_assignments_by_ids") == 1, rec.calls
    assert rec.calls.count("list_employee_linked_assignment_overview") == 1, rec.calls
    assert rec.calls.count("list_employee_pending_assignment_overview") == 1, rec.calls
    assert rec.calls.count("map_claim_invite_statuses_by_assignments") == 2, rec.calls
    assert len(rec.calls) == 13, rec.calls

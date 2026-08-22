"""[AIQ-2088] HR case closure, mounted on the prod app (backend.main:app).

Mounting the PROD app is deliberate: it proves the dual registration CLAUDE.md
requires. A router registered only in backend/app/main.py 405s in production —
that is the AI-002 v2 incident, and it has happened three times.

THE DEFECT THESE PIN
--------------------
`AssignmentStatus.CLOSED` was a legal status the DB constraint has always allowed,
and nothing an HR user could reach had ever written it. Production 2026-08-22:
1,418 assignments — 838 submitted, 523 assigned, 55 awaiting_intake, 2 approved,
**0 closed, 0 rejected**. HR could start a relocation and never finish one.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import hr_case_closure

_HR = {"id": "hr-1", "role": "HR", "company": "co-1", "is_admin": False, "auth_uuid": None}


class _Recorder:
    """Captures the writes so the tests assert on behaviour, not on a mock's shape."""

    def __init__(self, status="submitted", company_id="co-1"):
        self.assignment = {"id": "asg-1", "case_id": "case-1", "status": status}
        self.case = {"id": "case-1", "company_id": company_id}
        self.status_writes = []
        self.events = []

    def get_assignment_by_id(self, aid):
        return dict(self.assignment) if aid == "asg-1" else None

    def get_relocation_case(self, cid):
        return dict(self.case) if cid == "case-1" else None

    def update_assignment_status(self, aid, status, request_id=None):
        self.status_writes.append((aid, status))
        self.assignment["status"] = status

    def insert_case_event(self, **kw):
        self.events.append(kw)


@pytest.fixture()
def rec(monkeypatch):
    r = _Recorder()
    monkeypatch.setattr(hr_case_closure.db, "get_assignment_by_id", r.get_assignment_by_id)
    monkeypatch.setattr(hr_case_closure.db, "get_relocation_case", r.get_relocation_case)
    monkeypatch.setattr(hr_case_closure.db, "update_assignment_status", r.update_assignment_status)
    monkeypatch.setattr(hr_case_closure.db, "insert_case_event", r.insert_case_event)
    # The outstanding probe is advisory and hits raw SQL; pin it so these tests are
    # about closure, not about the warning query.
    monkeypatch.setattr(hr_case_closure, "_outstanding_for_case",
                        lambda case_id: hr_case_closure.Outstanding(open_rfqs=2, incomplete_milestones=3))
    return r


@pytest.fixture()
def client(rec):
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _HR
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: "co-1"
    yield TestClient(app)
    app.dependency_overrides.pop(auth_deps.get_current_user, None)
    app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_routes_registered_in_prod_app():
    """Dual registration. Without this the feature 405s in production."""
    paths = {r.path for r in app.routes}
    assert "/api/hr/assignments/{assignment_id}/close" in paths
    assert "/api/hr/assignments/{assignment_id}/closure-readiness" in paths


def test_hr_can_close_a_case(client, rec):
    r = client.post("/api/hr/assignments/asg-1/close", json={"reason": "Employee arrived."})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "closed" and body["already_closed"] is False
    assert rec.status_writes == [("asg-1", "closed")]


def test_close_is_allowed_from_a_non_approved_state(client, rec):
    """Requiring `approved` first would make closure unreachable for 99.8% of cases
    (2 of 1,418), and an abandoned move never reaches approval at all."""
    assert rec.assignment["status"] == "submitted"
    assert client.post("/api/hr/assignments/asg-1/close", json={}).status_code == 200
    assert rec.status_writes == [("asg-1", "closed")]


def test_close_writes_one_audit_event_with_the_outstanding_snapshot(client, rec):
    client.post("/api/hr/assignments/asg-1/close", json={"reason": "Move complete"})
    assert len(rec.events) == 1
    ev = rec.events[0]
    assert ev["event_type"] == "assignment.closed"
    assert ev["payload"]["reason"] == "Move complete"
    assert ev["payload"]["previous_status"] == "submitted"
    # Warn-don't-block: what was still open must be recorded, or "why was this closed
    # with 3 open steps?" is unanswerable later.
    assert ev["payload"]["outstanding"] == {"open_rfqs": 2, "incomplete_milestones": 3}


def test_close_is_idempotent_and_does_not_double_audit(client, rec):
    client.post("/api/hr/assignments/asg-1/close", json={})
    second = client.post("/api/hr/assignments/asg-1/close", json={})
    assert second.status_code == 200
    assert second.json()["already_closed"] is True
    assert len(rec.status_writes) == 1, "a second close must not re-write the status"
    assert len(rec.events) == 1, "a second close must not add a closure that never happened"


def test_another_tenants_case_cannot_be_closed(rec, monkeypatch):
    """NEGATIVE test, and it must 404 rather than 403 — a different status code lets an
    attacker probe which assignment ids belong to other tenants."""
    rec.case["company_id"] = "some-other-co"
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _HR
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: "co-1"
    try:
        c = TestClient(app)
        assert c.post("/api/hr/assignments/asg-1/close", json={}).status_code == 404
        assert c.get("/api/hr/assignments/asg-1/closure-readiness").status_code == 404
        assert rec.status_writes == [], "a cross-tenant close must write nothing"
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)
        app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_unknown_assignment_is_404(client, rec):
    assert client.post("/api/hr/assignments/nope/close", json={}).status_code == 404


def test_readiness_reports_status_and_outstanding(client, rec):
    r = client.get("/api/hr/assignments/asg-1/closure-readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["already_closed"] is False and body["status"] == "submitted"
    assert body["outstanding"] == {"open_rfqs": 2, "incomplete_milestones": 3}


def test_outstanding_probe_degrades_to_zeros_rather_than_raising(monkeypatch):
    """The warning is advisory, so a failing probe must never stop HR closing a case.

    Tests the real function against a broken engine — an earlier draft of this test
    monkeypatched the raiser and then immediately replaced it, so it asserted nothing.
    """
    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(hr_case_closure.db, "engine", _BrokenEngine())
    assert hr_case_closure._outstanding_for_case("case-1") == hr_case_closure.Outstanding()


def test_close_still_succeeds_when_the_probe_returns_nothing(client, rec, monkeypatch):
    monkeypatch.setattr(hr_case_closure, "_outstanding_for_case",
                        lambda cid: hr_case_closure.Outstanding())
    r = client.post("/api/hr/assignments/asg-1/close", json={})
    assert r.status_code == 200
    assert rec.events[0]["payload"]["outstanding"] == {"open_rfqs": 0, "incomplete_milestones": 0}

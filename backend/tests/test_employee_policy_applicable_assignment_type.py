"""AIQ-1349: GET /api/employee/policy/applicable must use the case's real
assignment_type, mapped to the display vocabulary published policies store
("Short-Term"/"Long-Term"/"Permanent"), instead of the old hardcoded "Long-Term".
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient

import backend.main as bm
from backend.main import app, get_current_user


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1", "email": "e@x.com", "role": "EMPLOYEE", "is_admin": False,
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def _wire(monkeypatch, case_assignment_type):
    """Stub the db calls the handler makes; capture the assignment_type passed
    into the policy lookup. Patches `backend.main.db` — the exact object the
    handler dereferences — so this stays correct under full-suite discovery
    (where the `backend.database.db` reference can differ)."""
    captured = {}
    monkeypatch.setattr(
        bm.db, "get_assignment_by_id",
        lambda aid: {"id": aid, "employee_user_id": "u1", "case_id": "case-1"},
    )
    monkeypatch.setattr(
        bm.db, "get_employee_profile",
        lambda aid: {"movePlan": {"destination": "Singapore"},
                     "primaryApplicant": {"employer": {"jobLevel": "Band2"}}},
    )
    monkeypatch.setattr(
        bm.db, "get_relocation_case",
        lambda cid: {"id": cid, "assignment_type": case_assignment_type},
    )

    def fake_policy(**kwargs):
        captured["assignment_type"] = kwargs.get("assignment_type")
        return None  # early return — we only assert the value threaded in

    monkeypatch.setattr(bm.db, "get_published_hr_policy_for_employee", fake_policy)
    return captured


def test_sta_case_maps_to_short_term(client, monkeypatch):
    captured = _wire(monkeypatch, "STA")
    r = client.get("/api/employee/policy/applicable?assignmentId=a1")
    assert r.status_code == 200, r.text
    assert captured["assignment_type"] == "Short-Term"


def test_lta_case_maps_to_long_term(client, monkeypatch):
    captured = _wire(monkeypatch, "LTA")
    r = client.get("/api/employee/policy/applicable?assignmentId=a1")
    assert r.status_code == 200, r.text
    assert captured["assignment_type"] == "Long-Term"


def test_permanent_case_maps_to_permanent(client, monkeypatch):
    captured = _wire(monkeypatch, "PERMANENT")
    r = client.get("/api/employee/policy/applicable?assignmentId=a1")
    assert r.status_code == 200, r.text
    assert captured["assignment_type"] == "Permanent"


def test_null_type_falls_back_to_long_term(client, monkeypatch):
    captured = _wire(monkeypatch, None)
    r = client.get("/api/employee/policy/applicable?assignmentId=a1")
    assert r.status_code == 200, r.text
    assert captured["assignment_type"] == "Long-Term"

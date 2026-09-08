"""AIQ-1552: GET /api/employee/cases/{id}/intake-nationality.

Nationality pre-fill for the Relocation Assistant, sourced from intake and
scoped by require_case_access — NOT behind the immigration-consent gate.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user
from backend.app.routers import immigration_intake_profile as mod

_EMP = {"id": "emp-1", "role": "EMPLOYEE"}
_PATH = "/api/employee/cases/case-1/intake-nationality"


@pytest.fixture()
def client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: _EMP
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_own_case_returns_intake_nationality(client, monkeypatch):
    # real extract_profile_from_wizard_draft runs over a realistic wizard draft
    monkeypatch.setattr(mod, "require_case_access", lambda case_id, user: {"id": "a1"})
    monkeypatch.setattr(
        mod, "load_profile_draft_for_case",
        lambda session, case_id: {"employeeProfile": {"nationality": "DE"}},
    )
    r = client.get(_PATH)
    assert r.status_code == 200
    assert r.json() == {"nationality": "DE", "second_nationality": None}


def test_no_draft_returns_nulls_not_error(client, monkeypatch):
    monkeypatch.setattr(mod, "require_case_access", lambda case_id, user: {})
    monkeypatch.setattr(mod, "load_profile_draft_for_case", lambda session, case_id: {})
    r = client.get(_PATH)
    assert r.status_code == 200
    assert r.json() == {"nationality": None, "second_nationality": None}


def test_cross_employee_is_403(client, monkeypatch):
    def deny(case_id, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")

    monkeypatch.setattr(mod, "require_case_access", deny)
    # ownership is checked BEFORE reading the draft — a leak here would be a bug
    monkeypatch.setattr(
        mod, "load_profile_draft_for_case",
        lambda session, case_id: (_ for _ in ()).throw(AssertionError("must not read draft when denied")),
    )
    r = client.get(_PATH)
    assert r.status_code == 403

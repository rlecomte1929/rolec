"""AIQ-2285 — wrong-role hits on employee overview are 403, never 401."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient

from backend.main import app, get_current_user
import backend.main as bm


def _override(user: dict) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_hr_only_overview_is_403_not_401(monkeypatch):
    _override({
        "id": "hr-1",
        "email": "hr@example.test",
        "role": "HR",
        "roles": ["HR"],
        "is_admin": False,
    })
    monkeypatch.setattr(bm, "_best_effort_reconcile_employee_assignments", lambda **kw: None)
    client = TestClient(app)
    response = client.get("/api/employee/assignments/overview")
    assert response.status_code == 403
    assert isinstance(response.json()["detail"], str)


def test_admin_overview_is_not_rejected_as_expiry(monkeypatch):
    _override({
        "id": "adm-1",
        "email": "admin@relopass.com",
        "role": "ADMIN",
        "roles": ["ADMIN", "EMPLOYEE"],
        "is_admin": True,
    })
    monkeypatch.setattr(bm, "_best_effort_reconcile_employee_assignments", lambda **kw: None)
    monkeypatch.setattr(
        bm,
        "build_employee_assignment_overview",
        lambda *args, **kwargs: {"linked": [], "pending": []},
    )
    client = TestClient(app)
    response = client.get("/api/employee/assignments/overview")
    assert response.status_code == 200


def test_hr_primary_with_employee_junction_is_allowed(monkeypatch):
    """AIQ-2285 root cause, pinned.

    hr@testingapril.com in production is users.role='HR' with an EMPLOYEE row in
    public.user_roles. Before the membership fix, main.py's require_role compared
    users.role only and returned 403 here, which the client could not tell apart
    from a transport failure. This is the one shape that discriminates the fix:
    it returns 403 on origin/main and 200 now.
    """
    _override({
        "id": "hr-emp-1",
        "email": "hr@testingapril.com",
        "role": "HR",
        "roles": ["HR", "EMPLOYEE"],
        "is_admin": False,
    })
    monkeypatch.setattr(bm, "_best_effort_reconcile_employee_assignments", lambda **kw: None)
    monkeypatch.setattr(
        bm,
        "build_employee_assignment_overview",
        lambda *args, **kwargs: {"linked": [], "pending": []},
    )
    client = TestClient(app)
    response = client.get("/api/employee/assignments/overview")
    assert response.status_code == 200

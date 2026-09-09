"""WS2 Task 2.6 — query-count characterisation for catalog notification-counts.

GET /api/hr/catalog/notification-counts and GET /api/admin/catalog/notification-counts
each used three COUNT/SUM round-trips on one connection. Identity lookups
(_caller_company_id_optional) are Task 2.7 and are not pinned here.

Auth is overridden on backend.app.auth_deps.get_current_user (the dependency
the modular routers actually use). The recorder wraps db.engine.connect().execute.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient

import backend.app.auth_deps as auth_deps
import backend.app.routers.admin_catalog as admin_catalog_mod
import backend.app.routers.hr_catalog as hr_catalog_mod
import backend.database as database_mod
from backend.main import app

HR = {
    "id": "hr-1",
    "email": "hr@example.test",
    "role": "HR",
    "is_admin": False,
}

ADMIN = {
    "id": "admin-1",
    "email": "admin@example.test",
    "role": "ADMIN",
    "is_admin": True,
}

COMPANY_ID = "co-1"


class _Result:
    def __init__(self, row=None, scalar=0):
        self._row = row or {}
        self._scalar = scalar

    def mappings(self):
        return self

    def first(self):
        return self._row

    def scalar(self):
        return self._scalar


class _RecordingConn:
    def __init__(self, rec: "RecordingCatalogDb"):
        self._rec = rec

    def execute(self, statement, *args, **kwargs):
        self._rec.sql_execute_calls += 1
        sql = str(statement).lower()
        if "as waiting" in sql and "as distinct_pairs" in sql:
            return _Result(row={"waiting": 4, "distinct_pairs": 2, "pending": 1})
        if "as pending_tickets" in sql:
            return _Result(
                row={
                    "pending_tickets": 3,
                    "allowlisted_destinations": 5,
                    "pending_capabilities": 7,
                }
            )
        if "sum(" in sql or "as waiting" in sql:
            return _Result(row={"waiting": 4}, scalar=4)
        if "distinct" in sql:
            return _Result(scalar=2)
        if "catalog_destination_allowlist" in sql:
            return _Result(scalar=5)
        if "supplier_service_capabilities" in sql:
            return _Result(scalar=7)
        if "catalog_destination_requests" in sql:
            # HR scopes by company_id; admin counts all pending tickets.
            return _Result(scalar=1 if "company_id" in sql else 3)
        return _Result(scalar=0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RecordingCatalogDb:
    """Stub db: company lookup + a recording SQL engine."""

    def __init__(self, company_id=COMPANY_ID):
        self.sql_execute_calls = 0
        self.company_id = company_id
        self.engine = self

    def connect(self):
        return _RecordingConn(self)

    def get_hr_company_id(self, hr_user_id):
        return self.company_id

    def get_profile_record(self, user_id):
        if not self.company_id:
            return {"id": user_id}
        return {"id": user_id, "company_id": self.company_id}


def _install(monkeypatch, rec, user):
    monkeypatch.setattr(database_mod, "db", rec)
    monkeypatch.setattr(hr_catalog_mod, "db", rec)
    monkeypatch.setattr(admin_catalog_mod, "db", rec)
    app.dependency_overrides[auth_deps.get_current_user] = lambda: dict(user)
    return TestClient(app)


def test_hr_notification_counts_sql_round_trips(monkeypatch):
    rec = RecordingCatalogDb()
    client = _install(monkeypatch, rec, HR)
    try:
        response = client.get("/api/hr/catalog/notification-counts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json() == {
        "employees_waiting": 4,
        "destinations_with_demand": 2,
        "pending_admin_tickets": 1,
    }
    # Before: 3 COUNT/SUM executes. After: one SELECT with subselect columns.
    assert rec.sql_execute_calls == 1, rec.sql_execute_calls


def test_hr_notification_counts_unlinked_user_skips_sql(monkeypatch):
    rec = RecordingCatalogDb(company_id=None)
    client = _install(monkeypatch, rec, HR)
    try:
        response = client.get("/api/hr/catalog/notification-counts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json() == {
        "employees_waiting": 0,
        "destinations_with_demand": 0,
        "pending_admin_tickets": 0,
    }
    assert rec.sql_execute_calls == 0


def test_admin_notification_counts_sql_round_trips(monkeypatch):
    rec = RecordingCatalogDb()
    client = _install(monkeypatch, rec, ADMIN)
    try:
        response = client.get("/api/admin/catalog/notification-counts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json() == {
        "pending_tickets": 3,
        "allowlisted_destinations": 5,
        "pending_capabilities": 7,
    }
    # Before: 3 COUNT executes. After: one SELECT with subselect columns.
    assert rec.sql_execute_calls == 1, rec.sql_execute_calls

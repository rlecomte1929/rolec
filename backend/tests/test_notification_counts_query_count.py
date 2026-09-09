"""WS2 Task 2.6 — query-count characterisation for catalog notification-counts.

HR handler (backend/app/routers/hr_catalog.py hr_notification_counts) used three
COUNT round-trips on one connection. Admin twin (admin_catalog.admin_notification_counts)
did the same. Both now issue a single SELECT with subselect columns.

Auth is not mounted: the recorder wraps db.engine.connect().execute on the handler
module, matching the recording-stub style of test_employee_policy_caps_query_count.py.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from backend.app.routers import admin_catalog as admin_router
from backend.app.routers import hr_catalog as hr_router
from backend import database as database_mod

HR = {
    "id": "hr-1",
    "email": "hr@example.test",
    "role": "HR",
    "is_admin": False,
    "company": "co-1",
}

ADMIN = {
    "id": "admin-1",
    "email": "admin@example.test",
    "role": "ADMIN",
    "is_admin": True,
}


class _FakeResult:
    def __init__(self, row: dict) -> None:
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row

    def scalar(self):
        if not self._row:
            return 0
        return next(iter(self._row.values()))


class _FakeConn:
    def __init__(self, rec: "RecordingCatalogDb") -> None:
        self._rec = rec

    def execute(self, *_args, **_kwargs):
        self._rec.calls.append("execute")
        return _FakeResult(dict(self._rec.row))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeEngine:
    def __init__(self, rec: "RecordingCatalogDb") -> None:
        self._rec = rec

    def connect(self):
        self._rec.calls.append("connect")
        return _FakeConn(self._rec)


class RecordingCatalogDb:
    """Stub db: identity lookups + a recording engine.execute."""

    def __init__(self, row: dict) -> None:
        self.calls: list[str] = []
        self.row = row
        self.engine = _FakeEngine(self)

    def get_hr_company_id(self, hr_user_id):
        self.calls.append("get_hr_company_id")
        return "co-1"

    def get_profile_record(self, user_id):
        self.calls.append("get_profile_record")
        return {"id": user_id, "company_id": "co-1"}


def _patch_catalog_db(monkeypatch, rec: RecordingCatalogDb) -> None:
    """The suite's backend/conftest.py may have swapped in a MagicMock
    ``backend.database``; patch both the imported name and sys.modules."""
    import sys

    monkeypatch.setattr(database_mod, "db", rec)
    loaded = sys.modules.get("backend.database")
    if loaded is not None:
        monkeypatch.setattr(loaded, "db", rec)
    monkeypatch.setattr(hr_router, "db", rec)


def test_hr_notification_counts_single_execute(monkeypatch):
    rec = RecordingCatalogDb(
        {"waiting": 4, "distinct_pairs": 2, "pending": 1}
    )
    _patch_catalog_db(monkeypatch, rec)

    result = hr_router.hr_notification_counts(dict(HR))

    assert result == {
        "employees_waiting": 4,
        "destinations_with_demand": 2,
        "pending_admin_tickets": 1,
    }
    # Before: 3 COUNT executes (SUM, DISTINCT, pending tickets). After: 1.
    assert rec.calls.count("connect") == 1, rec.calls
    assert rec.calls.count("execute") == 1, rec.calls
    assert rec.calls.count("get_hr_company_id") == 1, rec.calls
    assert rec.calls.count("get_profile_record") == 0, rec.calls


def test_admin_notification_counts_single_execute(monkeypatch):
    rec = RecordingCatalogDb(
        {
            "pending_tickets": 3,
            "allowlisted_destinations": 5,
            "pending_capabilities": 2,
        }
    )
    _patch_catalog_db(monkeypatch, rec)

    result = admin_router.admin_notification_counts(dict(ADMIN))

    assert result == {
        "pending_tickets": 3,
        "allowlisted_destinations": 5,
        "pending_capabilities": 2,
    }
    # Before: 3 COUNT executes (tickets, allowlist, capabilities). After: 1.
    assert rec.calls.count("connect") == 1, rec.calls
    assert rec.calls.count("execute") == 1, rec.calls

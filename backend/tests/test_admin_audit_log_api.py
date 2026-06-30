"""TDD tests for GET /api/admin/audit-log (Task 7 — A-05).

All tests use in-memory SQLite. No live Postgres required.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin_audit_log  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT
)
"""

_SEED = [
    ("log-001", "admin_allowlist", "eid-1", "update", None,
     json.dumps({"event": "admin_added", "email": "a@b.com"}), "human", "actor-1", "2026-06-01T10:00:00"),
    ("log-002", "admin_allowlist", "eid-2", "update", None,
     json.dumps({"event": "admin_disabled", "email": "b@b.com"}), "human", "actor-2", "2026-06-01T11:00:00"),
    ("log-003", "admin_allowlist", "eid-3", "update", None,
     json.dumps({"event": "admin_enabled", "email": "c@b.com"}), "human", "actor-1", "2026-06-02T09:00:00"),
]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        for row in _SEED:
            conn.execute(text(
                "INSERT INTO audit_logs (id, entity_type, entity_id, action_type, "
                "old_value_json, new_value_json, actor_type, actor_id, created_at) "
                "VALUES (:id, :et, :eid, :at, :ov, :nv, :act_t, :act_id, :ca)"
            ), {
                "id": row[0], "et": row[1], "eid": row[2], "at": row[3],
                "ov": row[4], "nv": row[5], "act_t": row[6], "act_id": row[7], "ca": row[8],
            })
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_client(db_session, *, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_audit_log.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin-1", "is_admin": is_admin}
    app.dependency_overrides[admin_audit_log._get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def admin_client(db_session):
    return _make_client(db_session, is_admin=True)


@pytest.fixture()
def non_admin_client(db_session):
    return _make_client(db_session, is_admin=False)


def test_get_returns_all_rows(admin_client):
    resp = admin_client.get("/api/admin/audit-log")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert len(body["items"]) == 3


def test_get_returns_desc_order(admin_client):
    resp = admin_client.get("/api/admin/audit-log")
    items = resp.json()["items"]
    dates = [i["created_at"] for i in items]
    assert dates == sorted(dates, reverse=True)


def test_get_since_filter(admin_client):
    resp = admin_client.get("/api/admin/audit-log?since=2026-06-02T00:00:00")
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "log-003"


def test_get_actor_filter(admin_client):
    resp = admin_client.get("/api/admin/audit-log?actor=actor-1")
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(i["actor_id"] == "actor-1" for i in items)


def test_get_event_filter(admin_client):
    resp = admin_client.get("/api/admin/audit-log?event=admin_added")
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "log-001"


def test_get_limit_offset(admin_client):
    resp = admin_client.get("/api/admin/audit-log?limit=2&offset=0")
    assert len(resp.json()["items"]) == 2
    resp2 = admin_client.get("/api/admin/audit-log?limit=2&offset=2")
    assert len(resp2.json()["items"]) == 1


def test_get_non_admin_403(non_admin_client):
    resp = non_admin_client.get("/api/admin/audit-log")
    assert resp.status_code == 403


def test_get_item_has_expected_fields(admin_client):
    item = admin_client.get("/api/admin/audit-log").json()["items"][0]
    for f in ("id", "entity_type", "entity_id", "action_type", "new_value", "actor_id", "created_at"):
        assert f in item, f"missing field: {f}"


def test_event_filter_against_real_record_admin_event(db_session):
    """Event filter must work against rows written by record_admin_event.

    This proves the filter is robust to JSON serialisation details (spacing, key
    ordering) by using the REAL writer rather than a hand-formatted seed string.
    """
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    unique_event = "task7_m1_real_write_probe"
    record_admin_event(
        db_session,
        actor_id="test-actor-id",
        event=unique_event,
        entity="admin_allowlist",
    )
    # No explicit flush needed: writes via db.connection() share the same SA transaction.

    app = FastAPI()
    app.include_router(admin_audit_log.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin-1", "is_admin": True}
    app.dependency_overrides[admin_audit_log._get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get(f"/api/admin/audit-log?event={unique_event}")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1, (
        "event filter returned 0 rows — JSON extraction broken or row not written; "
        f"all rows: {client.get('/api/admin/audit-log').json()['items']}"
    )
    assert any(
        (item.get("new_value") or {}).get("event") == unique_event
        for item in items
    ), f"Matched rows have wrong event field: {items}"

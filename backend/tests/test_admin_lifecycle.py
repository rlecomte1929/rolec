"""TDD tests for POST/PATCH /api/admin/admins (Task 7 — admin lifecycle).

All tests use an in-memory SQLite DB. No live Postgres required.
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

from backend.app.routers import admin_admins  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_allowlist (
  email TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 1,
  added_by_user_id TEXT,
  created_at TEXT NOT NULL
);
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

ACTOR_EMAIL = "actor@example.com"
ACTOR_ID = "actor-uuid-001"


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
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_client(db_session, *, is_admin: bool = True, email: str = ACTOR_EMAIL) -> TestClient:
    app = FastAPI()
    app.include_router(admin_admins.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": ACTOR_ID,
        "email": email,
        "is_admin": is_admin,
    }
    app.dependency_overrides[admin_admins._get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def admin_client(db_session):
    return _make_client(db_session, is_admin=True)


@pytest.fixture()
def non_admin_client(db_session):
    return _make_client(db_session, is_admin=False)


# ── GET /api/admin/admins ──────────────────────────────────────────────────────


def test_list_admins_empty(admin_client):
    resp = admin_client.get("/api/admin/admins")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_list_admins_non_admin_403(non_admin_client):
    resp = non_admin_client.get("/api/admin/admins")
    assert resp.status_code == 403


# ── POST /api/admin/admins ──────────────────────────────────────────────────────


def test_post_adds_allowlist_row(admin_client, db_session):
    resp = admin_client.post("/api/admin/admins", json={"email": "new@relopass.com"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@relopass.com"
    assert body["enabled"] is True

    row = db_session.execute(
        text("SELECT enabled FROM admin_allowlist WHERE email='new@relopass.com'")
    ).fetchone()
    assert row is not None
    assert row[0] == 1


def test_post_writes_audit_event(admin_client, db_session):
    admin_client.post("/api/admin/admins", json={"email": "audited@relopass.com"})
    rows = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchall()
    events = [json.loads(r[0])["event"] for r in rows if r[0]]
    assert "admin_added" in events


def test_post_non_admin_403(non_admin_client):
    resp = non_admin_client.post("/api/admin/admins", json={"email": "x@example.com"})
    assert resp.status_code == 403


# ── PATCH /api/admin/admins/{email} ─────────────────────────────────────────────


def test_patch_disable_makes_allowlist_return_false(admin_client, db_session):
    # Seed the target + a keeper admin (so disabling isn't blocked as the last admin)
    db_session.execute(text(
        "INSERT INTO admin_allowlist (email, enabled, created_at) VALUES "
        "('target@example.com', 1, '2026-01-01'), ('keeper@relopass.com', 1, '2026-01-01')"
    ))
    db_session.commit()

    resp = admin_client.patch("/api/admin/admins/target@example.com", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # is_admin_allowlisted should now return False (enabled=0)
    row = db_session.execute(
        text("SELECT enabled FROM admin_allowlist WHERE email='target@example.com'")
    ).fetchone()
    assert row[0] == 0


def test_patch_enable_makes_allowlist_return_true(admin_client, db_session):
    db_session.execute(text(
        "INSERT INTO admin_allowlist (email, enabled, created_at) VALUES ('disabled@example.com', 0, '2026-01-01')"
    ))
    db_session.commit()

    resp = admin_client.patch("/api/admin/admins/disabled@example.com", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True

    row = db_session.execute(
        text("SELECT enabled FROM admin_allowlist WHERE email='disabled@example.com'")
    ).fetchone()
    assert row[0] == 1


def test_patch_disable_writes_audit_event(admin_client, db_session):
    db_session.execute(text(
        "INSERT INTO admin_allowlist (email, enabled, created_at) VALUES "
        "('audit2@example.com', 1, '2026-01-01'), ('keeper@relopass.com', 1, '2026-01-01')"
    ))
    db_session.commit()

    admin_client.patch("/api/admin/admins/audit2@example.com", json={"enabled": False})
    rows = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchall()
    events = [json.loads(r[0])["event"] for r in rows if r[0]]
    assert "admin_disabled" in events


def test_patch_enable_writes_audit_event(admin_client, db_session):
    db_session.execute(text(
        "INSERT INTO admin_allowlist (email, enabled, created_at) VALUES ('audit3@example.com', 0, '2026-01-01')"
    ))
    db_session.commit()

    admin_client.patch("/api/admin/admins/audit3@example.com", json={"enabled": True})
    rows = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchall()
    events = [json.loads(r[0])["event"] for r in rows if r[0]]
    assert "admin_enabled" in events


def test_patch_self_disable_returns_400(db_session):
    """An admin cannot disable their own account."""
    db_session.execute(text(
        f"INSERT INTO admin_allowlist (email, enabled, created_at) VALUES ('{ACTOR_EMAIL}', 1, '2026-01-01')"
    ))
    db_session.commit()

    client = _make_client(db_session, is_admin=True, email=ACTOR_EMAIL)
    resp = client.patch(f"/api/admin/admins/{ACTOR_EMAIL}", json={"enabled": False})
    assert resp.status_code == 400


def test_patch_non_admin_403(non_admin_client, db_session):
    db_session.execute(text(
        "INSERT INTO admin_allowlist (email, enabled, created_at) VALUES ('x@example.com', 1, '2026-01-01')"
    ))
    db_session.commit()
    resp = non_admin_client.patch("/api/admin/admins/x@example.com", json={"enabled": False})
    assert resp.status_code == 403


def test_patch_missing_admin_404(admin_client):
    resp = admin_client.patch("/api/admin/admins/nobody@example.com", json={"enabled": False})
    assert resp.status_code == 404


def test_patch_disable_no_email_in_user_dict_fails_closed(db_session):
    """Disable request where user dict has no 'email' must be blocked (400 fail-closed).

    The actor_id is an opaque non-email string and no 'users' table exists in this
    SQLite fixture, so identity cannot be resolved.  The guard must reject rather
    than silently allow the disable (which would bypass the self-disable check).
    """
    db_session.execute(text(
        "INSERT INTO admin_allowlist (email, enabled, created_at) "
        "VALUES ('target@example.com', 1, '2026-01-01'), ('keeper@relopass.com', 1, '2026-01-01')"
    ))
    db_session.commit()

    app = FastAPI()
    app.include_router(admin_admins.router)
    # Actor has no 'email' in user dict; actor_id is not an email → identity ambiguous
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "opaque-actor-id-without-email",
        "is_admin": True,
    }
    app.dependency_overrides[admin_admins._get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.patch("/api/admin/admins/target@example.com", json={"enabled": False})
    assert resp.status_code == 400, f"Expected 400 (fail-closed), got {resp.status_code}: {resp.text}"
    assert "identity" in resp.json()["detail"].lower()


def test_patch_disable_actor_id_is_email_resolves_and_self_checks(db_session):
    """If actor_id is itself an email (legacy), resolve it and apply the self-disable guard."""
    actor_as_email = "self@example.com"
    db_session.execute(text(
        f"INSERT INTO admin_allowlist (email, enabled, created_at) VALUES ('{actor_as_email}', 1, '2026-01-01')"
    ))
    db_session.commit()

    app = FastAPI()
    app.include_router(admin_admins.router)
    # No 'email' in dict, but id IS an email
    app.dependency_overrides[get_current_user] = lambda: {
        "id": actor_as_email,
        "is_admin": True,
    }
    app.dependency_overrides[admin_admins._get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.patch(f"/api/admin/admins/{actor_as_email}", json={"enabled": False})
    assert resp.status_code == 400, "Self-disable via legacy email actor_id must be rejected"

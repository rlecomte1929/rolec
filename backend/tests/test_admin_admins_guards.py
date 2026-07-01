"""
Admin-allowlist safety guards (ported from #1236 into #1227's admin_admins.py):
new entries must be @relopass.com, and you cannot disable the LAST enabled admin
(lockout protection). The self-removal guard already existed.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.routers import admin_admins
from backend.app.auth_deps import require_admin

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_allowlist (
  email TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 1,
  added_by_user_id TEXT,
  created_at TEXT
)
"""


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _client(db_session, *, actor_email: str = "boss@relopass.com") -> TestClient:
    app = FastAPI()
    app.include_router(admin_admins.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "u-1", "email": actor_email, "is_admin": True}
    app.dependency_overrides[admin_admins._get_db] = lambda: db_session
    return TestClient(app)


def _seed(db_session, *emails: str) -> None:
    for e in emails:
        db_session.execute(
            text("INSERT INTO admin_allowlist (email, enabled, created_at) VALUES (:e, 1, '2026-07-01')"),
            {"e": e},
        )
    db_session.commit()


def test_add_requires_relopass_domain(db_session):
    c = _client(db_session)
    assert c.post("/api/admin/admins", json={"email": "attacker@gmail.com"}).status_code == 422
    assert c.post("/api/admin/admins", json={"email": "new.admin@relopass.com"}).status_code == 201


def test_cannot_disable_the_last_admin(db_session):
    _seed(db_session, "solo@relopass.com")
    c = _client(db_session, actor_email="other@relopass.com")  # not self, so self-guard won't fire first
    r = c.patch("/api/admin/admins/solo@relopass.com", json={"enabled": False})
    assert r.status_code == 400
    assert "last admin" in r.json()["detail"].lower()


def test_can_disable_when_more_than_one_admin(db_session):
    _seed(db_session, "a@relopass.com", "b@relopass.com")
    c = _client(db_session, actor_email="other@relopass.com")
    r = c.patch("/api/admin/admins/a@relopass.com", json={"enabled": False})
    assert r.status_code == 200

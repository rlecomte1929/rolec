"""WS-E — tests for the end-user helpfulness endpoint + dual-router registration.

Mirrors test_ai_feedback_router.py: a minimal FastAPI app mounts only the
policy_helpfulness router, get_current_user is overridden to a fixed end user, and
the service's SessionLocal is patched to an in-memory SQLite DB seeded with a trace
so company_id is derived from it.
"""
from __future__ import annotations

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

from backend.app.routers import policy_helpfulness  # noqa: E402
from backend.app.services import policy_helpfulness_service  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402


_SCHEMA = [
    """
    CREATE TABLE policy_assistant_traces (
      id TEXT PRIMARY KEY, session_id TEXT, query_hash TEXT NOT NULL, company_id TEXT NOT NULL,
      prompt_version_id TEXT, canary_arm TEXT, created_at TEXT
    )
    """,
    """
    CREATE TABLE policy_answer_helpfulness (
      id TEXT PRIMARY KEY, trace_session_id TEXT NOT NULL, company_id TEXT,
      user_id TEXT NOT NULL, helpful BOOLEAN NOT NULL, comment TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      UNIQUE (trace_session_id, user_id)
    )
    """,
]


@pytest.fixture
def patched(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA:
            conn.execute(text(stmt))
        conn.execute(
            text(
                "INSERT INTO policy_assistant_traces (id, query_hash, company_id) "
                "VALUES ('trace-1', 'hashA', 'co-1')"
            )
        )
    monkeypatch.setattr(policy_helpfulness_service, "SessionLocal", sessionmaker(bind=engine))
    return engine


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(policy_helpfulness.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    return app


def test_requires_auth():
    app = FastAPI()
    app.include_router(policy_helpfulness.router)
    client = TestClient(app)
    r = client.post("/api/policy-assistant/helpfulness", json={"trace_session_id": "trace-1", "helpful": True})
    assert r.status_code == 401


def test_vote_lands_with_company_from_trace(patched):
    client = TestClient(_app())
    r = client.post(
        "/api/policy-assistant/helpfulness",
        json={"trace_session_id": "trace-1", "helpful": True, "comment": "clear"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["company_id"] == "co-1"
    assert body["user_id"] == "user-1"
    assert body["helpful"] is True


def test_vote_is_idempotent_and_updates(patched):
    client = TestClient(_app())
    first = client.post(
        "/api/policy-assistant/helpfulness", json={"trace_session_id": "trace-1", "helpful": True}
    )
    assert first.status_code == 201, first.text
    # Flip the vote → updates the same row, no duplicate.
    second = client.post(
        "/api/policy-assistant/helpfulness", json={"trace_session_id": "trace-1", "helpful": False}
    )
    assert second.status_code == 201, second.text

    Session = policy_helpfulness_service.SessionLocal
    s = Session()
    try:
        n = s.execute(text("SELECT COUNT(*) FROM policy_answer_helpfulness")).scalar()
        helpful = s.execute(text("SELECT helpful FROM policy_answer_helpfulness")).scalar()
    finally:
        s.close()
    assert n == 1
    assert helpful in (0, False)


def test_unknown_trace_returns_404(patched):
    client = TestClient(_app())
    r = client.post(
        "/api/policy-assistant/helpfulness", json={"trace_session_id": "nope", "helpful": True}
    )
    assert r.status_code == 404, r.text


def test_router_registered_in_both_entrypoints():
    """CLAUDE.md hard rule: the route must be registered in BOTH main entrypoints."""
    prod = (
        __import__("pathlib").Path(_REPO_ROOT) / "backend" / "main.py"
    ).read_text()
    modular = (
        __import__("pathlib").Path(_REPO_ROOT) / "backend" / "app" / "main.py"
    ).read_text()
    assert "policy_helpfulness" in prod, "missing registration in backend/main.py"
    assert "policy_helpfulness" in modular, "missing registration in backend/app/main.py"

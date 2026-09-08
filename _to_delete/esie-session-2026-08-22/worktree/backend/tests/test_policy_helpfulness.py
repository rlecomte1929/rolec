"""WS-E helpfulness endpoint — scenario tests (app task spec).

Covers:
(a) company_id comes from the trace (not the request body) — sending a bogus
    company_id in the body has no effect.
(b) Re-vote replaces: flip 👍→👎 on the same (trace, user) leaves exactly one
    row with helpful=False.
(c) A different user's vote on the same trace coexists (distinct rows).
(d) Auth is required — unauthenticated request is rejected.
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
      id TEXT PRIMARY KEY, session_id TEXT, query_hash TEXT NOT NULL,
      company_id TEXT NOT NULL, prompt_version_id TEXT, canary_arm TEXT,
      created_at TEXT
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
                "VALUES ('trace-A', 'h1', 'co-real')"
            )
        )
    monkeypatch.setattr(policy_helpfulness_service, "SessionLocal", sessionmaker(bind=engine))
    return engine


def _app(user_id: str = "user-1") -> FastAPI:
    app = FastAPI()
    app.include_router(policy_helpfulness.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id}
    return app


# (a) Body's company_id is ignored — company comes from the trace (co-real).
def test_company_id_from_trace_not_body(patched):
    client = TestClient(_app())
    r = client.post(
        "/api/policy-assistant/helpfulness",
        json={
            "trace_session_id": "trace-A",
            "helpful": True,
            "company_id": "bogus-company",   # not in schema — silently ignored
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["company_id"] == "co-real", "company_id must come from the trace, not the body"
    assert body["user_id"] == "user-1"


# (b) Re-vote replaces: flip 👍 → 👎 leaves exactly one row with helpful=False.
def test_revote_replaces(patched):
    client = TestClient(_app())
    r1 = client.post(
        "/api/policy-assistant/helpfulness",
        json={"trace_session_id": "trace-A", "helpful": True},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        "/api/policy-assistant/helpfulness",
        json={"trace_session_id": "trace-A", "helpful": False},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["helpful"] is False

    Session = policy_helpfulness_service.SessionLocal
    s = Session()
    try:
        count = s.execute(
            text("SELECT COUNT(*) FROM policy_answer_helpfulness WHERE trace_session_id='trace-A'")
        ).scalar()
        stored = s.execute(
            text("SELECT helpful FROM policy_answer_helpfulness WHERE trace_session_id='trace-A'")
        ).scalar()
    finally:
        s.close()
    assert count == 1, f"expected 1 row, got {count}"
    assert stored in (0, False), "helpful must be False after flip"


# (c) Different user's vote on same trace coexists as a distinct row.
def test_different_users_votes_coexist(patched):
    client_u1 = TestClient(_app(user_id="user-1"))
    client_u2 = TestClient(_app(user_id="user-2"))

    r1 = client_u1.post(
        "/api/policy-assistant/helpfulness",
        json={"trace_session_id": "trace-A", "helpful": True},
    )
    assert r1.status_code == 201, r1.text

    r2 = client_u2.post(
        "/api/policy-assistant/helpfulness",
        json={"trace_session_id": "trace-A", "helpful": False},
    )
    assert r2.status_code == 201, r2.text

    Session = policy_helpfulness_service.SessionLocal
    s = Session()
    try:
        count = s.execute(
            text("SELECT COUNT(*) FROM policy_answer_helpfulness WHERE trace_session_id='trace-A'")
        ).scalar()
        users = set(
            row[0]
            for row in s.execute(
                text("SELECT user_id FROM policy_answer_helpfulness WHERE trace_session_id='trace-A'")
            ).fetchall()
        )
    finally:
        s.close()
    assert count == 2, f"expected 2 rows (one per user), got {count}"
    assert users == {"user-1", "user-2"}


# (d) Unauthenticated request is rejected.
def test_auth_required():
    app = FastAPI()
    app.include_router(policy_helpfulness.router)
    # No dependency_overrides — get_current_user raises 401 when no token provided.
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        "/api/policy-assistant/helpfulness",
        json={"trace_session_id": "trace-A", "helpful": True},
    )
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


def test_malformed_trace_uuid_is_unknown_not_500():
    """policy_assistant_traces.id is uuid in Postgres; a non-uuid trace_session_id
    makes `WHERE id = :tid` raise DataError (→ prod 500). _lookup_trace_company must
    catch it, roll back the aborted tx, and return None so the caller 404s.
    """
    from sqlalchemy.exc import DataError

    class _Sess:
        def __init__(self):
            self.rolled_back = False

        def execute(self, *a, **k):
            raise DataError("invalid input syntax for type uuid", None, None)

        def rollback(self):
            self.rolled_back = True

    s = _Sess()
    assert policy_helpfulness_service._lookup_trace_company(s, "not-a-uuid") is None
    assert s.rolled_back is True, "aborted transaction must be rolled back"

"""
Tests for backend/app/routers/ai_feedback.py — Parker Step E.

A minimal FastAPI app mounts only the ai_feedback router. get_current_user is
overridden to a fixed reviewer, and ai_feedback_service.SessionLocal is patched to
an in-memory SQLite DB seeded with a prompt version + trace so the row's
attribution (prompt_version_id / canary_arm) is derived from the trace.
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

from backend.app.routers import ai_feedback  # noqa: E402
from backend.app.services import ai_feedback_service  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402


_SCHEMA = [
    """
    CREATE TABLE prompt_versions (
      id TEXT PRIMARY KEY, task_key TEXT NOT NULL, version INTEGER NOT NULL,
      system_prompt TEXT NOT NULL, model_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'prod'
    )
    """,
    """
    CREATE TABLE policy_assistant_traces (
      id TEXT PRIMARY KEY, session_id TEXT, query_hash TEXT NOT NULL, company_id TEXT NOT NULL,
      prompt_version_id TEXT, canary_arm TEXT, created_at TEXT
    )
    """,
    """
    CREATE TABLE ai_human_feedback (
      id TEXT PRIMARY KEY, trace_session_id TEXT NOT NULL, reviewer_user_id TEXT NOT NULL,
      verdict TEXT NOT NULL, edited_output_json TEXT, comment TEXT,
      prompt_version_id TEXT REFERENCES prompt_versions(id), canary_arm TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      UNIQUE (trace_session_id, reviewer_user_id)
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
        # Seed a prompt version + a trace attributed to it.
        conn.execute(
            text(
                "INSERT INTO prompt_versions (id, task_key, version, system_prompt, model_name, status) "
                "VALUES ('v-canary', 'policy_assistant_answer', 2, 'SYS', 'm', 'canary')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO policy_assistant_traces (id, query_hash, company_id, prompt_version_id, canary_arm) "
                "VALUES ('trace-1', 'hashA', 'co-1', 'v-canary', 'canary')"
            )
        )
    monkeypatch.setattr(ai_feedback_service, "SessionLocal", sessionmaker(bind=engine))
    return engine


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(ai_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "rev-1", "is_admin": True}
    return app


def test_requires_auth():
    # No dependency override and no Authorization header → 401 from get_current_user.
    app = FastAPI()
    app.include_router(ai_feedback.router)
    client = TestClient(app)
    r = client.post("/api/ai/feedback", json={"trace_session_id": "trace-1", "verdict": "approved"})
    assert r.status_code == 401


def test_feedback_lands_with_attribution(patched):
    client = TestClient(_app())
    r = client.post(
        "/api/ai/feedback",
        json={"trace_session_id": "trace-1", "verdict": "approved", "comment": "good"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["prompt_version_id"] == "v-canary"
    assert body["canary_arm"] == "canary"
    assert body["verdict"] == "approved"


def test_feedback_is_idempotent(patched):
    client = TestClient(_app())
    payload = {"trace_session_id": "trace-1", "verdict": "approved"}
    first = client.post("/api/ai/feedback", json=payload)
    assert first.status_code == 201, first.text
    # Re-submit with a different verdict → updates, does not duplicate.
    second = client.post(
        "/api/ai/feedback", json={"trace_session_id": "trace-1", "verdict": "rejected"}
    )
    assert second.status_code == 201, second.text

    Session = ai_feedback_service.SessionLocal
    s = Session()
    try:
        n = s.execute(text("SELECT COUNT(*) FROM ai_human_feedback")).scalar()
        verdict = s.execute(text("SELECT verdict FROM ai_human_feedback")).scalar()
    finally:
        s.close()
    assert n == 1
    assert verdict == "rejected"


def test_bad_verdict_is_rejected(patched):
    client = TestClient(_app())
    r = client.post(
        "/api/ai/feedback", json={"trace_session_id": "trace-1", "verdict": "maybe"}
    )
    assert r.status_code == 422, r.text


def test_unknown_trace_returns_404(patched):
    client = TestClient(_app())
    r = client.post(
        "/api/ai/feedback", json={"trace_session_id": "nope", "verdict": "approved"}
    )
    assert r.status_code == 404, r.text

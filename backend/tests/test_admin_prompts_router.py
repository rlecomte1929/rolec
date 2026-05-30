"""
Tests for backend/app/routers/admin_prompts.py — Parker Step D.

A minimal FastAPI app mounts only the admin_prompts router. require_admin is
overridden (admin vs non-admin), and prompt_registry.SessionLocal is patched to
an in-memory SQLite engine so the router exercises the real service code.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin_prompts  # noqa: E402
from backend.app.services import prompt_registry  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402


_SCHEMA = [
    """
    CREATE TABLE prompt_versions (
      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
      task_key TEXT NOT NULL,
      version INTEGER NOT NULL,
      system_prompt TEXT NOT NULL,
      user_template TEXT,
      model_name TEXT NOT NULL,
      temperature NUMERIC NOT NULL DEFAULT 0.0,
      max_tokens INTEGER NOT NULL DEFAULT 1024,
      status TEXT NOT NULL DEFAULT 'draft',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      created_by TEXT,
      notes TEXT,
      UNIQUE (task_key, version)
    )
    """,
    "CREATE UNIQUE INDEX ux_one_prod ON prompt_versions(task_key) WHERE status='prod'",
    """
    CREATE TABLE prompt_routing (
      task_key TEXT PRIMARY KEY,
      canary_share NUMERIC NOT NULL DEFAULT 0.0
    )
    """,
]


@pytest.fixture
def patched_registry(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA:
            conn.execute(text(stmt))
    monkeypatch.setattr(prompt_registry, "SessionLocal", sessionmaker(bind=engine))
    yield


def _admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_prompts.router, prefix="/api/admin")
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "is_admin": True}
    return app


def _non_admin_app() -> FastAPI:
    def _forbidden():
        raise HTTPException(status_code=403, detail="admin only")

    app = FastAPI()
    app.include_router(admin_prompts.router, prefix="/api/admin")
    app.dependency_overrides[require_admin] = _forbidden
    return app


def test_non_admin_gets_403(patched_registry):
    client = TestClient(_non_admin_app())
    assert client.get("/api/admin/prompts").status_code == 403
    assert client.post("/api/admin/prompts", json={
        "task_key": "t", "system_prompt": "s", "model_name": "m",
    }).status_code == 403


def test_admin_list_empty(patched_registry):
    client = TestClient(_admin_app())
    r = client.get("/api/admin/prompts")
    assert r.status_code == 200
    assert r.json() == []


def test_admin_create_and_list(patched_registry):
    client = TestClient(_admin_app())
    r = client.post("/api/admin/prompts", json={
        "task_key": "policy_extraction",
        "system_prompt": "SYS",
        "model_name": "claude-sonnet-4-6",
        "user_template": "t={{truncated}}",
        "max_tokens": 4096,
        "status": "draft",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["status"] == "draft"

    listed = client.get("/api/admin/prompts/policy_extraction").json()
    assert len(listed) == 1
    assert listed[0]["task_key"] == "policy_extraction"


def test_admin_promote(patched_registry):
    client = TestClient(_admin_app())
    v1 = client.post("/api/admin/prompts", json={
        "task_key": "t", "system_prompt": "V1", "model_name": "m", "status": "prod",
    }).json()
    v2 = client.post("/api/admin/prompts", json={
        "task_key": "t", "system_prompt": "V2", "model_name": "m", "status": "draft",
    }).json()

    r = client.post(f"/api/admin/prompts/{v2['id']}/promote", json={"target_status": "prod"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "prod"

    rows = {row["id"]: row for row in client.get("/api/admin/prompts/t").json()}
    assert rows[v1["id"]]["status"] == "archived"
    assert rows[v2["id"]]["status"] == "prod"


def test_admin_set_canary_share(patched_registry):
    client = TestClient(_admin_app())
    client.post("/api/admin/prompts", json={
        "task_key": "t", "system_prompt": "S", "model_name": "m", "status": "prod",
    })
    r = client.post("/api/admin/prompts/t/canary-share", json={"canary_share": 0.25})
    assert r.status_code == 200, r.text
    assert r.json()["canary_share"] == 0.25

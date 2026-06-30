"""Tests for GET/POST /api/admin/ai-controls (Task 4).

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

from backend.app.routers import admin_settings  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_logs (
  id              TEXT PRIMARY KEY,
  entity_type     TEXT NOT NULL,
  entity_id       TEXT NOT NULL,
  action_type     TEXT NOT NULL,
  old_value_json  TEXT,
  new_value_json  TEXT,
  actor_type      TEXT NOT NULL,
  actor_id        TEXT,
  created_at      TEXT
);
CREATE TABLE IF NOT EXISTS platform_settings (
  key         TEXT PRIMARY KEY,
  value_json  TEXT NOT NULL,
  updated_by  TEXT,
  updated_at  TEXT
);
"""


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_client(db_session, *, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_settings.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin-1", "is_admin": is_admin}
    app.dependency_overrides[admin_settings._get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def admin_client(db_session):
    return _make_client(db_session, is_admin=True)


@pytest.fixture()
def non_admin_client(db_session):
    return _make_client(db_session, is_admin=False)


# ── GET /api/admin/ai-controls ────────────────────────────────────────────────


def test_get_returns_all_known_keys(admin_client):
    r = admin_client.get("/api/admin/ai-controls")
    assert r.status_code == 200
    body = r.json()
    keys = {c["key"] for c in body["controls"]}
    assert keys == {
        "policy_rag_groundedness_gate",
        "policy_rag_groundedness_min_score",
        "policy_rag_rerank",
        "supplier_learned_weights",
    }


def test_get_source_is_default_when_nothing_set(admin_client, monkeypatch):
    for env_var in [
        "POLICY_RAG_GROUNDEDNESS_GATE", "POLICY_RAG_GROUNDEDNESS_MIN_SCORE",
        "POLICY_RAG_RERANK", "SUPPLIER_LEARNED_WEIGHTS",
    ]:
        monkeypatch.delenv(env_var, raising=False)
    r = admin_client.get("/api/admin/ai-controls")
    body = r.json()
    for c in body["controls"]:
        assert c["source"] == "default", f"expected default for {c['key']}, got {c['source']}"


def test_get_source_is_env_when_env_set(admin_client, monkeypatch):
    monkeypatch.setenv("POLICY_RAG_RERANK", "1")
    r = admin_client.get("/api/admin/ai-controls")
    body = r.json()
    ctrl = next(c for c in body["controls"] if c["key"] == "policy_rag_rerank")
    assert ctrl["source"] == "env"
    assert ctrl["value"] == "1"


def test_get_source_is_db_after_post(admin_client, db_session, monkeypatch):
    monkeypatch.delenv("POLICY_RAG_RERANK", raising=False)
    admin_client.post(
        "/api/admin/ai-controls",
        json={"key": "policy_rag_rerank", "value": "1", "reason": "test"},
    )
    r = admin_client.get("/api/admin/ai-controls")
    body = r.json()
    ctrl = next(c for c in body["controls"] if c["key"] == "policy_rag_rerank")
    assert ctrl["source"] == "db"
    assert ctrl["value"] == "1"


# ── POST /api/admin/ai-controls — auth gate ───────────────────────────────────


def test_post_rejects_non_admin(non_admin_client):
    r = non_admin_client.post(
        "/api/admin/ai-controls",
        json={"key": "policy_rag_rerank", "value": "1", "reason": "x"},
    )
    assert r.status_code == 403


# ── POST /api/admin/ai-controls — main path ──────────────────────────────────


def test_set_ai_control_audited(admin_client, db_session, monkeypatch):
    monkeypatch.delenv("POLICY_RAG_RERANK", raising=False)
    r = admin_client.post(
        "/api/admin/ai-controls",
        json={"key": "policy_rag_rerank", "value": "1", "reason": "enable"},
    )
    assert r.status_code == 200

    from backend.app.services.platform_settings import get_setting
    assert get_setting("policy_rag_rerank", env_var="POLICY_RAG_RERANK", default="0", db=db_session) == "1"

    rows = db_session.execute(
        text("SELECT new_value_json FROM audit_logs WHERE entity_type = 'platform_settings'")
    ).all()
    assert rows, "expected at least one audit_logs row"
    ai_changed = [r for r in rows if json.loads(r[0]).get("event") == "ai_setting_changed"]
    assert ai_changed, "expected an ai_setting_changed audit row"


def test_post_rejects_unknown_key(admin_client):
    r = admin_client.post(
        "/api/admin/ai-controls",
        json={"key": "unknown_flag", "value": "1", "reason": "test"},
    )
    assert r.status_code == 400


def test_post_persists_value_in_db(admin_client, db_session, monkeypatch):
    monkeypatch.delenv("POLICY_RAG_GROUNDEDNESS_GATE", raising=False)
    admin_client.post(
        "/api/admin/ai-controls",
        json={"key": "policy_rag_groundedness_gate", "value": "1", "reason": "enable gate"},
    )
    row = db_session.execute(
        text("SELECT value_json FROM platform_settings WHERE key = 'policy_rag_groundedness_gate'")
    ).first()
    assert row is not None
    assert json.loads(row[0]) == "1"


# ── POST /api/admin/ai-controls/kill/{feature} ───────────────────────────────


def test_kill_forces_zero(admin_client, db_session, monkeypatch):
    monkeypatch.delenv("POLICY_RAG_RERANK", raising=False)
    admin_client.post(
        "/api/admin/ai-controls",
        json={"key": "policy_rag_rerank", "value": "1", "reason": "enable"},
    )
    r = admin_client.post("/api/admin/ai-controls/kill/policy_rag_rerank")
    assert r.status_code == 200
    assert r.json()["value"] == "0"

    from backend.app.services.platform_settings import get_setting
    assert get_setting("policy_rag_rerank", env_var="POLICY_RAG_RERANK", default="0", db=db_session) == "0"


def test_kill_rejects_unknown_feature(admin_client):
    r = admin_client.post("/api/admin/ai-controls/kill/nonexistent_feature")
    assert r.status_code == 400


def test_kill_requires_admin(non_admin_client):
    r = non_admin_client.post("/api/admin/ai-controls/kill/policy_rag_rerank")
    assert r.status_code == 403


# ── Behavior-preservation: service helpers default OFF when no env ─────────────


def test_groundedness_gate_default_off_no_env(monkeypatch):
    """_groundedness_gate_enabled() returns False when env is unset (no DB value)."""
    monkeypatch.delenv("POLICY_RAG_GROUNDEDNESS_GATE", raising=False)
    from backend.app.services.policy_assistant_rag_engine import _groundedness_gate_enabled
    assert _groundedness_gate_enabled() is False


def test_rerank_default_off_no_env(monkeypatch):
    monkeypatch.delenv("POLICY_RAG_RERANK", raising=False)
    from backend.app.services.policy_chunk_retriever import _rerank_enabled
    assert _rerank_enabled() is False


def test_learned_weights_default_off_no_env(monkeypatch):
    monkeypatch.delenv("SUPPLIER_LEARNED_WEIGHTS", raising=False)
    from backend.app.recommendations.weights import _learned_weights_enabled
    assert _learned_weights_enabled() is False

"""TDD tests for R1 — GET /api/feedback/mine reporter-status list.

Safety property: the endpoint only returns rows belonging to the calling user.

Mirrors test_feedback_ticket.py setup exactly: patches
``feedback_router_module.db.engine`` (the reference the router captured at
import time) so the fixture is suite-order-independent.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import feedback as feedback_router_module  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

# ── Schema (identical to test_feedback_ticket.py) ─────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  user_id      TEXT,
  page_url     TEXT,
  category     TEXT DEFAULT 'other',
  message      TEXT,
  status       TEXT DEFAULT 'new',
  created_at   TEXT DEFAULT (datetime('now')),
  report_id    TEXT,
  screenshot_data TEXT
);
CREATE TABLE IF NOT EXISTS feedback_status (
  stream          TEXT NOT NULL,
  source_id       TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'new',
  owner           TEXT,
  resolution      TEXT,
  updated_at      TEXT,
  severity        TEXT,
  area            TEXT,
  reporter_id     TEXT,
  dispatch_ref    TEXT,
  dispatch_status TEXT,
  PRIMARY KEY (stream, source_id)
)
"""

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def sqlite_engine():
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
    return engine


@pytest.fixture()
def patched_db(sqlite_engine, monkeypatch):
    """Patch the router's own db reference (suite-order safe)."""
    monkeypatch.setattr(feedback_router_module.db, "engine", sqlite_engine)
    yield sqlite_engine


def _make_client(user_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(feedback_router_module.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "auth_uuid": user_id,
        "is_admin": False,
    }
    return TestClient(app)


# ── Seed helpers ──────────────────────────────────────────────────────────────


def _seed_feedback(
    engine,
    *,
    user_id: str,
    report_id: str,
    category: str = "bug",
    message: str = "test message",
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO feedback (user_id, category, message, report_id) "
                "VALUES (:uid, :cat, :msg, :rid)"
            ),
            {"uid": user_id, "cat": category, "msg": message, "rid": report_id},
        )


def _seed_status(
    engine,
    *,
    report_id: str,
    reporter_id: str,
    severity: str = "high",
    area: str = "api",
    dispatch_status: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO feedback_status "
                "(stream, source_id, status, severity, area, reporter_id, dispatch_status, updated_at) "
                "VALUES ('product', :rid, 'new', :sev, :area, :rep, :ds, datetime('now'))"
            ),
            {"rid": report_id, "sev": severity, "area": area, "rep": reporter_id, "ds": dispatch_status},
        )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_mine_returns_only_callers_reports(patched_db):
    """Caller A sees only their own reports — user B's are invisible."""
    rid_a1 = f"BUG-{uuid.uuid4().hex[:8]}"
    rid_a2 = f"BUG-{uuid.uuid4().hex[:8]}"
    rid_b = f"BUG-{uuid.uuid4().hex[:8]}"

    _seed_feedback(patched_db, user_id="user-a", report_id=rid_a1, message="Login fails for me")
    _seed_feedback(patched_db, user_id="user-a", report_id=rid_a2, message="Dashboard blank screen")
    _seed_feedback(patched_db, user_id="user-b", report_id=rid_b, message="B's private report — must not leak")

    client = _make_client("user-a")
    resp = client.get("/api/feedback/mine")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "reports" in body
    report_ids = {r["report_id"] for r in body["reports"]}
    assert rid_a1 in report_ids, "Own report A1 must be returned"
    assert rid_a2 in report_ids, "Own report A2 must be returned"
    assert rid_b not in report_ids, "Another user's report must NOT appear"


def test_mine_surfaces_feedback_status_fields(patched_db):
    """status, severity, area and dispatch_status from feedback_status appear in each item."""
    rid = f"BUG-{uuid.uuid4().hex[:8]}"
    _seed_feedback(patched_db, user_id="user-c", report_id=rid, message="Critical isolation bug found")
    _seed_status(
        patched_db,
        report_id=rid,
        reporter_id="user-c",
        severity="critical",
        area="isolation",
        dispatch_status="dispatched",
    )

    client = _make_client("user-c")
    resp = client.get("/api/feedback/mine")
    assert resp.status_code == 200, resp.text
    reports = resp.json()["reports"]
    assert len(reports) == 1
    r = reports[0]
    assert r["report_id"] == rid
    assert r["status"] == "new"
    assert r["severity"] == "critical"
    assert r["area"] == "isolation"
    assert r["dispatch_status"] == "dispatched"


def test_mine_empty_for_user_with_no_reports(patched_db):
    """A user who has never submitted feedback gets an empty reports list."""
    client = _make_client("user-brand-new")
    resp = client.get("/api/feedback/mine")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"reports": []}


def test_mine_message_excerpt_capped_at_120_chars(patched_db):
    """message_excerpt is at most 120 characters regardless of original length."""
    rid = f"BUG-{uuid.uuid4().hex[:8]}"
    long_msg = "verbose description " * 20  # 400+ chars
    _seed_feedback(patched_db, user_id="user-d", report_id=rid, message=long_msg)

    client = _make_client("user-d")
    resp = client.get("/api/feedback/mine")
    assert resp.status_code == 200
    excerpt = resp.json()["reports"][0]["message_excerpt"]
    assert len(excerpt) <= 120, f"Excerpt too long: {len(excerpt)} chars"


def test_mine_null_status_fields_when_no_ticket(patched_db):
    """Reports without a feedback_status row return null for status fields (LEFT JOIN)."""
    rid = f"BUG-{uuid.uuid4().hex[:8]}"
    _seed_feedback(patched_db, user_id="user-e", report_id=rid, message="Unclassified report")
    # No _seed_status call — no feedback_status row

    client = _make_client("user-e")
    resp = client.get("/api/feedback/mine")
    assert resp.status_code == 200
    r = resp.json()["reports"][0]
    assert r["report_id"] == rid
    assert r["status"] is None
    assert r["severity"] is None
    assert r["area"] is None
    assert r["dispatch_status"] is None


def test_mine_requires_auth():
    """GET /api/feedback/mine with no Authorization header → 401."""
    app = FastAPI()
    app.include_router(feedback_router_module.router)
    # No dependency override → real get_current_user raises 401 without header
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/feedback/mine")
    assert resp.status_code == 401

"""Tests for GET/PATCH /api/admin/feedback (Task 6 — unified feedback console).

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

from backend.app.routers import admin_feedback  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  page_url TEXT,
  category TEXT DEFAULT 'other',
  message TEXT,
  status TEXT DEFAULT 'new',
  created_at TEXT,
  report_id TEXT,
  screenshot_data TEXT,
  reporter_email TEXT,
  reporter_name TEXT,
  reporter_role TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,
  email TEXT,
  full_name TEXT,
  role TEXT
);
CREATE TABLE IF NOT EXISTS ai_human_feedback (
  id TEXT PRIMARY KEY,
  trace_session_id TEXT,
  reviewer_user_id TEXT,
  verdict TEXT,
  edited_output_json TEXT,
  comment TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS policy_answer_helpfulness (
  id TEXT PRIMARY KEY,
  trace_session_id TEXT,
  company_id TEXT,
  user_id TEXT,
  helpful INTEGER,
  comment TEXT,
  created_at TEXT
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
);
CREATE TABLE IF NOT EXISTS hr_feedback (
  id TEXT PRIMARY KEY,
  assignment_id TEXT,
  hr_user_id TEXT,
  employee_user_id TEXT,
  message TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS case_feedback (
  id TEXT PRIMARY KEY,
  case_id TEXT,
  canonical_case_id TEXT,
  assignment_id TEXT,
  author_user_id TEXT,
  author_role TEXT,
  section TEXT,
  message TEXT,
  created_at_ts TEXT
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
        # Seed one row per stream.
        # Product row carries a stored reporter snapshot (works even when user_id is NULL).
        conn.execute(text(
            "INSERT INTO feedback (id, user_id, page_url, category, message, status, created_at, "
            "reporter_email, reporter_name, reporter_role) "
            "VALUES ('f-001', 'u-1', '/dashboard', 'bug', 'Button broken', 'new', '2026-06-01T10:00:00', "
            "'reporter@acme.com', 'Rita Reporter', 'employee')"
        ))
        conn.execute(text(
            "INSERT INTO ai_human_feedback (id, trace_session_id, reviewer_user_id, verdict, comment, created_at) "
            "VALUES ('h-001', 'trace-001', 'rev-1', 'approved', 'Looks good', '2026-06-01T11:00:00')"
        ))
        # Helpfulness row has no stored reporter → resolved from profiles by user_id.
        conn.execute(text(
            "INSERT INTO policy_answer_helpfulness (id, trace_session_id, company_id, user_id, helpful, comment, created_at) "
            "VALUES ('p-001', 'trace-002', 'co-1', 'emp-1', 1, 'Very helpful', '2026-06-01T12:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO profiles (id, email, full_name, role) "
            "VALUES ('emp-1', 'emp1@acme.com', 'Ellen Emp', 'employee')"
        ))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_client(db_session, *, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin-1", "is_admin": is_admin}
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def admin_client(db_session):
    return _make_client(db_session, is_admin=True)


@pytest.fixture()
def non_admin_client(db_session):
    return _make_client(db_session, is_admin=False)


# ── GET tests ─────────────────────────────────────────────────────────────────


def test_get_returns_all_streams(admin_client):
    """GET /api/admin/feedback returns normalized rows from ≥2 streams."""
    resp = admin_client.get("/api/admin/feedback")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    streams = {r["stream"] for r in body["items"]}
    assert streams >= {"product", "ai_answers", "helpfulness"}


def test_get_stream_filter(admin_client):
    """GET ?stream=helpfulness returns only helpfulness rows."""
    resp = admin_client.get("/api/admin/feedback?stream=helpfulness")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(r["stream"] == "helpfulness" for r in items)


def test_get_includes_hr_streams(admin_client, db_session):
    """PR-A: hr_feedback + case_feedback surface as hr_assignment / hr_case streams."""
    db_session.execute(text(
        "INSERT INTO hr_feedback (id, assignment_id, hr_user_id, employee_user_id, message, created_at) "
        "VALUES ('hf-001', 'asg-1', 'hr-1', 'emp-1', 'Please upload your passport', '2026-06-02T09:00:00')"
    ))
    db_session.execute(text(
        "INSERT INTO case_feedback "
        "(id, case_id, canonical_case_id, assignment_id, author_user_id, author_role, section, message, created_at_ts) "
        "VALUES ('cf-001', 'case-1', 'canon-1', 'asg-1', 'hr-2', 'HR', 'documents', 'Section looks incomplete', '2026-06-02T10:00:00')"
    ))
    db_session.commit()

    items = admin_client.get("/api/admin/feedback").json()["items"]
    streams = {r["stream"] for r in items}
    assert {"hr_assignment", "hr_case"} <= streams

    hr_row = next(r for r in items if r["stream"] == "hr_assignment")
    assert hr_row["text"] == "Please upload your passport"
    assert hr_row["source_ref"] == "asg-1"
    assert hr_row["user_id"] == "hr-1"

    case_row = next(r for r in items if r["stream"] == "hr_case")
    assert case_row["text"] == "Section looks incomplete"
    assert case_row["verdict"] == "documents"       # section → verdict
    assert case_row["source_ref"] == "canon-1"       # COALESCE(canonical_case_id, case_id)
    assert case_row["user_id"] == "hr-2"


def test_get_stream_filter_hr_case_coalesces_case_id(admin_client, db_session):
    """?stream=hr_case returns only case rows; NULL canonical_case_id falls back to case_id."""
    db_session.execute(text(
        "INSERT INTO case_feedback "
        "(id, case_id, assignment_id, author_user_id, author_role, section, message, created_at_ts) "
        "VALUES ('cf-002', 'case-2', 'asg-2', 'hr-3', 'HR', 'housing', 'Need more detail', '2026-06-02T11:00:00')"
    ))
    db_session.commit()
    items = admin_client.get("/api/admin/feedback?stream=hr_case").json()["items"]
    assert items and all(r["stream"] == "hr_case" for r in items)
    row = next(r for r in items if r["id"] == "cf-002")
    assert row["source_ref"] == "case-2"


def test_get_normalized_fields(admin_client):
    """Normalized row has the required fields."""
    resp = admin_client.get("/api/admin/feedback?stream=product")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    for field in ("id", "stream", "source_ref", "text", "verdict", "user_id", "created_at"):
        assert field in item, f"missing field: {field}"


def test_get_left_joins_feedback_status(admin_client, db_session):
    """status/owner/resolution from feedback_status are included (null when no triage)."""
    resp = admin_client.get("/api/admin/feedback?stream=product")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    # No triage yet — status should be None (no row in feedback_status)
    assert item["status"] is None
    assert item["owner"] is None

    # Now seed a triage row and re-query
    db_session.execute(text(
        "INSERT INTO feedback_status (stream, source_id, status, owner, resolution, updated_at) "
        "VALUES ('product', 'f-001', 'reviewed', 'alice', 'Fixed', '2026-06-01T13:00:00')"
    ))
    db_session.commit()
    resp2 = admin_client.get("/api/admin/feedback?stream=product")
    item2 = resp2.json()["items"][0]
    assert item2["status"] == "reviewed"
    assert item2["owner"] == "alice"


def test_get_non_admin_returns_403(non_admin_client):
    """Non-admin gets 403 (require_admin raises 403 Forbidden)."""
    resp = non_admin_client.get("/api/admin/feedback")
    assert resp.status_code == 403


# ── PATCH tests ───────────────────────────────────────────────────────────────


def test_patch_upserts_status(admin_client, db_session):
    """PATCH upserts feedback_status and returns the new state."""
    resp = admin_client.patch(
        "/api/admin/feedback/product/f-001",
        json={"status": "reviewed", "owner": "bob", "resolution": "Will fix"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reviewed"
    assert body["stream"] == "product"
    assert body["id"] == "f-001"

    # Verify persisted in DB
    row = db_session.execute(
        text("SELECT status, owner, resolution FROM feedback_status WHERE stream='product' AND source_id='f-001'")
    ).fetchone()
    assert row is not None
    assert row[0] == "reviewed"
    assert row[1] == "bob"
    assert row[2] == "Will fix"


def test_patch_writes_audit_row(admin_client, db_session):
    """PATCH writes a feedback_triaged audit log row."""
    admin_client.patch(
        "/api/admin/feedback/helpfulness/p-001",
        json={"status": "acted_on"},
    )
    rows = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchall()
    assert len(rows) >= 1
    events = [json.loads(r[0])["event"] for r in rows if r[0]]
    assert "feedback_triaged" in events


def test_patch_upsert_overwrites(admin_client, db_session):
    """Second PATCH overwrites the first (upsert semantics)."""
    admin_client.patch("/api/admin/feedback/product/f-001", json={"status": "reviewed"})
    admin_client.patch("/api/admin/feedback/product/f-001", json={"status": "closed"})
    row = db_session.execute(
        text("SELECT status FROM feedback_status WHERE stream='product' AND source_id='f-001'")
    ).fetchone()
    assert row[0] == "closed"


def test_patch_invalid_status_400(admin_client):
    """Invalid status value → 400."""
    resp = admin_client.patch(
        "/api/admin/feedback/product/f-001",
        json={"status": "bogus"},
    )
    assert resp.status_code == 400


def test_patch_non_admin_returns_403(non_admin_client):
    """Non-admin PATCH → 403 (require_admin raises 403 Forbidden)."""
    resp = non_admin_client.patch(
        "/api/admin/feedback/product/f-001",
        json={"status": "reviewed"},
    )
    assert resp.status_code == 403


# ── Screenshot tests ────────────────────────────────────────────────────────


def _seed_screenshot_row(db_session):
    db_session.execute(text(
        "INSERT INTO feedback (id, user_id, page_url, category, message, status, created_at, screenshot_data) "
        "VALUES ('f-shot', 'u-2', '/journey', 'bug', 'has shot', 'new', '2026-06-02T10:00:00', "
        "'data:image/jpeg;base64,AAAA')"
    ))
    db_session.commit()


def test_list_flags_has_screenshot(admin_client, db_session):
    """The list marks product rows with/without a screenshot; other streams are always false."""
    _seed_screenshot_row(db_session)
    items = admin_client.get("/api/admin/feedback").json()["items"]
    by_id = {r["id"]: r for r in items}
    assert by_id["f-shot"]["has_screenshot"]        # row with screenshot → truthy
    assert not by_id["f-001"]["has_screenshot"]     # product row without one → falsy
    assert not by_id["h-001"]["has_screenshot"]     # non-product stream → falsy


def test_get_screenshot_returns_data(admin_client, db_session):
    """GET .../product/{id}/screenshot returns the stored base64 data URL."""
    _seed_screenshot_row(db_session)
    resp = admin_client.get("/api/admin/feedback/product/f-shot/screenshot")
    assert resp.status_code == 200
    assert resp.json()["screenshot_data"] == "data:image/jpeg;base64,AAAA"


def test_get_screenshot_non_product_is_null(admin_client):
    """Non-product streams never carry a screenshot → null, no DB lookup."""
    resp = admin_client.get("/api/admin/feedback/helpfulness/p-001/screenshot")
    assert resp.status_code == 200
    assert resp.json()["screenshot_data"] is None


def test_get_screenshot_missing_returns_404(admin_client):
    resp = admin_client.get("/api/admin/feedback/product/does-not-exist/screenshot")
    assert resp.status_code == 404


def test_get_screenshot_requires_admin(non_admin_client):
    resp = non_admin_client.get("/api/admin/feedback/product/f-001/screenshot")
    assert resp.status_code == 403


# ── Reporter identity tests ─────────────────────────────────────────────────


def _row(items, row_id):
    return next(r for r in items if r["id"] == row_id)


def test_product_row_uses_stored_reporter(admin_client):
    """A product row returns its stored reporter snapshot (works even if user_id is unresolvable)."""
    items = admin_client.get("/api/admin/feedback").json()["items"]
    r = _row(items, "f-001")
    assert r["reporter_name"] == "Rita Reporter"
    assert r["reporter_email"] == "reporter@acme.com"
    assert r["reporter_role"] == "employee"


def test_other_stream_resolves_reporter_from_profiles(admin_client):
    """A stream row with no stored reporter is resolved via profiles by user_id."""
    items = admin_client.get("/api/admin/feedback").json()["items"]
    r = _row(items, "p-001")  # helpfulness, user_id='emp-1'
    assert r["reporter_name"] == "Ellen Emp"
    assert r["reporter_email"] == "emp1@acme.com"
    assert r["reporter_role"] == "employee"


def test_unresolvable_reporter_is_null(admin_client):
    """A row with neither a stored reporter nor a matching profile → null (NULL-safe, no crash)."""
    items = admin_client.get("/api/admin/feedback").json()["items"]
    r = _row(items, "h-001")  # ai_answers, reviewer_user_id='rev-1' (no profile)
    assert r["reporter_name"] is None
    assert r["reporter_email"] is None

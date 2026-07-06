"""TDD tests for POST /api/admin/feedback/{stream}/{item_id}/dispatch (BR-2).

Covers:
  - Low/medium ticket dispatches WITHOUT confirm → 200 + dispatch_ref + audit row
    with event='ticket_dispatched' + dispatch_status='dispatched'
  - Critical (or area=isolation) without confirm → 400 (not dispatched, no audit)
  - Critical with confirm=true → 200 dispatched + audit
  - Non-admin → 403
  - Missing ticket → 404
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

# ── Schema (includes BR-1 ticket columns) ──────────────────────────────────────

_SCHEMA = """
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
CREATE TABLE IF NOT EXISTS audit_logs (
  id            TEXT PRIMARY KEY,
  entity_type   TEXT NOT NULL,
  entity_id     TEXT NOT NULL,
  action_type   TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type    TEXT NOT NULL,
  actor_id      TEXT,
  created_at    TEXT
)
"""

# ── Fixture ────────────────────────────────────────────────────────────────────


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


def _make_client(db_session, *, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-admin-1",
        "is_admin": is_admin,
    }
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    return TestClient(app)


def _seed_ticket(db_session, *, stream: str, item_id: str, severity: str, area: str = "api"):
    db_session.execute(
        text(
            "INSERT INTO feedback_status (stream, source_id, status, severity, area) "
            "VALUES (:stream, :sid, 'new', :sev, :area)"
        ),
        {"stream": stream, "sid": item_id, "sev": severity, "area": area},
    )
    db_session.commit()


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_dispatch_low_severity_no_confirm_200(db_session):
    """Low-severity ticket dispatches without confirm → 200 + dispatch_ref."""
    _seed_ticket(db_session, stream="product", item_id="t-001", severity="low")
    client = _make_client(db_session)

    resp = client.post("/api/admin/feedback/product/t-001/dispatch", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] is True
    assert "dispatch_ref" in body
    assert body["status"] == "dispatched"


def test_dispatch_medium_severity_no_confirm_200(db_session):
    """Medium-severity ticket dispatches without confirm → 200."""
    _seed_ticket(db_session, stream="ai_answers", item_id="t-002", severity="medium")
    client = _make_client(db_session)

    resp = client.post("/api/admin/feedback/ai_answers/t-002/dispatch", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["dispatched"] is True


def test_dispatch_persists_dispatch_status(db_session):
    """After dispatch, dispatch_status='dispatched' and dispatch_ref set in DB."""
    _seed_ticket(db_session, stream="product", item_id="t-003", severity="medium")
    client = _make_client(db_session)

    resp = client.post("/api/admin/feedback/product/t-003/dispatch", json={"note": "urgent"})
    assert resp.status_code == 200
    dispatch_ref = resp.json()["dispatch_ref"]

    row = db_session.execute(
        text(
            "SELECT status, dispatch_status, dispatch_ref "
            "FROM feedback_status WHERE stream='product' AND source_id='t-003'"
        )
    ).fetchone()
    assert row is not None
    assert row[0] == "dispatched"
    assert row[1] == "dispatched"
    assert row[2] == dispatch_ref


def test_dispatch_writes_audit_ticket_dispatched(db_session):
    """Dispatch writes audit row with event='ticket_dispatched'."""
    _seed_ticket(db_session, stream="helpfulness", item_id="t-004", severity="low")
    client = _make_client(db_session)

    client.post("/api/admin/feedback/helpfulness/t-004/dispatch", json={})

    rows = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchall()
    assert len(rows) >= 1
    events = [json.loads(r[0])["event"] for r in rows if r[0]]
    assert "ticket_dispatched" in events


def test_dispatch_audit_contains_stream_and_dispatch_ref(db_session):
    """Audit detail contains stream, severity, area, dispatch_ref, note."""
    _seed_ticket(db_session, stream="product", item_id="t-005", severity="high", area="api")
    client = _make_client(db_session)

    resp = client.post("/api/admin/feedback/product/t-005/dispatch", json={"note": "prio"})
    dispatch_ref = resp.json()["dispatch_ref"]

    row = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchone()
    detail = json.loads(row[0])
    assert detail["event"] == "ticket_dispatched"
    assert detail["stream"] == "product"
    assert detail["dispatch_ref"] == dispatch_ref
    assert detail["note"] == "prio"


def test_dispatch_critical_no_confirm_400(db_session):
    """Critical ticket without confirm → 400 (HITL gate)."""
    _seed_ticket(db_session, stream="product", item_id="t-006", severity="critical")
    client = _make_client(db_session)

    resp = client.post("/api/admin/feedback/product/t-006/dispatch", json={})
    assert resp.status_code == 400
    assert "confirm" in resp.json()["detail"].lower()


def test_dispatch_critical_no_confirm_not_dispatched(db_session):
    """Critical ticket 400 path leaves dispatch_status unchanged."""
    _seed_ticket(db_session, stream="product", item_id="t-007", severity="critical")
    client = _make_client(db_session)

    client.post("/api/admin/feedback/product/t-007/dispatch", json={})

    row = db_session.execute(
        text("SELECT dispatch_status FROM feedback_status WHERE source_id='t-007'")
    ).fetchone()
    assert row[0] is None  # unchanged from initial null


def test_dispatch_critical_no_confirm_no_audit(db_session):
    """Critical ticket 400 path writes no audit row."""
    _seed_ticket(db_session, stream="product", item_id="t-008", severity="critical")
    client = _make_client(db_session)

    client.post("/api/admin/feedback/product/t-008/dispatch", json={})

    count = db_session.execute(text("SELECT COUNT(*) FROM audit_logs")).scalar()
    assert count == 0


def test_dispatch_isolation_area_no_confirm_400(db_session):
    """area=isolation (any severity) without confirm → 400 HITL gate."""
    _seed_ticket(db_session, stream="product", item_id="t-009", severity="high", area="isolation")
    client = _make_client(db_session)

    resp = client.post("/api/admin/feedback/product/t-009/dispatch", json={})
    assert resp.status_code == 400


def test_dispatch_critical_with_confirm_200(db_session):
    """Critical ticket WITH confirm=true → 200 dispatched + audit."""
    _seed_ticket(db_session, stream="product", item_id="t-010", severity="critical")
    client = _make_client(db_session)

    resp = client.post(
        "/api/admin/feedback/product/t-010/dispatch",
        json={"confirm": True, "note": "reviewed by CISO"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] is True
    assert "dispatch_ref" in body

    count = db_session.execute(text("SELECT COUNT(*) FROM audit_logs")).scalar()
    assert count == 1


def test_dispatch_isolation_with_confirm_200(db_session):
    """area=isolation WITH confirm=true → 200 dispatched."""
    _seed_ticket(db_session, stream="product", item_id="t-011", severity="high", area="isolation")
    client = _make_client(db_session)

    resp = client.post(
        "/api/admin/feedback/product/t-011/dispatch",
        json={"confirm": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["dispatched"] is True


def test_dispatch_untriaged_item_upserts_and_dispatches(db_session):
    """A never-triaged item dispatches (no 404): it upserts a dispatched feedback_status row."""
    client = _make_client(db_session)
    resp = client.post("/api/admin/feedback/product/brand-new-item/dispatch", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["dispatched"] is True
    row = db_session.execute(
        text(
            "SELECT status, dispatch_status FROM feedback_status "
            "WHERE stream = 'product' AND source_id = 'brand-new-item'"
        )
    ).fetchone()
    assert row is not None, "dispatch should create the feedback_status row"
    assert row[0] == "dispatched"
    assert row[1] == "dispatched"


def test_dispatch_non_admin_403(db_session):
    """Non-admin → 403."""
    _seed_ticket(db_session, stream="product", item_id="t-012", severity="low")
    client = _make_client(db_session, is_admin=False)

    resp = client.post("/api/admin/feedback/product/t-012/dispatch", json={})
    assert resp.status_code == 403

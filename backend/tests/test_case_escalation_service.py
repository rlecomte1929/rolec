"""W2-3 — service tests for case escalation (create / list / resolve), SQLite-backed."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.services import case_escalation_service as svc

_SCHEMA = """
CREATE TABLE case_escalations (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, company_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'specialist', reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', assignee TEXT, sla_due_at TEXT,
  created_by TEXT, resolution_note TEXT, resolved_at TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action_type TEXT,
  old_value_json TEXT, new_value_json TEXT, actor_type TEXT, actor_id TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_CO_A = "11111111-1111-1111-1111-111111111111"
_CO_B = "22222222-2222-2222-2222-222222222222"
_USER = "33333333-3333-3333-3333-333333333333"


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in _SCHEMA.split(";"))):
            conn.execute(text(stmt))
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(svc, "SessionLocal", TestSession)
    return TestSession


def test_create_then_list(session_factory):
    e = svc.create_escalation(case_id="case-1", company_id=_CO_A, reason="Need legal review",
                              kind="legal", created_by=_USER)
    assert e["status"] == "open" and e["kind"] == "legal" and e["case_id"] == "case-1"
    rows = svc.list_escalations("case-1", _CO_A)
    assert len(rows) == 1 and rows[0]["id"] == e["id"]
    # audit row written
    with session_factory() as db:
        n = db.execute(text("SELECT COUNT(*) FROM audit_logs WHERE entity_type='case_escalation' "
                            "AND action_type='insert'")).scalar()
    assert n == 1


def test_invalid_kind_defaults_to_specialist(session_factory):
    e = svc.create_escalation(case_id="c", company_id=_CO_A, reason="x", kind="bogus", created_by=_USER)
    assert e["kind"] == "specialist"


def test_list_is_company_scoped(session_factory):
    svc.create_escalation(case_id="c", company_id=_CO_A, reason="a", created_by=_USER)
    assert svc.list_escalations("c", _CO_A) != []
    assert svc.list_escalations("c", _CO_B) == []   # other tenant sees nothing


def test_resolve_sets_status_and_note(session_factory):
    e = svc.create_escalation(case_id="c", company_id=_CO_A, reason="a", created_by=_USER)
    out = svc.resolve_escalation(e["id"], _CO_A, resolution_note="handled by counsel", resolved_by=_USER)
    assert out is not None and out["status"] == "resolved"
    assert out["resolution_note"] == "handled by counsel" and out["resolved_at"] is not None


def test_resolve_cross_tenant_returns_none(session_factory):
    e = svc.create_escalation(case_id="c", company_id=_CO_A, reason="a", created_by=_USER)
    assert svc.resolve_escalation(e["id"], _CO_B, resolution_note="nope", resolved_by=_USER) is None
    # and it stays open for the rightful owner
    assert svc.list_escalations("c", _CO_A)[0]["status"] == "open"


def test_resolve_unknown_id_returns_none(session_factory):
    assert svc.resolve_escalation("no-such-id", _CO_A, resolution_note="x") is None

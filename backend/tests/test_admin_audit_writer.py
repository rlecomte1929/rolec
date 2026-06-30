"""Tests for record_admin_event() — writes to audit_logs on SQLite (TDD, A-07 / task-1)."""
from __future__ import annotations

import json
import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# SQLite schema mirrors audit_logs (no uuid type, no check constraints)
_AUDIT_SCHEMA = """
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
    )
    with engine.begin() as conn:
        conn.execute(text(_AUDIT_SCHEMA))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def test_record_admin_event_writes_row(db_session):
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    record_admin_event(db_session, actor_id="u1", event="test_event", detail={"k": 1})

    rows = db_session.execute(
        text("SELECT new_value_json FROM audit_logs WHERE actor_id = 'u1'")
    ).all()
    assert rows, "expected at least one audit_logs row"
    data = json.loads(rows[0][0])
    assert data["event"] == "test_event"
    assert data["k"] == 1


def test_record_admin_event_stores_entity(db_session):
    """entity and entity_id forwarded to the row."""
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    record_admin_event(
        db_session,
        actor_id="u2",
        event="country_update",
        entity="countries",
        entity_id="DE",
        detail={"field": "visa_policy"},
    )

    rows = db_session.execute(
        text(
            "SELECT entity_type, entity_id, action_type, actor_type, new_value_json"
            " FROM audit_logs WHERE actor_id = 'u2'"
        )
    ).all()
    assert rows
    row = rows[0]
    assert row[0] == "countries"
    assert row[1] == "DE"
    assert row[2] == "update"
    assert row[3] == "human"
    data = json.loads(row[4])
    assert data["event"] == "country_update"
    assert data["field"] == "visa_policy"


def test_record_admin_event_never_raises(db_session):
    """Best-effort: must not propagate exceptions even on a broken session."""
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    class BrokenSession:
        def connection(self):
            raise RuntimeError("simulated DB failure")

    # Should complete without raising.
    record_admin_event(BrokenSession(), actor_id="u3", event="whatever")

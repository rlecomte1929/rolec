"""Tests for record_admin_event() — writes to audit_logs on SQLite (TDD, A-07 / task-1).

UUID-safety tests (the Important review finding):
  Postgres types actor_id and entity_id as ``uuid``.  Legacy admin IDs such as
  ``"seed-admin-testingapril"`` are plain text and would raise
  ``invalid input syntax for type uuid`` — swallowed silently by best-effort,
  so the row is never written.  The fix normalises non-UUID values before the
  INSERT.  Because SQLite accepts any TEXT in uuid columns the normalization
  behaviour must be asserted directly (not just that SQLite accepted the row).
"""
from __future__ import annotations

import json
import os
import sys
import uuid

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


# ── existing behaviour tests (updated for UUID-safe normalization) ─────────


def test_record_admin_event_writes_row(db_session):
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    record_admin_event(db_session, actor_id="u1", event="test_event", detail={"k": 1})

    # "u1" is non-UUID → actor_id column is NULL; query by event instead.
    rows = db_session.execute(
        text("SELECT actor_id, new_value_json FROM audit_logs WHERE entity_type = 'admin_event'")
    ).all()
    assert rows, "expected at least one audit_logs row"
    actor_col, nv_json = rows[0]
    data = json.loads(nv_json)
    assert data["event"] == "test_event"
    assert data["k"] == 1
    # Non-UUID actor_id is routed to new_value.actor_ref; column is NULL.
    assert actor_col is None
    assert data["actor_ref"] == "u1"


def test_record_admin_event_stores_entity(db_session):
    """entity and entity_id forwarded to the row; non-UUID entity_id goes to entity_ref."""
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
            "SELECT entity_type, entity_id, action_type, actor_type, actor_id, new_value_json"
            " FROM audit_logs WHERE entity_type = 'countries'"
        )
    ).all()
    assert rows
    row = rows[0]
    entity_type, entity_id_col, action_type, actor_type, actor_id_col, nv_json = row
    data = json.loads(nv_json)

    assert entity_type == "countries"
    # "DE" is non-UUID → column holds an auto-generated UUID, original goes to entity_ref.
    assert entity_id_col != "DE", "non-UUID entity_id must not be stored raw in the uuid column"
    try:
        uuid.UUID(entity_id_col)
    except ValueError:
        pytest.fail(f"entity_id column should hold a valid UUID, got {entity_id_col!r}")
    assert data["entity_ref"] == "DE"
    assert action_type == "update"
    assert actor_type == "human"
    # "u2" is non-UUID → actor_id column is NULL.
    assert actor_id_col is None
    assert data["actor_ref"] == "u2"
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


# ── UUID-safety tests (the Important review finding) ─────────────────────────


def test_non_uuid_actor_id_routes_to_sidecar(db_session):
    """Legacy text actor_id → new_value.actor_ref; actor_id column gets NULL.

    This asserts the normalisation logic directly: Postgres would reject a
    non-UUID value bound to a uuid column; the fix must route it to
    new_value_json and use NULL (nullable column) so the INSERT always succeeds.
    """
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    legacy_id = "seed-admin-testingapril"
    record_admin_event(db_session, actor_id=legacy_id, event="policy_updated")

    rows = db_session.execute(
        text("SELECT actor_id, new_value_json FROM audit_logs WHERE entity_type = 'admin_event'")
    ).all()
    assert rows, "audit row must be written even for non-UUID actor_id"
    actor_col, nv_json = rows[0]

    # Column must be NULL (non-UUID cannot be stored in a Postgres uuid column).
    assert actor_col is None, (
        f"actor_id column must be NULL for non-UUID input, got {actor_col!r}"
    )
    data = json.loads(nv_json)
    # Original identifier must be preserved in new_value.
    assert data.get("actor_ref") == legacy_id, (
        f"expected actor_ref={legacy_id!r} in new_value_json, got {data}"
    )


def test_valid_uuid_actor_id_lands_in_column(db_session):
    """A genuine UUID actor_id is stored in the actor_id column, not diverted."""
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    actor_uuid = str(uuid.uuid4())
    record_admin_event(db_session, actor_id=actor_uuid, event="uuid_actor_event")

    rows = db_session.execute(
        text(
            "SELECT actor_id, new_value_json FROM audit_logs"
            " WHERE entity_type = 'admin_event'"
        )
    ).all()
    assert rows
    actor_col, nv_json = rows[0]

    # UUID goes straight to the column.
    assert actor_col == actor_uuid, (
        f"valid UUID actor_id should land in the column, got {actor_col!r}"
    )
    data = json.loads(nv_json)
    # No sidecar key for valid UUIDs.
    assert "actor_ref" not in data, "valid UUID must not produce an actor_ref sidecar"


def test_non_uuid_entity_id_routes_to_sidecar(db_session):
    """Non-UUID entity_id → new_value.entity_ref; entity_id column gets a generated UUID."""
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    record_admin_event(
        db_session,
        actor_id=str(uuid.uuid4()),
        event="country_hardening",
        entity="countries",
        entity_id="FR",
    )

    rows = db_session.execute(
        text(
            "SELECT entity_id, new_value_json FROM audit_logs WHERE entity_type = 'countries'"
        )
    ).all()
    assert rows
    entity_id_col, nv_json = rows[0]

    # Column must hold a valid UUID (auto-generated).
    try:
        uuid.UUID(entity_id_col)
    except (ValueError, TypeError):
        pytest.fail(
            f"entity_id column must hold a generated UUID for non-UUID input, got {entity_id_col!r}"
        )
    data = json.loads(nv_json)
    assert data.get("entity_ref") == "FR", (
        f"expected entity_ref='FR' in new_value_json, got {data}"
    )


def test_uuid_entity_id_lands_in_column(db_session):
    """A genuine UUID entity_id is stored in the entity_id column directly."""
    from backend.app.services.admin_audit import record_admin_event  # noqa: PLC0415

    eid = str(uuid.uuid4())
    record_admin_event(
        db_session,
        actor_id=str(uuid.uuid4()),
        event="uuid_entity_event",
        entity_id=eid,
    )

    rows = db_session.execute(
        text(
            "SELECT entity_id, new_value_json FROM audit_logs WHERE entity_type = 'admin_event'"
        )
    ).all()
    assert rows
    entity_id_col, nv_json = rows[0]

    assert entity_id_col == eid
    data = json.loads(nv_json)
    assert "entity_ref" not in data, "valid UUID must not produce an entity_ref sidecar"

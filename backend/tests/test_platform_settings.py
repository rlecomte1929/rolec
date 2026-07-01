"""Tests for platform_settings store + env→DB→default resolver (Task 3).

All tests run on an in-memory SQLite database; no real Postgres or Supabase
connection needed.  The db_session fixture creates both ``audit_logs``
(required by record_admin_event called inside set_setting) and
``platform_settings``.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# SQLite schema mirrors platform_settings and audit_logs (no jsonb / timestamptz types).
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


# ── precedence test (from brief, verbatim) ─────────────────────────────────


def test_get_setting_precedence(db_session, monkeypatch):
    from backend.app.services import platform_settings as ps

    # default when nothing set
    assert ps.get_setting("x", default="d", db=db_session) == "d"
    # DB overrides default
    ps.set_setting(db_session, "x", "dbval", actor_id="a")
    assert ps.get_setting("x", default="d", db=db_session) == "dbval"
    # env overrides DB
    monkeypatch.setenv("X_ENV", "envval")
    assert ps.get_setting("x", env_var="X_ENV", default="d", db=db_session) == "envval"


# ── additional coverage ──────────────────────────────────────────────────────


def test_get_setting_no_db_returns_default():
    """get_setting with db=None skips the DB look-up and returns default."""
    from backend.app.services import platform_settings as ps

    result = ps.get_setting("nonexistent_key", default="fallback")
    assert result == "fallback"


def test_get_setting_missing_table_returns_default():
    """Best-effort: returns default when the table is absent (pre-migration)."""
    from backend.app.services import platform_settings as ps

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    bare_session = Session()
    try:
        # No table created — simulates pre-migration environment.
        result = ps.get_setting("key", default="safe", db=bare_session)
        assert result == "safe"
    finally:
        bare_session.close()
        engine.dispose()


def test_set_setting_upsert(db_session):
    """set_setting is idempotent: second call updates the existing row."""
    from backend.app.services import platform_settings as ps

    ps.set_setting(db_session, "feature_flag", "off", actor_id="admin1")
    ps.set_setting(db_session, "feature_flag", "on", actor_id="admin1")

    val = ps.get_setting("feature_flag", db=db_session)
    assert val == "on"


def test_list_settings_returns_rows(db_session):
    """list_settings returns all written rows as dicts with a 'key' field."""
    from backend.app.services import platform_settings as ps

    ps.set_setting(db_session, "alpha", "1", actor_id="adm")
    ps.set_setting(db_session, "beta", "2", actor_id="adm")

    rows = ps.list_settings(db_session)
    keys = {r["key"] for r in rows}
    assert keys == {"alpha", "beta"}
    vals = {r["key"]: r["value"] for r in rows}
    assert vals["alpha"] == "1"
    assert vals["beta"] == "2"


def test_list_settings_empty_table(db_session):
    """list_settings returns [] when no settings have been written."""
    from backend.app.services import platform_settings as ps

    assert ps.list_settings(db_session) == []


def test_list_settings_missing_table_returns_empty():
    """Best-effort: list_settings returns [] when table is absent."""
    from backend.app.services import platform_settings as ps

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    bare_session = Session()
    try:
        assert ps.list_settings(bare_session) == []
    finally:
        bare_session.close()
        engine.dispose()


def test_env_var_wins_even_when_no_db(monkeypatch):
    """env_var takes precedence regardless of whether db is passed."""
    from backend.app.services import platform_settings as ps

    monkeypatch.setenv("SOME_SETTING", "from_env")
    assert ps.get_setting("anything", env_var="SOME_SETTING", default="d") == "from_env"


def test_set_setting_writes_audit_log(db_session):
    """set_setting calls record_admin_event which writes to audit_logs."""
    from backend.app.services import platform_settings as ps

    ps.set_setting(db_session, "my_key", "my_val", actor_id="audit-actor")

    rows = db_session.execute(
        text("SELECT entity_type, new_value_json FROM audit_logs")
    ).all()
    assert rows, "expected an audit_logs row after set_setting"
    entity_types = {r[0] for r in rows}
    assert "platform_settings" in entity_types

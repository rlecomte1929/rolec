"""Tests for the autopilot-event -> feedback_status bridge (Task 5):
advance_status_for_event() advances feedback_status.dispatch_status when the autopilot's
CI funnel events (fix_attempted/merged/canary_passed/task_done/canary_failed/reverted)
arrive at POST /api/crons/autopilot-event, joining on the dashless-lower 16-hex prefix
of notion_task_id.
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.services.feedback_status_bridge import advance_status_for_event


_SCHEMA = """
CREATE TABLE feedback (
  id TEXT PRIMARY KEY, user_id TEXT, page_url TEXT, category TEXT, message TEXT,
  status TEXT, created_at TEXT, report_id TEXT, screenshot_data TEXT,
  reporter_email TEXT, reporter_name TEXT, reporter_role TEXT, client_context TEXT
);
CREATE TABLE feedback_status (
  stream TEXT NOT NULL, source_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','reviewed','acted_on','closed')),
  owner TEXT, resolution TEXT, updated_at TEXT, severity TEXT, area TEXT,
  reporter_id TEXT, dispatch_ref TEXT, dispatch_status TEXT, dispatch_context TEXT, dismissed_at TEXT,
  notion_task_id TEXT, autonomy_tier TEXT, spec_drafted_at TEXT, dispatched_at TEXT,
  triaged_at TEXT, in_progress_at TEXT, deployed_at TEXT, done_at TEXT,
  pr_url TEXT, pr_number INTEGER, branch_name TEXT,
  PRIMARY KEY (stream, source_id)
);
"""


@pytest.fixture()
def session_with_dispatched_row():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as c:
        for stmt in _SCHEMA.strip().split(";"):
            if stmt.strip():
                c.execute(text(stmt))
        c.execute(text(
            "INSERT INTO feedback_status (stream, source_id, status, dispatch_status, notion_task_id) "
            "VALUES ('product', 'seed', 'acted_on', 'dispatched', '0123456789abcdef0123456789abcdef')"
        ))
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


def test_bridge_advances_on_task_done(session_with_dispatched_row):
    s = session_with_dispatched_row  # feedback_status row with notion_task_id='0123456789abcdef0123456789abcdef'
    ok = advance_status_for_event(s, "autopilot.task_done", "0123456789abcdef")  # 16-hex prefix
    assert ok is True
    row = s.execute(text("SELECT dispatch_status, done_at FROM feedback_status WHERE source_id=:i"),
                    {"i": "seed"}).fetchone()
    assert row[0] == "done" and row[1] is not None


def test_bridge_noop_on_unknown_entity(session_with_dispatched_row):
    assert advance_status_for_event(session_with_dispatched_row, "autopilot.merged", "ffffffffffffffff") is False


def test_bridge_ignores_non_lifecycle_events(session_with_dispatched_row):
    assert advance_status_for_event(session_with_dispatched_row, "autopilot.run_started", "0123456789abcdef") is False

"""feedback_notion_sync — polls Notion Work Queue Status → advances feedback_status.

get_task_meta is monkeypatched (no live Notion). record_admin_event is left real: the
minimal SQLite fixture has no admin-events table, so the audit write fails — the service's
SAVEPOINT must roll back only the audit and keep the status UPDATE (this test proves that).
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.services import feedback_notion_sync as sync
from backend.app.services import notion_work_queue as nwq

_SCHEMA = """
CREATE TABLE feedback_status (
  stream TEXT NOT NULL, source_id TEXT NOT NULL,
  status TEXT, dispatch_ref TEXT, dispatch_status TEXT,
  triaged_at TEXT, spec_drafted_at TEXT, dispatched_at TEXT, in_progress_at TEXT,
  deployed_at TEXT, done_at TEXT, dismissed_at TEXT, updated_at TEXT,
  PRIMARY KEY (stream, source_id)
);
"""

# page-id fragments (dashless) → Notion Status
_META = {
    "c898d1ef15ab07f1d3": {"status": "Done", "aiq_id": "AIQ-1454"},
    "c59729cefca38baf93": {"status": "AI in Progress", "aiq_id": "AIQ-1455"},
    "a187fd53c5f9c97b": {"status": "Ready for AI", "aiq_id": "AIQ-9999"},  # unmapped → no change
}


def _fake_get_task_meta(page_id):
    flat = (page_id or "").replace("-", "")
    for frag, meta in _META.items():
        if frag in flat:
            return meta
    return {"status": "Ready for AI", "aiq_id": None}


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as c:
        c.execute(text(_SCHEMA))
        c.execute(text(
            "INSERT INTO feedback_status (stream, source_id, status, dispatch_ref, dispatch_status) VALUES "
            "('product','fb-done','new','https://app.notion.com/p/x-395887c64d4881c898d1ef15ab07f1d3','dispatched'),"
            "('product','fb-prog','new','https://app.notion.com/p/y-395887c64d4881c59729cefca38baf93','dispatched'),"
            "('product','fb-ready','new','https://app.notion.com/p/z-395887c64d488101a187fd53c5f9c97b','dispatched'),"
            "('product','fb-term','closed','https://app.notion.com/p/w-395887c64d4881c898d1ef15ab07f1d3','done'),"
            "('product','fb-none','new',NULL,NULL)"
        ))
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_dry_run_reports_without_writing(session, monkeypatch):
    monkeypatch.setattr(nwq, "get_task_meta", _fake_get_task_meta)
    res = sync.sync_dispatched_statuses(dry_run=True, session=session)
    assert res["dry_run"] is True
    assert res["changed"] == 2  # fb-done→done, fb-prog→in_progress (ready=unmapped, term/none skipped)
    assert {c["source_id"]: c["to"] for c in res["changes"]} == {"fb-done": "done", "fb-prog": "in_progress"}
    # nothing written
    assert session.execute(text("SELECT dispatch_status FROM feedback_status WHERE source_id='fb-done'")).fetchone()[0] == "dispatched"


def test_apply_advances_done_and_in_progress(session, monkeypatch):
    monkeypatch.setattr(nwq, "get_task_meta", _fake_get_task_meta)
    res = sync.sync_dispatched_statuses(dry_run=False, session=session)
    assert res["changed"] == 2
    done = session.execute(text("SELECT dispatch_status, status, done_at FROM feedback_status WHERE source_id='fb-done'")).fetchone()
    assert done[0] == "done" and done[1] == "closed" and done[2] is not None  # green + triage closed + timestamp
    prog = session.execute(text("SELECT dispatch_status, status, in_progress_at FROM feedback_status WHERE source_id='fb-prog'")).fetchone()
    assert prog[0] == "in_progress" and prog[1] == "new" and prog[2] is not None
    # unmapped, terminal, and undispatched rows are untouched
    assert session.execute(text("SELECT dispatch_status FROM feedback_status WHERE source_id='fb-ready'")).fetchone()[0] == "dispatched"
    assert session.execute(text("SELECT dispatch_status FROM feedback_status WHERE source_id='fb-term'")).fetchone()[0] == "done"
    assert session.execute(text("SELECT dispatch_status FROM feedback_status WHERE source_id='fb-none'")).fetchone()[0] is None


def test_notion_failure_is_skipped_not_raised(session, monkeypatch):
    def _boom(_pid):
        raise RuntimeError("notion unreachable")
    monkeypatch.setattr(nwq, "get_task_meta", _boom)
    res = sync.sync_dispatched_statuses(dry_run=False, session=session)
    assert res["changed"] == 0 and res["errors"] >= 1  # swept without raising

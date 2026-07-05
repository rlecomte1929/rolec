"""AIQ-1414 — end-to-end coordinator test (real store round-trip on SQLite).

Exercises the REAL `coordinator_agent.respond` → `coordinator_session_store` path against a
real in-memory SQLite `ai_coordinator_sessions` table (validating the store's SQLite
tolerance + persistence + summary fold). Only the context builder, the LLM client, and the
tracer are stubbed — no network, no key. Proves PII masking end-to-end and the fold.
"""

import json

from sqlalchemy import create_engine, text

from backend.app.services import coordinator_agent as agent
from backend.app.services import coordinator_session_store as store

# SQLite-compatible mirror of supabase/migrations/20260829000000_ai_coordinator_sessions.sql
_DDL = """
CREATE TABLE ai_coordinator_sessions (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  case_id TEXT NOT NULL,
  employee_id TEXT,
  company_id TEXT NOT NULL,
  rolling_summary TEXT NOT NULL DEFAULT '',
  recent_turns TEXT NOT NULL DEFAULT '[]',
  last_event_cursor TEXT,
  model TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
  status TEXT NOT NULL DEFAULT 'active',
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_active_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_acs_case ON ai_coordinator_sessions(case_id);
"""

_CTX = {
    "case": {"company_id": "acme", "case_id": "c-1"},
    "_meta": {"company_id": "acme"},
    "people": [], "documents": [], "requirements": [],
    "recent_events": [{"kind": "event", "at": "2026-07-04T00:00:00+00:00", "type": "visa_update"}],
    "rolling_summary": "",
}


class _FakeClient:
    def __init__(self):
        self.requests = []

    def complete(self, req):
        self.requests.append(req)
        return {"text": "Next: book your medical.", "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 120, "output_tokens": 25}}


class _NoopTracer:
    def __init__(self, **_kw):
        pass

    def record_llm_call(self, **_kw):
        pass

    def flush(self):
        pass


def _wire(monkeypatch, engine, fake_client):
    class _DB:
        pass
    _DB.engine = engine
    monkeypatch.setattr(agent, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(agent, "build_coordinator_context_for_case", lambda _cid, **_k: dict(_CTX))
    monkeypatch.setattr(agent, "get_default_client", lambda: fake_client)
    monkeypatch.setattr(agent, "TraceSession", _NoopTracer)
    monkeypatch.setattr(agent.store, "_get_db", lambda: _DB())


def _session_row(engine, case_id="c-1"):
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT rolling_summary, recent_turns, status FROM ai_coordinator_sessions WHERE case_id=:c"),
            {"c": case_id},
        ).mappings().first()
    return dict(r) if r else None


def test_store_round_trips_and_masks_on_sqlite(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        for stmt in _DDL.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    fake = _FakeClient()
    _wire(monkeypatch, engine, fake)

    out = agent.respond("c-1", "my email is sarah.chen@acme.com — what's next?", employee_id="emp-1")
    assert out["answer"] == "Next: book your medical."

    row = _session_row(engine)
    assert row is not None  # real INSERT round-tripped on SQLite
    turns = json.loads(row["recent_turns"])
    assert len(turns) == 1
    # PII masked both in the persisted turn AND in what the LLM client received
    assert "sarah.chen@acme.com" not in row["recent_turns"]
    assert "sarah.chen@acme.com" not in fake.requests[0].user_message


def test_fold_runs_and_truncates_on_sqlite(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        for stmt in _DDL.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    fake = _FakeClient()
    _wire(monkeypatch, engine, fake)

    # run past the window so a fold triggers (needs_fold when turns > MAX_RECENT_TURNS)
    for i in range(store.MAX_RECENT_TURNS + 1):
        agent.respond("c-1", f"turn {i} — reach me at +33 6 12 34 56 78", employee_id="emp-1")

    row = _session_row(engine)
    turns = json.loads(row["recent_turns"])
    # after the fold, only the tail is kept verbatim and the summary was updated
    assert len(turns) == agent._KEEP_AFTER_FOLD
    assert row["rolling_summary"] != ""
    # the fold's own LLM output is our fake text; masking held throughout
    assert "+33 6 12 34 56 78" not in row["recent_turns"]

"""AIQ-1414 Phase 3b — unit tests for coordinator tool_use structured actions.

DB- and network-free: the LLM client, tracer, store and db are faked. Verifies that a
tool_use response writes a case_events row + appends a confirmation, that a plain answer
writes nothing, and that a failed action never breaks the turn (best-effort).
"""

from backend.app.services import coordinator_agent as agent

SONNET = "claude-sonnet-4-6"


class _ClientWithTool:
    def __init__(self, tool_use, text=""):
        self._tool = tool_use
        self._text = text

    def complete(self, req):
        assert req.tools and req.tool_choice, "coordinator must pass tools + tool_choice"
        return {"text": self._text, "tool_use": self._tool, "model": SONNET,
                "usage": {"input_tokens": 10, "output_tokens": 5}}


class _Tracer:
    def __init__(self, **kw):
        pass

    def record_llm_call(self, **kw):
        pass

    def flush(self):
        pass


class _FakeDB:
    def __init__(self, fail=False):
        self.events = []
        self._fail = fail

    def insert_case_event(self, **kw):
        if self._fail:
            raise RuntimeError("boom")
        self.events.append(kw)


def _ctx(company="acme"):
    return {"case": {"company_id": company}, "_meta": {}, "people": [], "documents": [],
            "requirements": [], "recent_events": []}


def _wire(monkeypatch, client, fakedb):
    monkeypatch.setattr(agent, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(agent, "build_coordinator_context_for_case", lambda *a, **k: _ctx())
    monkeypatch.setattr(agent.store, "get_or_create",
                        lambda *a, **k: {"id": "s1", "model": SONNET, "rolling_summary": "", "recent_turns": []})
    monkeypatch.setattr(agent, "get_default_client", lambda: client)
    monkeypatch.setattr(agent, "TraceSession", _Tracer)
    monkeypatch.setattr(agent, "_breaker_model", lambda *a, **k: SONNET)
    monkeypatch.setattr(agent, "_persist_turn", lambda *a, **k: None)
    monkeypatch.setattr(agent.store, "_get_db", lambda: fakedb)


def test_flag_risk_writes_case_event_and_confirms(monkeypatch):
    db = _FakeDB()
    _wire(monkeypatch, _ClientWithTool(
        {"action": "flag_risk", "detail": "Visa appointment slipping", "severity": "high"}), db)
    out = agent.respond("case-1", "flag the visa risk", employee_id="emp-1")
    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "coordinator.risk_flagged"
    assert ev["payload"]["severity"] == "high"
    assert ev["actor_principal_id"] == "emp-1"
    assert "flagged a risk" in out["answer"]


def test_add_note_writes_event_with_fallback_actor(monkeypatch):
    db = _FakeDB()
    _wire(monkeypatch, _ClientWithTool({"action": "add_note", "detail": "Prefers Munich district"}), db)
    out = agent.respond("case-1", "note that", employee_id=None)
    assert db.events[0]["event_type"] == "coordinator.note_added"
    assert db.events[0]["actor_principal_id"] == "ai_coordinator"  # fallback when no employee
    assert "added a note" in out["answer"]


def test_plain_answer_writes_no_event(monkeypatch):
    db = _FakeDB()
    _wire(monkeypatch, _ClientWithTool(None, text="Here's your next step."), db)
    out = agent.respond("case-1", "how's it going")
    assert db.events == []
    assert out["answer"] == "Here's your next step."


def test_action_dispatch_is_fail_soft(monkeypatch):
    db = _FakeDB(fail=True)
    _wire(monkeypatch, _ClientWithTool({"action": "flag_risk", "detail": "x"}, text="answer"), db)
    out = agent.respond("case-1", "flag it")
    assert out["answer"] == "answer"  # insert raised, but the turn still returns cleanly


def test_unknown_action_is_ignored(monkeypatch):
    db = _FakeDB()
    _wire(monkeypatch, _ClientWithTool({"action": "delete_case", "detail": "oops"}, text="ok"), db)
    out = agent.respond("case-1", "do something")
    assert db.events == []          # only whitelisted actions are dispatched
    assert out["answer"] == "ok"

"""AIQ-1414 Phase 2b-ii — unit tests for the single-turn coordinator.

DB- and network-free: the LLM client, tracer, and store are faked. Focus is on the
flag gate, PII masking before egress, telemetry, and the summary fold.
"""

from backend.app.services import coordinator_agent as agent
from backend.app.services import coordinator_session_store as store


class _FakeClient:
    def __init__(self, text="OK answer"):
        self.requests = []
        self._text = text

    def complete(self, req):
        self.requests.append(req)
        return {"text": self._text, "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 100, "output_tokens": 20}}


class _FakeTracer:
    instances = []

    def __init__(self, **kw):
        self.kw = kw
        self.calls = []
        self.flushed = False
        _FakeTracer.instances.append(self)

    def record_llm_call(self, **kw):
        self.calls.append(kw)

    def flush(self):
        self.flushed = True


def _ctx(company="acme"):
    return {"case": {"company_id": company}, "_meta": {}, "people": [], "documents": [],
            "requirements": [], "recent_events": []}


def test_respond_none_when_flag_off(monkeypatch):
    monkeypatch.setattr(agent, "coordinator_enabled", lambda **_: False)
    monkeypatch.setattr(agent, "get_default_client",
                        lambda: (_ for _ in ()).throw(AssertionError("no LLM when flag off")))
    assert agent.respond("c-1", "hello") is None


def test_respond_masks_user_message_before_egress(monkeypatch):
    fake = _FakeClient()
    _FakeTracer.instances = []
    monkeypatch.setattr(agent, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(agent, "build_coordinator_context_for_case", lambda *_a, **_k: _ctx())
    monkeypatch.setattr(agent.store, "get_or_create",
                        lambda *_a, **_k: {"id": "s-1", "model": "claude-sonnet-4-6",
                                           "rolling_summary": "", "recent_turns": []})
    monkeypatch.setattr(agent, "get_default_client", lambda: fake)
    monkeypatch.setattr(agent, "TraceSession", _FakeTracer)
    captured = {}
    monkeypatch.setattr(agent, "_persist_turn",
                        lambda cid, s, mu, ans, ctx, **_k: captured.update(masked_user=mu, answer=ans))

    out = agent.respond("c-1", "my email is sarah.chen@acme.com, help with my visa")

    assert out["answer"] == "OK answer"
    # the raw email must NOT reach the LLM payload
    sent = fake.requests[0].user_message
    assert "sarah.chen@acme.com" not in sent
    assert "NEW MESSAGE:" in sent
    # nor the persisted turn
    assert "sarah.chen@acme.com" not in captured["masked_user"]
    # telemetry recorded + flushed
    tracer = _FakeTracer.instances[-1]
    assert tracer.calls[0]["input_tokens"] == 100
    assert tracer.calls[0]["output_tokens"] == 20
    assert tracer.kw["feature_key"] == "ai_coordinator"
    assert tracer.flushed is True


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeEngine:
    def begin(self):
        return _FakeConn()


class _FakeDB:
    engine = _FakeEngine()


def test_persist_turn_folds_when_window_overflows(monkeypatch):
    # session already at the window limit → appending one more turn overflows it
    session = {"id": "s-1", "rolling_summary": "prior",
               "recent_turns": [{"user": f"u{i}", "assistant": f"a{i}"}
                                for i in range(store.MAX_RECENT_TURNS)]}
    saved = {}
    monkeypatch.setattr(agent.store, "_get_db", lambda: _FakeDB())
    monkeypatch.setattr(agent.store, "load_for_update", lambda _conn, _cid: session)
    monkeypatch.setattr(agent.store, "save", lambda _conn, s: saved.update(s))
    fold_client = _FakeClient(text="FOLDED SUMMARY")
    monkeypatch.setattr(agent, "get_default_client", lambda: fold_client)

    agent._persist_turn("c-1", session, "new-user", "new-answer",
                        {"recent_events": [{"at": "2026-07-04T00:00:00+00:00"}]})

    assert saved["rolling_summary"] == "FOLDED SUMMARY"
    assert len(saved["recent_turns"]) == agent._KEEP_AFTER_FOLD
    assert saved["last_event_cursor"] == "2026-07-04T00:00:00+00:00"


def test_persist_turn_no_fold_under_window(monkeypatch):
    session = {"id": "s-1", "rolling_summary": "keep", "recent_turns": []}
    saved = {}
    monkeypatch.setattr(agent.store, "_get_db", lambda: _FakeDB())
    monkeypatch.setattr(agent.store, "load_for_update", lambda _conn, _cid: session)
    monkeypatch.setattr(agent.store, "save", lambda _conn, s: saved.update(s))
    monkeypatch.setattr(agent, "get_default_client",
                        lambda: (_ for _ in ()).throw(AssertionError("no fold under window")))

    agent._persist_turn("c-1", session, "u", "a", {"recent_events": []})

    assert saved["rolling_summary"] == "keep"
    assert saved["recent_turns"] == [{"user": "u", "assistant": "a"}]

"""AIQ-1414 Phase 3b — unit tests for the coordinator cost circuit-breaker.

DB- and network-free: the spend reader and LLM client are faked. Verifies the
per-relocation monthly cap downgrades routine turns to Haiku, that the downgrade is
persisted, and that the meter fails open (never blocks a turn).
"""

from backend.app.services import ai_unit_economics as econ
from backend.app.services import coordinator_agent as agent

SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5"


# ── _breaker_model ────────────────────────────────────────────────────────────


def test_breaker_downgrades_when_over_cap(monkeypatch):
    monkeypatch.setenv(agent._MONTHLY_CAP_ENV, "2.0")
    monkeypatch.setattr(econ, "relocation_feature_spend_usd", lambda *a, **k: 2.5)
    assert agent._breaker_model("case-1", SONNET) == HAIKU


def test_breaker_stays_under_cap(monkeypatch):
    monkeypatch.setenv(agent._MONTHLY_CAP_ENV, "2.0")
    monkeypatch.setattr(econ, "relocation_feature_spend_usd", lambda *a, **k: 0.5)
    assert agent._breaker_model("case-1", SONNET) == SONNET


def test_breaker_noops_when_already_haiku(monkeypatch):
    # Already downgraded → return Haiku without even reading the meter.
    def _boom(*a, **k):
        raise AssertionError("should not read the meter when already downgraded")

    monkeypatch.setattr(econ, "relocation_feature_spend_usd", _boom)
    assert agent._breaker_model("case-1", HAIKU) == HAIKU


def test_breaker_disabled_when_cap_zero(monkeypatch):
    monkeypatch.setenv(agent._MONTHLY_CAP_ENV, "0")
    monkeypatch.setattr(econ, "relocation_feature_spend_usd", lambda *a, **k: 999.0)
    assert agent._breaker_model("case-1", SONNET) == SONNET


def test_breaker_fails_open_on_read_error(monkeypatch):
    monkeypatch.setenv(agent._MONTHLY_CAP_ENV, "2.0")

    def _raise(*a, **k):
        raise RuntimeError("meter down")

    monkeypatch.setattr(econ, "relocation_feature_spend_usd", _raise)
    assert agent._breaker_model("case-1", SONNET) == SONNET


# ── respond() wires the effective model + persists the downgrade ───────────────


class _FakeClient:
    def __init__(self):
        self.requests = []

    def complete(self, req):
        self.requests.append(req)
        return {"text": "ok", "model": req.model, "usage": {"input_tokens": 5, "output_tokens": 2}}


class _FakeTracer:
    def __init__(self, **kw):
        pass

    def record_llm_call(self, **kw):
        pass

    def flush(self):
        pass


def _ctx(company="acme"):
    return {"case": {"company_id": company}, "_meta": {}, "people": [], "documents": [],
            "requirements": [], "recent_events": []}


def test_respond_uses_and_persists_downgraded_model(monkeypatch):
    fake = _FakeClient()
    persisted = {}
    monkeypatch.setattr(agent, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(agent, "build_coordinator_context_for_case", lambda *_a, **_k: _ctx())
    monkeypatch.setattr(agent.store, "get_or_create",
                        lambda *_a, **_k: {"id": "s-1", "model": SONNET,
                                           "rolling_summary": "", "recent_turns": []})
    monkeypatch.setattr(agent, "get_default_client", lambda: fake)
    monkeypatch.setattr(agent, "TraceSession", _FakeTracer)
    monkeypatch.setattr(agent, "_breaker_model", lambda *_a, **_k: HAIKU)
    monkeypatch.setattr(agent, "_persist_turn",
                        lambda *a, **k: persisted.update(model=k.get("model")))

    out = agent.respond("case-1", "how's my move going?")
    assert out["model"] == HAIKU               # returned model reflects the downgrade
    assert fake.requests[0].model == HAIKU      # the LLM call used Haiku
    assert persisted["model"] == HAIKU          # the downgrade was threaded to persistence


def test_persist_turn_writes_model_to_session(monkeypatch):
    saved = {}

    class _Conn:
        pass

    class _Eng:
        def begin(self):
            import contextlib

            @contextlib.contextmanager
            def _cm():
                yield _Conn()
            return _cm()

    class _DB:
        engine = _Eng()

    monkeypatch.setattr(agent.store, "_get_db", lambda: _DB())
    monkeypatch.setattr(agent.store, "load_for_update",
                        lambda conn, cid: {"id": "s-1", "model": SONNET, "recent_turns": []})
    monkeypatch.setattr(agent.store, "needs_fold", lambda s: False)
    monkeypatch.setattr(agent.store, "save", lambda conn, s: saved.update(s))

    agent._persist_turn("case-1", {}, "u", "a", _ctx(), model=HAIKU)
    assert saved["model"] == HAIKU


# ── relocation_feature_spend_usd ───────────────────────────────────────────────


class _FakeSession:
    def __init__(self, total):
        self._total = total
        self.params = None

    def execute(self, sql, params):
        self.params = params

        class _R:
            def fetchone(_self):
                return (self_outer._total,)
        self_outer = self
        return _R()


def test_relocation_spend_sums_and_scopes(monkeypatch):
    s = _FakeSession(1.2345)
    val = econ.relocation_feature_spend_usd("case-9", feature_key="ai_coordinator", session=s)
    assert val == 1.2345
    assert s.params["sid"] == "case-9"
    assert s.params["fk"] == "ai_coordinator"
    assert s.params["ms"].endswith("-01")  # date-only month start


def test_relocation_spend_fails_soft(monkeypatch):
    class _Bad:
        def execute(self, *a, **k):
            raise RuntimeError("db down")

    assert econ.relocation_feature_spend_usd("c", feature_key="ai_coordinator", session=_Bad()) == 0.0

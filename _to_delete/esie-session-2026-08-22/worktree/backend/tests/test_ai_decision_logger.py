"""AIQ-1694·3 — production-time AI-recommendation audit write helper.

Pins the compliance-load-bearing behaviour without a real DB:
  * input PII is masked BEFORE the write (raw values never reach input_context),
  * the write is a `decision='produced'` row linking masked-input + ai_output,
  * a DB failure is swallowed (never fails the recommendation request).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import json

from backend.app.services.ai_decision_logger import mask_input_context, record_ai_recommendation

# Raw PII that must never survive masking.
PII_SAMPLES = ["+33612345678", "jean.dupont@acme.com", "FR7630006000011234567890189"]


def test_mask_input_context_masks_every_string_leaf():
    masked = mask_input_context(
        {"origin_phone": "+33612345678", "contact": {"email": "jean.dupont@acme.com"},
         "docs": ["IBAN FR7630006000011234567890189"], "budget": 45000, "flag": True}
    )
    blob = json.dumps(masked)
    for raw in PII_SAMPLES:
        assert raw not in blob, f"raw PII leaked through masking: {raw}"
    assert masked["budget"] == 45000  # non-strings pass through untouched
    assert masked["flag"] is True


# ── fake DB capturing the write, so we assert the row params without a real PG ──
class _FakeConn:
    def __init__(self, cap):
        self._cap = cap

    def execute(self, sql, params=None):
        self._cap["sql"] = str(sql)
        self._cap["params"] = params


class _FakeBegin:
    def __init__(self, cap):
        self._cap = cap

    def __enter__(self):
        return _FakeConn(self._cap)

    def __exit__(self, *_a):
        return False


class _FakeEngine:
    def __init__(self, cap):
        self._cap = cap

    def begin(self):
        return _FakeBegin(self._cap)


class _FakeDB:
    def __init__(self, cap):
        self.engine = _FakeEngine(cap)


def test_writes_produced_row_with_masked_input(monkeypatch):
    cap: dict = {}
    import backend.database as bdb
    monkeypatch.setattr(bdb, "db", _FakeDB(cap), raising=False)

    rid = record_ai_recommendation(
        feature="supplier_reco:movers",
        recommendation_id="rec-1",
        input_context={"origin": "+33612345678", "picks_note": "call jean.dupont@acme.com"},
        ai_output={"picks": ["m1", "m2"]},
        company_id="co-a",
        model_name="rule-based",
    )

    assert rid, "should return the new row id"
    p = cap["params"]
    assert p["decision"] == "produced"                      # production-time state
    assert p["feature"] == "supplier_reco:movers"
    assert p["company"] == "co-a"
    assert p["model_name"] == "rule-based"
    assert json.loads(p["ai_output"]) == {"picks": ["m1", "m2"]}   # links the output
    for raw in ("+33612345678", "jean.dupont@acme.com"):    # input masked before write
        assert raw not in p["input_context"], f"raw PII in input_context: {raw}"


def test_stable_recommendation_id_is_deterministic_and_result_sensitive():
    from backend.app.services.ai_decision_logger import stable_recommendation_id
    a = stable_recommendation_id("co-a", "movers", "m1", "m2")
    b = stable_recommendation_id("co-a", "movers", "m1", "m2")
    c = stable_recommendation_id("co-a", "movers", "m1", "m3")  # different picks
    assert a == b            # same inputs → same id (re-computes dedup)
    assert a != c            # changed result → new id (logged fresh)
    assert len(a) == 40 and all(ch in "0123456789abcdef" for ch in a)


class _DedupConn:
    """execute() returns a result whose .first() reflects whether a row 'exists'."""
    def __init__(self, cap, exists):
        self._cap = cap
        self._exists = exists

    def execute(self, sql, params=None):
        s = str(sql)
        self._cap.setdefault("sqls", []).append(s)
        if s.strip().upper().startswith("SELECT"):
            class _R:
                def __init__(self, hit):
                    self._hit = hit
                def first(self):
                    return (1,) if self._hit else None
            return _R(self._exists)
        self._cap["insert_params"] = params  # the INSERT
        return None


class _DedupDB:
    def __init__(self, cap, exists):
        self._cap, self._exists = cap, exists

    class _Engine:
        def __init__(self, outer): self._o = outer
        def begin(self):
            outer = self._o
            class _Ctx:
                def __enter__(_s): return _DedupConn(outer._cap, outer._exists)
                def __exit__(_s, *a): return False
            return _Ctx()

    @property
    def engine(self):
        return _DedupDB._Engine(self)


def test_skip_if_exists_dedups_a_repeat_produced_row(monkeypatch):
    import backend.database as bdb
    cap: dict = {}
    monkeypatch.setattr(bdb, "db", _DedupDB(cap, exists=True), raising=False)
    rid = record_ai_recommendation(
        feature="supplier_reco:movers", recommendation_id="stable-1",
        input_context={"a": "x"}, ai_output={}, company_id="co-a", skip_if_exists=True,
    )
    assert rid is None                         # a 'produced' row already exists → skip
    assert "insert_params" not in cap          # and NO insert was issued


def test_skip_if_exists_inserts_when_absent(monkeypatch):
    import backend.database as bdb
    cap: dict = {}
    monkeypatch.setattr(bdb, "db", _DedupDB(cap, exists=False), raising=False)
    rid = record_ai_recommendation(
        feature="supplier_reco:movers", recommendation_id="stable-1",
        input_context={"phone": "+33612345678"}, ai_output={"picks": ["m1"]},
        company_id="co-a", skip_if_exists=True,
    )
    assert rid                                 # no existing row → inserted
    assert cap["insert_params"]["decision"] == "produced"
    assert "+33612345678" not in cap["insert_params"]["input_context"]  # still masked


def test_fail_open_returns_none_and_does_not_raise(monkeypatch):
    class _Boom:
        @property
        def engine(self):
            raise RuntimeError("db down")

    import backend.database as bdb
    monkeypatch.setattr(bdb, "db", _Boom(), raising=False)

    rid = record_ai_recommendation(
        feature="f", recommendation_id="r",
        input_context={"a": "x"}, ai_output={}, company_id=None,
    )
    assert rid is None  # swallowed, caller unaffected

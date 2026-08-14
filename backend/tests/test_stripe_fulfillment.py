"""Unit tests for the Stripe fulfilment brain (portable-webhook spec §3 + §8).

These pin the *control flow* — which branch, what return contract, commit vs
rollback — with a fake DB session. The SQL itself (columns, `id::text`, ON CONFLICT)
is validated separately against the real Postgres schema via a rollback transaction,
because SQLite (the conftest default) does not share `::text` / `now()` semantics.

The verifiable success criteria map to the spec §8 test plan:
  test_applies_...            → #1 tier flip + stripe_events row
  test_duplicate_...          → #2 replay is a no-op, tier unchanged
  test_ignored_unknown_type   → #4 unknown event type
  test_ignored_missing_case_id→ #5 missing metadata.case_id, no crash
"""
from __future__ import annotations

from backend.app.services.stripe_fulfillment import fulfil_stripe_event


class _Result:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class FakeDb:
    """Records executed SQL and returns a scripted rowcount per statement kind.

    `insert_rowcount`: what the `INSERT INTO stripe_events ... ON CONFLICT` returns
    (1 = newly inserted, 0 = duplicate). `update_case_rowcount`: what the
    `UPDATE relocation_cases` returns (1 = case found, 0 = unknown case).
    """
    def __init__(self, *, insert_rowcount: int = 1, update_case_rowcount: int = 1):
        self.insert_rowcount = insert_rowcount
        self.update_case_rowcount = update_case_rowcount
        self.executed: list[tuple[str, dict]] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params or {}))
        if "INSERT INTO stripe_events" in sql:
            return _Result(self.insert_rowcount)
        if "UPDATE relocation_cases" in sql:
            return _Result(self.update_case_rowcount)
        return _Result(1)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    # convenience for assertions
    def sql_joined(self) -> str:
        return "\n".join(s for s, _ in self.executed)


def _event(event_type="checkout.session.completed", *, event_id="evt_1",
           metadata=None, session_extra=None):
    session = {"id": "cs_test_1", "amount_total": 80000, "currency": "eur",
               "payment_intent": "pi_1", "metadata": metadata if metadata is not None else {}}
    session.update(session_extra or {})
    return {"id": event_id, "type": event_type, "data": {"object": session}}


def test_applies_tier_flip_and_writes_event_row():
    db = FakeDb()
    ev = _event(metadata={"case_id": "11111111-1111-1111-1111-111111111111", "tier": "roadmap"})
    out = fulfil_stripe_event(db, ev)

    assert out == {"status": "applied",
                   "case_id": "11111111-1111-1111-1111-111111111111",
                   "tier": "roadmap"}
    assert db.committed and not db.rolled_back
    # idempotency insert happened before the tier flip
    joined = db.sql_joined()
    assert joined.index("INSERT INTO stripe_events") < joined.index("UPDATE relocation_cases")
    # the flip carried the mapped tier + payment_status and the money fields
    _, upd_params = next((s, p) for s, p in db.executed if "UPDATE relocation_cases" in s)
    assert upd_params["access_tier"] == "roadmap"
    assert upd_params["payment_status"] == "roadmap_paid"
    assert upd_params["amount_cents"] == 80000
    assert upd_params["case_id"] == "11111111-1111-1111-1111-111111111111"


def test_essentials_tier_maps_to_essentials_paid():
    db = FakeDb()
    out = fulfil_stripe_event(db, _event(metadata={"case_id": "c-2", "tier": "essentials"}))
    assert out["status"] == "applied" and out["tier"] == "essentials"
    _, upd = next((s, p) for s, p in db.executed if "UPDATE relocation_cases" in s)
    assert upd["payment_status"] == "essentials_paid"


def test_duplicate_event_is_a_noop():
    # Second delivery of the same event: the INSERT conflicts (rowcount 0).
    db = FakeDb(insert_rowcount=0)
    out = fulfil_stripe_event(db, _event(metadata={"case_id": "c-1", "tier": "roadmap"}))
    assert out == {"status": "duplicate", "event_id": "evt_1"}
    assert db.rolled_back and not db.committed
    # no tier flip on a duplicate
    assert "UPDATE relocation_cases" not in db.sql_joined()


def test_ignored_unknown_event_type():
    db = FakeDb()
    out = fulfil_stripe_event(db, _event(event_type="payment_intent.succeeded"))
    assert out["status"] == "ignored" and out["reason"] == "unhandled_event_type"
    # recorded (committed) but never touched a case
    assert db.committed
    assert "UPDATE relocation_cases" not in db.sql_joined()
    assert "status='ignored'" in db.sql_joined()


def test_ignored_missing_case_id_does_not_crash():
    db = FakeDb()
    out = fulfil_stripe_event(db, _event(metadata={"tier": "roadmap"}))  # no case_id
    assert out["status"] == "ignored" and out["reason"] == "missing_case_id"
    assert db.rolled_back
    assert "UPDATE relocation_cases" not in db.sql_joined()


def test_ignored_unknown_tier():
    db = FakeDb()
    out = fulfil_stripe_event(db, _event(metadata={"case_id": "c-1", "tier": "premium"}))
    assert out["status"] == "ignored" and out["reason"] == "unknown_tier"
    assert db.rolled_back
    assert "UPDATE relocation_cases" not in db.sql_joined()


def test_ignored_unknown_case():
    # Valid event, but the case_id matches no row (UPDATE rowcount 0).
    db = FakeDb(update_case_rowcount=0)
    out = fulfil_stripe_event(db, _event(metadata={"case_id": "c-missing", "tier": "roadmap"}))
    assert out["status"] == "ignored" and out["reason"] == "unknown_case"
    assert db.rolled_back and not db.committed


def test_ignored_missing_event_id():
    db = FakeDb()
    out = fulfil_stripe_event(db, _event(event_id="", metadata={"case_id": "c", "tier": "roadmap"}))
    assert out["status"] == "ignored" and out["reason"] == "missing_event_id"
    # never attempted an idempotency insert without an id to guard on
    assert "INSERT INTO stripe_events" not in db.sql_joined()

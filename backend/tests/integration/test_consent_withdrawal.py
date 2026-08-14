"""[AIQ-1803] Withdrawing immigration consent must actually stop processing.

WHY THIS EXISTS
---------------
`consent_records` is an append-only GDPR ledger. A trigger enforces it, and the trigger's
own error message states the contract:

    consent_records is append-only. Withdrawals must be inserted as new rows
    (consented=false), not updates or deletes.

Verified against production 2026-08-11 — `BEFORE DELETE OR UPDATE ... FOR EACH ROW`, and the
function body raises unconditionally with no branch. Two code paths disagreed with it, and
between them there was **no working way to withdraw consent**:

1. `withdraw_consent_employee` issued an UPDATE. The trigger blocks UPDATE, so the endpoint
   raised for every caller. Its `affected == 0` → 404 branch and its `records_withdrawn`
   count were unreachable in production.

2. `_check_consent` put `consented = TRUE AND withdrawn_at IS NULL` in the WHERE clause and
   *then* `ORDER BY created_at DESC LIMIT 1`. The filter prunes before the ordering picks, so
   the ORDER BY was decorative — the query answered "has any grant ever existed?", not "what
   is the current state?". Append the withdrawal row the trigger demands and the older grant
   row still matched, so processing continued.

So the only mechanism the schema allows was the one the consent check ignored. Measured on
live production data the same day, on a real grant+withdrawal pair:

    ledger                 [{consented: true, withdrawn: false},
                            {consented: false, withdrawn: true}]
    _check_consent's query  -> 1 row  -> ACCESS GRANTED
    latest-row logic        -> false  -> access denied

That is GDPR Art. 7(3) ("it shall be as easy to withdraw consent as to give it") failing
open, and it stopped being hypothetical the moment `IMMIGRATION_ENCRYPTION_KEY` went live
(AIQ-1800) and the profile table began holding Article 9 passport data.

Three endpoints already had the correct shape and are the reference for the fix:
`outcome_extractor.has_outcome_consent`, `outcome_consent.get_outcome_consent`, and
`immigration_intake_consent.list_consent_employee` (via `DISTINCT ON`). The last one is why
this was observable at all: the employee's own privacy screen showed *withdrawn* while the
backend kept processing.

WHAT IS PINNED HERE
-------------------
- The table really does reject UPDATE and DELETE (if that ever stops being true, the fix
  below is solving a problem that no longer exists — fail loudly rather than silently).
- `_check_consent` honours a withdrawal row.
- It still grants on a plain grant, and on a re-grant after a withdrawal. Latest-row
  semantics must not lock a user out of consenting again.
- The old query shape is kept as an executable characterisation of the bug, so a future
  reader can see *why* filter-before-order is wrong rather than taking it on faith.

RUNNING — use a throwaway local Postgres, not production
--------------------------------------------------------
`integration`-marked, so CI's `-m "not integration"` run skips it.

    docker run -d --name consentpg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=consenttest \
      -p 55434:5432 postgres:15-alpine

    DATABASE_URL=postgresql://postgres:test@127.0.0.1:55434/consenttest \
      pytest backend/tests/integration/test_consent_withdrawal.py -v

The schema and the trigger are created by the fixture below, mirroring
`supabase/migrations/20260518120000_immigration_core_tables.sql` — including
`consent_version` and `consent_text_hash` being NOT NULL, which is what forces the fix to
carry them onto the withdrawal row instead of inserting a bare marker.
"""
from __future__ import annotations

import os
import uuid

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import DatabaseError  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = DATABASE_URL.startswith("postgres")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _IS_PG,
        reason="needs a Postgres DATABASE_URL — this is a trigger-and-ordering bug, and a "
        "mocked or sqlite database cannot see either half.",
    ),
]

PURPOSE = "immigration_processing"

#: Mirrors the production DDL closely enough to reproduce both halves: the NOT NULLs that
#: constrain what a withdrawal row may contain, and the trigger that blocks UPDATE/DELETE.
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS public.consent_records (
  id                text PRIMARY KEY DEFAULT (gen_random_uuid())::text,
  employee_id       text NOT NULL,
  case_id           text NOT NULL,
  purpose           text NOT NULL,
  consented         boolean NOT NULL,
  consent_version   text NOT NULL,
  consent_text_hash text NOT NULL,
  consented_at      timestamptz,
  withdrawn_at      timestamptz,
  withdrawn_reason  text,
  ip_address        text,
  user_agent        text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.fn_consent_records_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION
    'consent_records is append-only. Withdrawals must be inserted as new rows '
    '(consented=false), not updates or deletes. Operation % on row % is not permitted.',
    TG_OP, OLD.id;
END;
$$;

DROP TRIGGER IF EXISTS trg_consent_records_immutable ON public.consent_records;
CREATE TRIGGER trg_consent_records_immutable
  BEFORE UPDATE OR DELETE ON public.consent_records
  FOR EACH ROW EXECUTE FUNCTION public.fn_consent_records_immutable();
"""


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(DATABASE_URL, future=True)
    # Raw DBAPI cursor rather than conn.execute(): this is a multi-statement DDL script
    # containing a $$-quoted function body. SQLAlchemy's exec_driver_sql passes an empty
    # immutabledict as parameters, which psycopg2 rejects ("not a sequence").
    raw = eng.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        cur.execute(SCHEMA_DDL)
        raw.commit()
    finally:
        raw.close()
    yield eng
    eng.dispose()


@pytest.fixture
def ids():
    """A fresh case+employee pair per test, so tests cannot see each other's ledger."""
    return {"case_id": f"case-{uuid.uuid4()}", "employee_id": f"emp-{uuid.uuid4()}"}


def _insert(conn, *, case_id, employee_id, consented, withdrawn, seq=None):
    """Append one ledger row.

    `seq` orders rows that share a transaction: `now()` is transaction-start time, so every
    statement in one transaction sees the SAME value and `ORDER BY created_at DESC` would be
    a coin toss. Sequenced rows are placed in the PAST (`now() - (60 - seq)` seconds), never
    the future — a future timestamp cannot be superseded by a later real-time insert, which
    is a trap that made an earlier version of this file fail for the wrong reason.

    `seq=None` uses real `now()`. Rows written in separate transactions are ordered by the
    clock already, so that is the right choice whenever the endpoint under test is what
    writes the next row.
    """
    created = "now()" if seq is None else "now() - make_interval(secs => 60 - :seq)"
    params = {
        "eid": employee_id,
        "cid": case_id,
        "purpose": PURPOSE,
        "consented": consented,
        "withdrawn": withdrawn,
    }
    if seq is not None:
        params["seq"] = seq
    conn.execute(
        text(
            f"""
            INSERT INTO public.consent_records
                (employee_id, case_id, purpose, consented, consent_version,
                 consent_text_hash, consented_at, withdrawn_at, created_at)
            VALUES
                (:eid, :cid, :purpose, :consented, 'v-test', 'hash-test',
                 CASE WHEN :consented THEN now() ELSE NULL END,
                 CASE WHEN :withdrawn THEN now() ELSE NULL END,
                 {created})
            """
        ),
        params,
    )


def _grant(conn, ids, *, seq=None):
    _insert(conn, **ids, consented=True, withdrawn=False, seq=seq)


def _withdraw(conn, ids, *, seq=None):
    _insert(conn, **ids, consented=False, withdrawn=True, seq=seq)


def _check_consent_under_test(engine, ids, monkeypatch) -> bool:
    """Call the REAL production function against this test database.

    Testing a hand-copy of the query would prove only that my copy is correct. The whole
    class of bug here is that the shipped query disagrees with the schema, so the shipped
    query is what has to run.
    """
    from backend import database as database_module
    from backend.app.services import immigration_service

    monkeypatch.setattr(database_module.db, "engine", engine, raising=False)
    return immigration_service._check_consent(ids["case_id"], ids["employee_id"])


# ── the append-only contract itself ──────────────────────────────────────────────────

def test_update_is_rejected(engine, ids):
    """The mechanism behind defect 1a. If this ever passes, the withdraw endpoint could go
    back to an UPDATE — and this test failing is how you would find that out."""
    with engine.begin() as conn:
        _grant(conn, ids)

    with pytest.raises(DatabaseError) as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.consent_records SET consented = FALSE, withdrawn_at = now() "
                    "WHERE case_id = :cid AND employee_id = :eid AND withdrawn_at IS NULL"
                ),
                {"cid": ids["case_id"], "eid": ids["employee_id"]},
            )
    assert "append-only" in str(exc.value)


def test_delete_is_rejected(engine, ids):
    with engine.begin() as conn:
        _grant(conn, ids)

    with pytest.raises(DatabaseError) as exc:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.consent_records WHERE case_id = :cid"),
                {"cid": ids["case_id"]},
            )
    assert "append-only" in str(exc.value)


def test_appending_a_withdrawal_row_is_allowed(engine, ids):
    """The one mutation the schema does permit — and therefore the only shape the withdraw
    endpoint can legally take."""
    with engine.begin() as conn:
        _grant(conn, ids, seq=0)
        _withdraw(conn, ids, seq=1)
        n = conn.execute(
            text("SELECT count(*) FROM public.consent_records WHERE case_id = :cid"),
            {"cid": ids["case_id"]},
        ).scalar()
    assert n == 2, "both the grant and its withdrawal must survive as ledger history"


# ── the consent check ────────────────────────────────────────────────────────────────

def test_check_consent_honours_a_withdrawal_row(engine, ids, monkeypatch):
    """THE BUG. Grant, then withdraw the way the trigger demands. Access must stop.

    Before the fix this returned True: the WHERE clause filtered the withdrawal row out of
    the candidate set and the surviving grant row satisfied the query.
    """
    with engine.begin() as conn:
        _grant(conn, ids, seq=0)
        _withdraw(conn, ids, seq=1)

    assert _check_consent_under_test(engine, ids, monkeypatch) is False, (
        "consent was withdrawn via the only mechanism the schema allows, and the consent "
        "check still authorised processing — GDPR Art. 7(3) failing open"
    )


def test_check_consent_grants_on_a_plain_grant(engine, ids, monkeypatch):
    """Non-regression: the fix must not deny consent that was never withdrawn."""
    with engine.begin() as conn:
        _grant(conn, ids)

    assert _check_consent_under_test(engine, ids, monkeypatch) is True


def test_check_consent_allows_a_regrant_after_withdrawal(engine, ids, monkeypatch):
    """Latest-row semantics must let someone consent again.

    A naive fix — "deny if any withdrawal row exists" — passes the bug test above and
    permanently locks the user out. That is a different Art. 7 problem, so it is pinned here.
    """
    with engine.begin() as conn:
        _grant(conn, ids, seq=0)
        _withdraw(conn, ids, seq=1)
        _grant(conn, ids, seq=2)

    assert _check_consent_under_test(engine, ids, monkeypatch) is True


def test_check_consent_denies_when_no_record_exists(engine, ids, monkeypatch):
    assert _check_consent_under_test(engine, ids, monkeypatch) is False


# ── the endpoint, end to end ─────────────────────────────────────────────────────────

def _call_withdraw(engine, ids, monkeypatch, *, purpose=PURPOSE):
    """Invoke the REAL withdraw endpoint against this database.

    `Depends(...)` defaults are ordinary Python default arguments, so the undecorated
    function can be called directly with `current_user` supplied. Audit and access logging
    are stubbed — they write to tables outside this test's schema, and the ledger is what is
    under test.
    """
    from backend import database as database_module
    from backend.app.routers import immigration_intake_consent as router_mod

    monkeypatch.setattr(database_module.db, "engine", engine, raising=False)
    monkeypatch.setattr(router_mod, "insert_audit_log", lambda *a, **k: None)
    monkeypatch.setattr(router_mod, "_log_access", lambda *a, **k: None)

    body = router_mod.WithdrawConsentBody(purpose=purpose, reason="test withdrawal")
    return router_mod.withdraw_consent_employee(
        case_id=ids["case_id"],
        body=body,
        current_user={"id": ids["employee_id"]},
    )


def test_withdraw_endpoint_succeeds_and_stops_processing(engine, ids, monkeypatch):
    """The whole point, in one test: an employee withdraws, and processing stops.

    Before the fix this raised — the endpoint issued an UPDATE against an append-only
    table — so there was no way for a user to exercise Art. 7(3) at all.
    """
    with engine.begin() as conn:
        _grant(conn, ids)
    assert _check_consent_under_test(engine, ids, monkeypatch) is True

    result = _call_withdraw(engine, ids, monkeypatch)

    assert result["withdrawn"] is True
    assert _check_consent_under_test(engine, ids, monkeypatch) is False, (
        "the endpoint reported success but the consent check still authorises processing"
    )


def test_withdraw_preserves_the_grant_row(engine, ids, monkeypatch):
    """The ledger is evidence. Withdrawing must add history, never rewrite it."""
    with engine.begin() as conn:
        _grant(conn, ids)
    _call_withdraw(engine, ids, monkeypatch)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT consented, withdrawn_at, consent_version, consent_text_hash "
                "FROM public.consent_records WHERE case_id = :cid ORDER BY created_at"
            ),
            {"cid": ids["case_id"]},
        ).mappings().all()

    assert len(rows) == 2, "the original grant must still be on record"
    assert rows[0]["consented"] is True and rows[0]["withdrawn_at"] is None
    assert rows[1]["consented"] is False and rows[1]["withdrawn_at"] is not None
    # The withdrawal must say WHICH consent text it revoked, not invent a fresh version.
    assert rows[1]["consent_version"] == rows[0]["consent_version"]
    assert rows[1]["consent_text_hash"] == rows[0]["consent_text_hash"]


def test_withdraw_404s_when_consent_is_not_held(engine, ids, monkeypatch):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _call_withdraw(engine, ids, monkeypatch)
    assert exc.value.status_code == 404


def test_withdraw_404s_on_an_already_withdrawn_purpose(engine, ids, monkeypatch):
    """Second withdrawal is a no-op, not a second ledger row — otherwise a retrying client
    could pile up withdrawal rows on a consent that was never re-granted."""
    with engine.begin() as conn:
        _grant(conn, ids)
    _call_withdraw(engine, ids, monkeypatch)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _call_withdraw(engine, ids, monkeypatch)
    assert exc.value.status_code == 404


def test_withdraw_works_again_after_a_regrant(engine, ids, monkeypatch):
    with engine.begin() as conn:
        _grant(conn, ids, seq=0)
    _call_withdraw(engine, ids, monkeypatch)
    with engine.begin() as conn:
        _grant(conn, ids)
    assert _check_consent_under_test(engine, ids, monkeypatch) is True

    _call_withdraw(engine, ids, monkeypatch)
    assert _check_consent_under_test(engine, ids, monkeypatch) is False


# ── why the old shape was wrong, kept executable ─────────────────────────────────────

def test_filter_before_order_is_what_broke_it(engine, ids):
    """A characterisation test: run both query shapes over the same ledger.

    This is the only test here that would pass before the fix as well as after — it asserts
    a property of SQL, not of our code. It exists so the next person to touch
    `_check_consent` can see the failure mode in one place instead of reconstructing it.
    """
    with engine.begin() as conn:
        _grant(conn, ids, seq=0)
        _withdraw(conn, ids, seq=1)

        old_shape = conn.execute(
            text(
                "SELECT id FROM public.consent_records "
                "WHERE case_id = :cid AND employee_id = :eid AND purpose = :p "
                "  AND consented = TRUE AND withdrawn_at IS NULL "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": ids["case_id"], "eid": ids["employee_id"], "p": PURPOSE},
        ).first()

        new_shape = conn.execute(
            text(
                "SELECT consented AND withdrawn_at IS NULL FROM public.consent_records "
                "WHERE case_id = :cid AND employee_id = :eid AND purpose = :p "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": ids["case_id"], "eid": ids["employee_id"], "p": PURPOSE},
        ).scalar()

    assert old_shape is not None, (
        "filter-before-order returns the stale grant row — the ORDER BY only ever chose "
        "among rows that already passed the filter, so it could not see the withdrawal"
    )
    assert new_shape is False, "order-then-judge sees the withdrawal, which is the fix"

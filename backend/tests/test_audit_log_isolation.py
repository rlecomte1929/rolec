"""AIQ-1807 — a failed audit row must never discard the write it was auditing.

THE INCIDENT. `POST /api/employee/cases/{id}/consent` returned **201 with a
consent_record_id and wrote no consent row**. `audit_logs.actor_id` is uuid; the handler
passed a legacy TEXT user id; Postgres raised; the handler's `except Exception: log`
caught the Python error — but the transaction was already ABORTED, so SQLAlchemy's
commit-on-exit degraded to a rollback and took the consent row with it. The employee was
told their GDPR consent was recorded when it was not, and the consent gate then correctly
refused to proceed.

64 call sites wrap `insert_audit_log` in exactly that `try/except`, so all 64 could
silently discard their primary write. 6 more call it unwrapped and 500 instead. One
savepoint in the helper fixes every one of them.

WHAT SQLITE CAN AND CANNOT PROVE — read this before trusting a green run.

SQLite does NOT abort a transaction when a statement fails; Postgres does. That
difference IS the bug. So the SQLite cases below pass with the savepoint REMOVED, and
they must not be read as proving it. They were written that way first, and they were
wrong — the same "green on SQLite, broken on prod" shape as the incident itself.

What each layer actually gates:
  * SQLite cases (CI)          — the helper never raises, the actor is coerced, the gap
                                 is logged. Real properties, just not the transactional one.
  * TestSavepointIsUsed (CI)   — structural: the savepoint cannot be silently deleted.
  * Postgres (docker, manual)  — the real proof. Reproduced 2026-08-11 against
                                 postgres:15 with production column types:
                                     pre-fix : consent_rows=0  (write discarded)
                                     post-fix: consent_rows=1, audit_rows=1
                                 Rerun with TestOnRealPostgres by pointing DATABASE_URL
                                 at a throwaway Postgres.

WHY FAULT INJECTION. The defect passed every existing test and returned 201. Only forcing
the failure distinguishes "audit worked" from "audit failed invisibly and took the write".
"""
from __future__ import annotations

import logging
import unittest
import uuid

from sqlalchemy import create_engine, text

from backend.app.services.audit_log_service import (
    ACTION_INSERT,
    ACTOR_HUMAN,
    _as_uuid_or_none,
    insert_audit_log,
)

_UUID_ACTOR = "d2991022-61c3-40c5-a172-f139254112ee"
_TEXT_ACTOR = "seed-emp-testingapril"


def _engine():
    """In-memory SQLite with the two tables that matter, mirroring prod's shape:
    audit_logs.entity_id NOT NULL and a CHECK on action_type."""
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE audit_logs (
              id TEXT PRIMARY KEY,
              entity_type TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              action_type TEXT NOT NULL
                CHECK (action_type IN ('insert','update','delete')),
              old_value_json TEXT, new_value_json TEXT,
              actor_type TEXT, actor_id TEXT)"""))
        conn.execute(text("""
            CREATE TABLE consent_records (
              id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, case_id TEXT NOT NULL)"""))
    return eng


def _primary_write(conn, rec_id="rec-1"):
    conn.execute(
        text("INSERT INTO consent_records (id, employee_id, case_id) "
             "VALUES (:i, :e, :c)"),
        {"i": rec_id, "e": _TEXT_ACTOR, "c": "case-1"})


class TestTheWriteSurvivesAnAuditFailure(unittest.TestCase):
    """G1 — an audit failure can never discard the write it was auditing."""

    def setUp(self) -> None:
        self.eng = _engine()

    def _rows(self, table):
        with self.eng.connect() as conn:
            return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

    def test_an_invalid_action_type_does_not_roll_back_the_primary_write(self) -> None:
        """THE regression. Reproduces the incident's shape with a different trigger:
        the audit insert fails, and the consent row must still be there afterwards."""
        with self.eng.begin() as conn:
            _primary_write(conn)
            insert_audit_log(
                conn, entity_type="consent_record", entity_id=str(uuid.uuid4()),
                action_type="NOT_A_VALID_ACTION",   # violates the CHECK
                actor_type=ACTOR_HUMAN, actor_id=_UUID_ACTOR)

        self.assertEqual(self._rows("consent_records"), 1,
                         "the primary write was rolled back by a failing audit insert")
        self.assertEqual(self._rows("audit_logs"), 0, "the bad audit row must not persist")

    def test_a_null_entity_id_does_not_roll_back_the_primary_write(self) -> None:
        with self.eng.begin() as conn:
            _primary_write(conn)
            insert_audit_log(
                conn, entity_type="consent_record", entity_id=None,  # NOT NULL violation
                action_type=ACTION_INSERT, actor_type=ACTOR_HUMAN, actor_id=_UUID_ACTOR)
        self.assertEqual(self._rows("consent_records"), 1)

    def test_the_caller_can_keep_working_after_a_failed_audit(self) -> None:
        """A poisoned transaction shows up as the NEXT statement failing. If the savepoint
        did not contain it, this second write would raise."""
        with self.eng.begin() as conn:
            _primary_write(conn, "rec-1")
            insert_audit_log(conn, entity_type="x", entity_id=str(uuid.uuid4()),
                             action_type="bogus", actor_type=ACTOR_HUMAN)
            _primary_write(conn, "rec-2")     # must not raise
        self.assertEqual(self._rows("consent_records"), 2)

    def test_a_successful_audit_still_commits_both(self) -> None:
        """The fix must not achieve isolation by never writing the audit row."""
        with self.eng.begin() as conn:
            _primary_write(conn)
            insert_audit_log(conn, entity_type="consent_record",
                             entity_id=str(uuid.uuid4()), action_type=ACTION_INSERT,
                             actor_type=ACTOR_HUMAN, actor_id=_UUID_ACTOR)
        self.assertEqual(self._rows("consent_records"), 1)
        self.assertEqual(self._rows("audit_logs"), 1)


class TestAnAuditGapIsNeverSilent(unittest.TestCase):
    """G3 — soft, but LOUD. Committing a write whose audit row vanished is its own
    compliance problem, so the failure has to be visible and countable."""

    def test_the_failure_is_logged_at_error_naming_the_entity(self) -> None:
        eng = _engine()
        with self.assertLogs("backend.app.services.audit_log_service", level="ERROR") as logs:
            with eng.begin() as conn:
                _primary_write(conn)
                insert_audit_log(conn, entity_type="consent_record",
                                 entity_id="ent-42", action_type="bogus",
                                 actor_type=ACTOR_HUMAN)
        blob = "\n".join(r.getMessage() for r in logs.records)
        self.assertIn("AUDIT GAP", blob)
        self.assertIn("consent_record", blob)
        self.assertIn("ent-42", blob, "an operator must be able to find the missing action")


class TestNonUuidActorsDoNotRaise(unittest.TestCase):
    """G1/T2 — the specific trigger. 2 of 2,479 production users have TEXT ids."""

    def test_a_text_actor_id_is_coerced_to_null(self) -> None:
        self.assertIsNone(_as_uuid_or_none(_TEXT_ACTOR))
        self.assertEqual(_as_uuid_or_none(_UUID_ACTOR), _UUID_ACTOR)
        self.assertIsNone(_as_uuid_or_none(None))
        self.assertIsNone(_as_uuid_or_none(""))

    def test_the_actor_is_still_recorded_in_the_payload(self) -> None:
        """Coercing to NULL must not lose WHO acted — that would trade a crash for an
        accountability hole."""
        import json

        eng = _engine()
        with eng.begin() as conn:
            insert_audit_log(conn, entity_type="consent_record",
                             entity_id=str(uuid.uuid4()), action_type=ACTION_INSERT,
                             actor_type=ACTOR_HUMAN, actor_id=_TEXT_ACTOR,
                             new_value={"event": "consent_recorded"})
        with eng.connect() as conn:
            row = conn.execute(
                text("SELECT actor_id, new_value_json FROM audit_logs")).mappings().first()
        self.assertIsNone(row["actor_id"])
        payload = json.loads(row["new_value_json"])
        self.assertEqual(payload["actor_ref"], _TEXT_ACTOR)
        self.assertEqual(payload["event"], "consent_recorded",
                         "the original payload must be preserved alongside actor_ref")

    def test_a_uuid_actor_payload_is_left_alone(self) -> None:
        import json

        eng = _engine()
        with eng.begin() as conn:
            insert_audit_log(conn, entity_type="x", entity_id=str(uuid.uuid4()),
                             action_type=ACTION_INSERT, actor_type=ACTOR_HUMAN,
                             actor_id=_UUID_ACTOR, new_value={"event": "e"})
        with eng.connect() as conn:
            row = conn.execute(
                text("SELECT actor_id, new_value_json FROM audit_logs")).mappings().first()
        self.assertEqual(row["actor_id"], _UUID_ACTOR)
        self.assertNotIn("actor_ref", json.loads(row["new_value_json"]))


class TestThePrimaryWriteStillFailsLoudly(unittest.TestCase):
    """G2 — isolation must not be achieved by making everything succeed. If the PRIMARY
    write fails, that must still propagate."""

    def test_a_failing_primary_write_still_raises(self) -> None:
        eng = _engine()
        with self.assertRaises(Exception):
            with eng.begin() as conn:
                _primary_write(conn, "dup")
                _primary_write(conn, "dup")   # PK violation — must NOT be swallowed
        with eng.connect() as conn:
            self.assertEqual(
                conn.execute(text("SELECT COUNT(*) FROM consent_records")).scalar(), 0)


class TestSavepointIsUsed(unittest.TestCase):
    """The CI-runnable guard on the transactional property.

    SQLite cannot demonstrate that the savepoint matters, so nothing in this file would
    fail if someone deleted it — which is exactly how the original defect survived. This
    asserts it structurally instead: cheap, and it cannot be satisfied by accident.
    """

    def test_the_audit_insert_is_wrapped_in_a_savepoint(self) -> None:
        import inspect

        from backend.app.services import audit_log_service

        src = inspect.getsource(audit_log_service.insert_audit_log)
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        self.assertIn(
            "begin_nested()", code,
            "insert_audit_log must run its INSERT inside a SAVEPOINT. Without it a "
            "failed audit row aborts the CALLER's transaction, and the 64 call sites "
            "that catch the exception silently discard their primary write while "
            "returning success (AIQ-1807).",
        )

    def test_the_failure_handler_does_not_re_raise(self) -> None:
        """Soft by design — the caller's write must survive an audit failure."""
        import inspect

        from backend.app.services import audit_log_service

        src = inspect.getsource(audit_log_service.insert_audit_log)
        self.assertIn("except Exception:", src)
        self.assertNotIn("raise", src.split("except Exception:")[-1])


@unittest.skipUnless(
    __import__("os").environ.get("DATABASE_URL", "").startswith("postgres"),
    "needs a throwaway Postgres — the transactional property cannot be shown on SQLite",
)
class TestOnRealPostgres(unittest.TestCase):
    """The real proof. Point DATABASE_URL at a disposable Postgres to run it.

    Deliberately NOT `integration`-marked: this file already runs in CI, and an
    integration mark plus a SQLite CI lane is how a test ends up never executing.
    The skipUnless is honest about why it did not run.
    """

    def test_a_failed_audit_does_not_discard_the_primary_write(self) -> None:
        import os

        eng = create_engine(os.environ["DATABASE_URL"])
        suffix = uuid.uuid4().hex[:8]
        tbl = f"aiq1807_probe_{suffix}"
        with eng.begin() as conn:
            conn.execute(text(f"CREATE TABLE {tbl} (id text PRIMARY KEY)"))
        try:
            with eng.begin() as conn:
                conn.execute(text(f"INSERT INTO {tbl} (id) VALUES ('keep-me')"))
                insert_audit_log(conn, entity_type="probe", entity_id=str(uuid.uuid4()),
                                 action_type="bogus",  # violates the CHECK on Postgres
                                 actor_type=ACTOR_HUMAN, actor_id=_TEXT_ACTOR)
            with eng.connect() as conn:
                kept = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            self.assertEqual(kept, 1, "the primary write was discarded by a failed audit")
        finally:
            with eng.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig()
    unittest.main()

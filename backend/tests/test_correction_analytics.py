"""Tests for AIQ-554 / C2-03 — reason-code taxonomy lock-in + correction analytics.

Mirrors test_ai_decisions_router.py: an in-memory SQLite engine with the
rce.corrections + rce.cases schemas preloaded, the analytics service / router
functions called directly (bypasses FastAPI DI so the test stays decoupled from
the rest of the wiring).

SQLite adaptations (applied via a before_cursor_execute shim so the *production*
SQL string is exercised unchanged):

  * ``date_trunc('week', col)`` → a Monday-of-week date expression. SQLite's
    ``date(col, 'weekday 0', '-6 days')`` returns the Monday of col's week.
  * ``CAST(:x AS uuid)`` → ``:x`` (SQLite has no uuid type).
  * ``col->>'key'`` → ``json_extract(col, '$.key')`` (SQLite JSON1).

Validation criteria covered here:
  2. Backfill migration sets reason_code='OTHER' for NULL rows; idempotent.
  3. /admin/corrections/by-reason returns weekly bucket + total counts, 3-way grouped.
  4. The CHECK enum still has exactly the 6 values (lock-in / drift guard).
  5. Digest summary renders for a 0-correction week and a mixed-reason week.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import create_engine, event, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import correction_analytics as svc  # noqa: E402
from backend.app.routers import admin_corrections as router_module  # noqa: E402
from backend.app.routers.admin_corrections import corrections_by_reason  # noqa: E402
from fastapi import HTTPException  # noqa: E402


# ---------------------------------------------------------------------------
# Migration enum lock-in (criterion 4) — pure static parse, no DB needed.
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260528020000_relopass_case_engine_v1.sql"
)
_BACKFILL = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260603000000_corrections_reason_code_backfill.sql"
)

EXPECTED_REASON_CODES = {
    "OCR_ERROR",
    "TYPO_IN_SOURCE",
    "AMBIGUOUS_PARTICLE",
    "LEGITIMATE_VARIATION",
    "FRAUD_SUSPECTED",
    "OTHER",
}


class ReasonCodeEnumLockInTests(unittest.TestCase):
    def test_check_enum_has_exactly_six_values(self) -> None:
        sql = _MIGRATION.read_text()
        # Isolate the reason_code CHECK ( ... ) block.
        m = re.search(
            r"reason_code\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*reason_code\s+IN\s*\((?P<vals>.*?)\)\s*\)",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(m, "Could not locate reason_code CHECK constraint")
        found = set(re.findall(r"'([A-Z_]+)'", m.group("vals")))
        self.assertEqual(
            found,
            EXPECTED_REASON_CODES,
            f"reason_code enum drifted: {found ^ EXPECTED_REASON_CODES}",
        )

    def test_service_constant_matches_migration(self) -> None:
        self.assertEqual(set(svc.REASON_CODES), EXPECTED_REASON_CODES)
        self.assertEqual(len(svc.REASON_CODES), 6)

    def test_backfill_migration_present_and_idempotent_shape(self) -> None:
        self.assertTrue(_BACKFILL.exists(), "AIQ-554 backfill migration missing")
        body = _BACKFILL.read_text()
        self.assertIn("SET reason_code = 'OTHER'", body)
        self.assertIn("WHERE reason_code IS NULL", body)


# ---------------------------------------------------------------------------
# SQLite shim so production SQL runs unchanged.
# ---------------------------------------------------------------------------

# NB: by the time before_cursor_execute fires, SQLAlchemy has already compiled
# :named params down to the DBAPI placeholder (``?`` for pysqlite), so these
# regexes must match the post-compilation form, not ``:employer_id``.
_DATE_TRUNC_RE = re.compile(
    r"date_trunc\(\s*'week'\s*,\s*([\w.]+)\s*\)", re.IGNORECASE
)
_CAST_UUID_RE = re.compile(r"CAST\s*\(\s*(\?|:\w+)\s+AS\s+uuid\s*\)", re.IGNORECASE)
_JSON_ARROW_RE = re.compile(r"([\w.]+)->>'(\w+)'")


def _rewrite_for_sqlite(statement: str) -> str:
    # Monday of the week of <col> in SQLite: date(col,'weekday 0','-6 days')
    statement = _DATE_TRUNC_RE.sub(r"date(\1, 'weekday 0', '-6 days')", statement)
    statement = _CAST_UUID_RE.sub(r"\1", statement)
    statement = _JSON_ARROW_RE.sub(r"json_extract(\1, '$.\2')", statement)
    return statement


SCHEMA = """
CREATE TABLE cases (
  case_id TEXT PRIMARY KEY,
  corridor_id TEXT,
  employer_id TEXT
);
CREATE TABLE corrections (
  correction_id TEXT PRIMARY KEY,
  case_id TEXT,
  reason_code TEXT,
  context_snapshot TEXT,
  corrected_at TEXT
);
"""


def _make_user(role: str, company: str | None, is_admin: bool = False):
    return {"id": str(uuid.uuid4()), "role": role, "company": company, "is_admin": is_admin}


class CorrectionAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def _shim(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            return _rewrite_for_sqlite(statement), parameters

        # rce.corrections / rce.cases → corrections / cases for SQLite.
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        # Patch db.engine for both the service and router modules.
        self.svc_patch = mock.patch.object(svc.db, "engine", self.engine)
        self.svc_patch.start()
        self.addCleanup(self.svc_patch.stop)

        # weekly_corrections_by_reason references rce.corrections / rce.cases; strip
        # the schema prefix for SQLite by patching the SQL the service builds.
        self._orig_weekly = svc.weekly_corrections_by_reason

        def _weekly_no_schema(employer_id=None, weeks_back=4):
            # Re-run the real function but against unqualified table names.
            with mock.patch.object(svc, "text", lambda s: text(s.replace("rce.", ""))):
                return self._orig_weekly(employer_id=employer_id, weeks_back=weeks_back)

        self.weekly_patch = mock.patch.object(
            svc, "weekly_corrections_by_reason", _weekly_no_schema
        )
        self.weekly_patch.start()
        self.addCleanup(self.weekly_patch.stop)
        # Router imports the symbol by reference at module load → repoint it too.
        self.router_weekly_patch = mock.patch.object(
            router_module, "weekly_corrections_by_reason", _weekly_no_schema
        )
        self.router_weekly_patch.start()
        self.addCleanup(self.router_weekly_patch.stop)

        # _caller_company_id falls back to get_profile_record.
        self.profile_patch = mock.patch.object(
            router_module.db,
            "get_profile_record",
            side_effect=lambda uid: {"id": uid, "company_id": None},
        )
        self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)

    # --- seeding -----------------------------------------------------------
    def _seed_case(self, case_id: str, corridor: str, employer_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO cases (case_id, corridor_id, employer_id) "
                    "VALUES (:c, :corr, :emp)"
                ),
                {"c": case_id, "corr": corridor, "emp": employer_id},
            )

    def _seed_correction(
        self, case_id: str, reason: str, clause_type: str | None, days_ago: int
    ) -> None:
        when = datetime.now(timezone.utc) - timedelta(days=days_ago)
        snap = json.dumps({"clause_type": clause_type} if clause_type else {})
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO corrections (correction_id, case_id, reason_code, "
                    "context_snapshot, corrected_at) "
                    "VALUES (:id, :case, :reason, :snap, :ts)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "case": case_id,
                    "reason": reason,
                    "snap": snap,
                    "ts": when.isoformat(sep=" "),
                },
            )

    def _seed_twenty(self, employer_id: str) -> None:
        """20 corrections across 4 weeks, 2 corridors, mixed reasons/clauses."""
        case_de = str(uuid.uuid4())
        case_no = str(uuid.uuid4())
        self._seed_case(case_de, "IN-DE", employer_id)
        self._seed_case(case_no, "FR-NO", employer_id)

        plan = [
            # (case, reason, clause_type, days_ago)
            (case_de, "OCR_ERROR", "housing_allowance", 1),
            (case_de, "OCR_ERROR", "housing_allowance", 2),
            (case_de, "TYPO_IN_SOURCE", "housing_allowance", 3),
            (case_de, "AMBIGUOUS_PARTICLE", None, 4),
            (case_de, "OTHER", "schooling", 5),
            (case_de, "FRAUD_SUSPECTED", "schooling", 8),
            (case_de, "OCR_ERROR", "schooling", 9),
            (case_de, "LEGITIMATE_VARIATION", None, 10),
            (case_de, "OTHER", "housing_allowance", 11),
            (case_de, "OCR_ERROR", "housing_allowance", 15),
            (case_no, "TYPO_IN_SOURCE", "language_training", 1),
            (case_no, "OCR_ERROR", "language_training", 2),
            (case_no, "OTHER", None, 7),
            (case_no, "AMBIGUOUS_PARTICLE", "language_training", 8),
            (case_no, "FRAUD_SUSPECTED", "schooling", 9),
            (case_no, "OCR_ERROR", "schooling", 16),
            (case_no, "LEGITIMATE_VARIATION", "housing_allowance", 17),
            (case_no, "OTHER", "housing_allowance", 18),
            # Keep the two oldest rows within 21 days. weekly_corrections_by_reason
            # uses an ISO-week-aligned window (this-Monday − (weeks_back−1) weeks),
            # which covers only 21 + today.weekday() days — so days_ago=22/23 fell
            # outside the window on Mon/Tue, making this assertion weekday-flaky.
            (case_no, "TYPO_IN_SOURCE", None, 19),
            (case_no, "OCR_ERROR", "language_training", 20),
        ]
        for case_id, reason, clause, days_ago in plan:
            self._seed_correction(case_id, reason, clause, days_ago)

    # --- tests -------------------------------------------------------------
    def test_returns_three_way_grouped_buckets(self) -> None:
        emp = str(uuid.uuid4())
        self._seed_twenty(emp)
        rows = svc.weekly_corrections_by_reason(employer_id=emp, weeks_back=4)
        self.assertGreater(len(rows), 0)
        # Every row carries the 4 grouping keys + count.
        for r in rows:
            self.assertIn("week_start", r)
            self.assertIn("reason_code", r)
            self.assertIn("case_corridor", r)
            self.assertIn("clause_type", r)
            self.assertIsInstance(r["count"], int)
        # Grand total of all buckets == 20 seeded rows (4-week window covers all).
        self.assertEqual(sum(r["count"] for r in rows), 20)
        # Both corridors represented.
        corridors = {r["case_corridor"] for r in rows}
        self.assertIn("IN-DE", corridors)
        self.assertIn("FR-NO", corridors)

    def test_endpoint_admin_sees_all_and_totals(self) -> None:
        emp = str(uuid.uuid4())
        self._seed_twenty(emp)
        admin = _make_user("ADMIN", company=None, is_admin=True)
        resp = corrections_by_reason(employer_id=None, weeks_back=4, user=admin)
        self.assertEqual(resp["total"], 20)
        self.assertEqual(sum(resp["totals_by_reason"].values()), 20)
        # totals_by_reason is zero-filled across the full taxonomy.
        self.assertEqual(set(resp["totals_by_reason"].keys()), EXPECTED_REASON_CODES)
        # OCR_ERROR is the most common seeded reason (7 occurrences across both cases).
        self.assertEqual(resp["totals_by_reason"]["OCR_ERROR"], 7)

    def test_endpoint_hr_scoped_to_own_employer(self) -> None:
        emp_a = "company-a"
        emp_b = "company-b"
        self._seed_twenty(emp_a)
        # Seed a stray correction for employer B.
        case_b = str(uuid.uuid4())
        self._seed_case(case_b, "IN-DE", emp_b)
        self._seed_correction(case_b, "OTHER", "schooling", 1)

        hr = _make_user("HR", company=emp_a)
        resp = corrections_by_reason(employer_id=emp_b, weeks_back=4, user=hr)
        # HR override is ignored — still pinned to company-a's 20 rows.
        self.assertEqual(resp["total"], 20)
        self.assertEqual(resp["employer_id"], emp_a)

    def test_hr_without_company_rejected(self) -> None:
        hr = _make_user("HR", company=None)
        with self.assertRaises(HTTPException) as ctx:
            corrections_by_reason(employer_id=None, weeks_back=4, user=hr)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_zero_correction_week_digest(self) -> None:
        # No data seeded → empty buckets, but digest still renders full taxonomy.
        totals = svc.summarize_by_reason([])
        self.assertEqual(set(totals.keys()), EXPECTED_REASON_CODES)
        self.assertEqual(sum(totals.values()), 0)

    def test_mixed_reason_week_digest(self) -> None:
        rows = [
            {"reason_code": "OCR_ERROR", "count": 3},
            {"reason_code": "FRAUD_SUSPECTED", "count": 1},
            {"reason_code": "OTHER", "count": 2},
        ]
        totals = svc.summarize_by_reason(rows)
        self.assertEqual(totals["OCR_ERROR"], 3)
        self.assertEqual(totals["FRAUD_SUSPECTED"], 1)
        self.assertEqual(totals["OTHER"], 2)
        self.assertEqual(totals["TYPO_IN_SOURCE"], 0)


if __name__ == "__main__":
    unittest.main()

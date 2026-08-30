"""
[AIQ-2136] permit_expiry_date had no write path, so a whole finished vertical was dormant.

Measured on production 2026-08-23: `git grep "UPDATE public.immigration_cases"` returned
NOTHING across the entire backend, the create endpoint omits the column, and the table's
RLS is service_role_only so no client could write it either. Result: 0 of 4 immigration
cases carried an expiry and `compliance_alerts` held 0 rows — while a seeded 60-day rule,
the evaluator, the alerts API, the HR risk dashboard section, the case-detail field and
the AIQ-1860 nudge were all already built and waiting on it.

These call the handler directly rather than through TestClient: the suite's conftest
replaces `backend.database` with a MagicMock, so a TestClient test would assert against
mock return values and pass while proving nothing.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import date, timedelta
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import immigration_status  # noqa: E402
from backend.app.routers.immigration_status import ImmigrationCaseDatesUpdate  # noqa: E402

SCHEMA = """
CREATE TABLE public.immigration_cases (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    corridor_from TEXT,
    corridor_to TEXT,
    permit_type TEXT,
    partner_name TEXT,
    expected_submission_date TEXT,
    expected_grant_date TEXT,
    permit_expiry_date TEXT,
    status TEXT,
    document_statuses TEXT,
    created_by_hr_id TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE public.relocation_cases (
    id TEXT PRIMARY KEY,
    company_id TEXT
);
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    entity_type TEXT,
    entity_id TEXT,
    action_type TEXT,
    old_value_json TEXT,
    new_value_json TEXT,
    actor_id TEXT,
    actor_type TEXT,
    created_at TEXT
);
"""

IMM_ID = "imm-1"
CASE_ID = "case-1"
COMPANY = "co-1"
HR = {"id": "hr-1", "role": "HR"}
ADMIN = {"id": "admin-1", "role": "ADMIN", "is_admin": True}


class PermitExpiryWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        # StaticPool: the ATTACHed `public` schema lives on the CONNECTION, so every
        # checkout must be the same one or the router's `public.<table>` SQL stops
        # resolving mid-test.
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            # The router qualifies every table as `public.<name>`. SQLite has no schemas,
            # but an ATTACHed in-memory database named `public` makes the same SQL resolve
            # unchanged — so the test exercises the REAL query text, not a rewritten one.
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            conn.execute(
                text(
                    "INSERT INTO public.immigration_cases (id, case_id, permit_type, status) "
                    "VALUES (:i, :c, 'work_permit', 'initiated')"
                ),
                {"i": IMM_ID, "c": CASE_ID},
            )
            conn.execute(
                text("INSERT INTO public.relocation_cases (id, company_id) VALUES (:i, :co)"),
                {"i": CASE_ID, "co": COMPANY},
            )
        patcher = mock.patch.object(immigration_status.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch(self, body: ImmigrationCaseDatesUpdate, user=None, org=COMPANY, imm_id=IMM_ID):
        return immigration_status.update_immigration_case_dates(
            imm_id, body, hr_user=user or HR, org_id=org
        )

    def _stored(self, col: str = "permit_expiry_date"):
        with self.engine.connect() as conn:
            return conn.execute(
                text(f"SELECT {col} FROM public.immigration_cases WHERE id = :i"), {"i": IMM_ID}
            ).scalar_one()

    # ── the gap this closes ───────────────────────────────────────────────────

    def test_hr_can_set_the_permit_expiry(self) -> None:
        """The whole point. There was no way to do this at all."""
        out = self._patch(ImmigrationCaseDatesUpdate(permit_expiry_date="2026-12-01"))
        self.assertEqual(self._stored(), "2026-12-01")
        self.assertEqual(out["permit_expiry_date"], "2026-12-01")

    def test_a_wrong_date_can_be_cleared(self) -> None:
        """A date entered by mistake must not be permanent."""
        self._patch(ImmigrationCaseDatesUpdate(permit_expiry_date="2026-12-01"))
        self._patch(ImmigrationCaseDatesUpdate(permit_expiry_date=None))
        self.assertIsNone(self._stored())

    def test_omitted_fields_are_left_alone(self) -> None:
        """Setting one date must not blank the others — the same lesson as the feedback
        console, where an unconditional upsert silently erased every resolution."""
        self._patch(
            ImmigrationCaseDatesUpdate(
                permit_expiry_date="2026-12-01", expected_grant_date="2026-06-01"
            )
        )
        self._patch(ImmigrationCaseDatesUpdate(expected_submission_date="2026-05-01"))
        self.assertEqual(self._stored(), "2026-12-01")
        self.assertEqual(self._stored("expected_grant_date"), "2026-06-01")
        self.assertEqual(self._stored("expected_submission_date"), "2026-05-01")

    def test_an_empty_body_is_a_400_not_a_silent_noop(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._patch(ImmigrationCaseDatesUpdate())
        self.assertEqual(ctx.exception.status_code, 400)

    # ── validation ────────────────────────────────────────────────────────────

    def test_a_malformed_date_is_refused_not_stored(self) -> None:
        """compliance_evaluator does `(actual - today).days` on this column, so garbage
        does not fail loudly — it makes the rule silently stop firing."""
        for bad in ["01/12/2026", "next tuesday", "2026-13-01", "2026-02-30", "20261201"]:
            with self.subTest(bad=bad):
                with self.assertRaises(HTTPException) as ctx:
                    self._patch(ImmigrationCaseDatesUpdate(permit_expiry_date=bad))
                self.assertEqual(ctx.exception.status_code, 422)
        self.assertIsNone(self._stored(), "nothing may be written on a rejected value")

    def test_an_unknown_case_is_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._patch(
                ImmigrationCaseDatesUpdate(permit_expiry_date="2026-12-01"), imm_id="nope"
            )
        self.assertEqual(ctx.exception.status_code, 404)

    # ── tenant scoping on the write ───────────────────────────────────────────

    def test_hr_from_another_company_cannot_write(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._patch(
                ImmigrationCaseDatesUpdate(permit_expiry_date="2026-12-01"), org="other-co"
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIsNone(self._stored(), "a refused write must not land")

    def test_an_admin_is_not_restricted_by_company(self) -> None:
        """An admin's org_id resolves empty, so gating strictly on equality would lock
        admins out of every case."""
        self._patch(
            ImmigrationCaseDatesUpdate(permit_expiry_date="2026-12-01"), user=ADMIN, org=""
        )
        self.assertEqual(self._stored(), "2026-12-01")

    def test_an_audit_row_is_written(self) -> None:
        self._patch(ImmigrationCaseDatesUpdate(permit_expiry_date="2026-12-01"))
        with self.engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM audit_logs WHERE entity_type='immigration_case'")
            ).scalar_one()
        self.assertEqual(n, 1)


class TheDateActuallyFiresTheRuleTests(unittest.TestCase):
    """The point of the ticket is not the endpoint — it is that a date now produces an
    alert. An endpoint that accepts a date and yields no alert has fixed nothing."""

    def test_a_date_inside_the_window_fires_the_seeded_60_day_rule(self) -> None:
        from backend.app.services.compliance_evaluator import (
            ComplianceRule, CaseComplianceData, evaluate,
        )
        today = date(2026, 8, 23)
        rule = ComplianceRule(
            id="c0119a01-0000-4000-8000-000000000001",
            category="immigration",
            severity="high",
            trigger_condition={
                "type": "date_threshold", "field": "permit_expiry_date",
                "operator": "within_days", "value": 60, "unit": "days",
            },
            active=True,
        )
        case = CaseComplianceData(
            case_id=CASE_ID, permit_expiry_date=today + timedelta(days=10)
        )
        firings = evaluate([rule], case, today=today)
        self.assertEqual(len(firings), 1, "a date 10 days out must fire the 60-day rule")
        self.assertEqual(firings[0].detail["days_until"], 10)

    def test_no_date_fires_nothing(self) -> None:
        """Which is exactly the state production is in today: 0 alerts, because every
        permit_expiry_date is NULL."""
        from backend.app.services.compliance_evaluator import (
            ComplianceRule, CaseComplianceData, evaluate,
        )
        rule = ComplianceRule(
            id="r", category="immigration", severity="high",
            trigger_condition={
                "type": "date_threshold", "field": "permit_expiry_date",
                "operator": "within_days", "value": 60, "unit": "days",
            },
            active=True,
        )
        case = CaseComplianceData(case_id=CASE_ID, permit_expiry_date=None)
        self.assertEqual(evaluate([rule], case, today=date(2026, 8, 23)), [])


if __name__ == "__main__":
    unittest.main()

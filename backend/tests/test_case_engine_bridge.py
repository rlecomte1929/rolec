"""Regression: an employee can access an HR-created case by its case id.

Defect (found 2026-06-05 diagnosing why the employee roadmap/dossier are empty
platform-wide): ``_assert_case_access`` resolved the case→assignment link only by
``case_assignments.id`` (assignment id), so an employee passing a *case id* (the
canonical/relocation_cases id) for an HR-created case got **404** even though the
``case_assignments`` row correctly links them. The fix resolves by
``id`` / ``canonical_case_id`` / ``case_id`` and treats the assignment as the
authoritative employee↔case link — necessary because ``public.cases.employee_id``
holds a contact UUID, not the caller's (possibly legacy text) id.

The companion change — ``Database._ensure_canonical_case_from_wizard`` bridging
the wizard intake into the canonical ``public.cases`` row the trigger reads — is
a fail-safe data sync verified live on prod (it lives on the DB object that this
suite mocks, so it can't be exercised here without a real DB).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_test_case_bridge.db")

import unittest
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import case_service
from backend.app.services.case_service import _assert_case_access

CASE = "cccccccc-cccc-cccc-cccc-cccccccccccc"
OTHER = "dddddddd-dddd-dddd-dddd-dddddddddddd"
EMP_UUID = "e0d4fd90-0000-0000-0000-000000000001"


class AssignmentBasedCaseAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        # Shared in-memory SQLite so tables persist across connections, injected
        # in place of the conftest-mocked main_db.engine.
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE case_assignments "
                "(id TEXT, case_id TEXT, canonical_case_id TEXT, employee_user_id TEXT, "
                "hr_user_id TEXT, employee_contact_id TEXT)"
            ))
            c.execute(text("CREATE TABLE relocation_cases (id TEXT, company_id TEXT)"))
            c.execute(text(
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, employee_user_id, hr_user_id, employee_contact_id) "
                "VALUES ('asgn-1', :c, :c, 'emp-1', 'hr-1', :emp)"
            ), {"c": CASE, "emp": EMP_UUID})
            c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, 'co-1')"), {"c": CASE})
        self._p = mock.patch.object(case_service.main_db, "engine", self.engine)
        self._p.start()
        self.addCleanup(self._p.stop)

    def _add_cases_row(self, employee_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, company_id TEXT, "
                "employee_id TEXT, hr_owner_id TEXT)"
            ))
            c.execute(text(
                "INSERT INTO cases (id, company_id, employee_id) VALUES (:c, 'co-1', :e)"
            ), {"c": CASE, "e": employee_id})

    def test_owning_employee_granted_by_case_id_no_cases_row(self) -> None:
        # The fix: resolve via case_id/canonical_case_id (was: only ca.id → 404).
        try:
            _assert_case_access({"id": "emp-1", "role": "EMPLOYEE"}, CASE)
        except HTTPException as e:  # pragma: no cover
            self.fail(f"owning employee should be granted, got {e.status_code} {e.detail}")

    def test_owning_employee_granted_even_when_cases_row_has_contact_uuid(self) -> None:
        # public.cases.employee_id holds the CONTACT uuid (≠ caller id) — access
        # must still be granted via the authoritative assignment link.
        self._add_cases_row(employee_id=EMP_UUID)
        try:
            _assert_case_access({"id": "emp-1", "role": "EMPLOYEE"}, CASE)
        except HTTPException as e:  # pragma: no cover
            self.fail(f"owner should be granted via assignment, got {e.status_code}")

    def test_non_owner_employee_forbidden(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access({"id": "emp-99", "role": "EMPLOYEE"}, CASE)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unknown_case_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access({"id": "emp-1", "role": "EMPLOYEE"}, OTHER)
        self.assertEqual(ctx.exception.status_code, 404)


class CanonicalCaseEnumGuardTests(unittest.TestCase):
    """Source guard for the bridge's public.cases enum values.

    public.cases enforces CHECK constraints — status in (draft, active, on_hold,
    completed, cancelled), stage in (discovery, dossier, roadmap, in_progress,
    closing, closed). The first cut of the bridge inserted 'created'/'intake',
    which failed the CHECK (silently, fail-safe) so no canonical row was created
    and the trigger generated no forms (empty roadmap/dossier). SQLite has no
    CHECK constraints, so an integration test can't catch this — guard at source.
    """

    def _bridge_source(self) -> str:
        import os
        path = os.path.join(_REPO_ROOT, "backend", "database.py")
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        start = src.index("def _ensure_canonical_case_from_wizard")
        end = src.index("\n    def ", start + 1)
        return src[start:end]

    def test_bridge_uses_valid_status_and_stage(self) -> None:
        body = self._bridge_source()
        self.assertIn("'active', 'discovery'", body,
                      "bridge must seed a valid status/stage for public.cases")
        for bad in ("'created', 'intake'", "'created',", "'intake',"):
            self.assertNotIn(bad, body,
                             f"{bad} violates the public.cases status/stage CHECK constraints")


_REPO_ROOT = __import__("os").path.dirname(
    __import__("os").path.dirname(__import__("os").path.dirname(__file__))
)


from backend.database import db as main_db  # noqa: E402

BRIDGE_CASE = "11111111-1111-1111-1111-111111111111"
BRIDGE_EMP = "e0d4fd90-1111-1111-1111-111111111111"


class CanonicalCaseBridgeFunctionalTests(unittest.TestCase):
    """Exercise ``_ensure_canonical_case_from_wizard`` against a real (sqlite)
    engine — it materializes the canonical ``public.cases`` row from a wizard
    intake. The hardening adds a company-resolution fallback chain
    (relocation_cases -> hr_users -> employee profile) so the bridge isn't a
    single point of failure when relocation_cases is missing/incomplete."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT, employee_id TEXT, "
                "origin_country_code TEXT, dest_country_code TEXT, dest_city TEXT, purpose TEXT, "
                "status TEXT, stage TEXT, target_move_date TEXT)"
            ))
            c.execute(text(
                "CREATE TABLE case_assignments (id TEXT, case_id TEXT, canonical_case_id TEXT, "
                "employee_user_id TEXT, hr_user_id TEXT, employee_contact_id TEXT)"
            ))
            c.execute(text("CREATE TABLE relocation_cases (id TEXT, company_id TEXT)"))
            c.execute(text("CREATE TABLE profiles (id TEXT, email TEXT, company_id TEXT, role TEXT, full_name TEXT)"))
            c.execute(text("CREATE TABLE users (id TEXT, email TEXT)"))
            c.execute(text("CREATE TABLE hr_users (profile_id TEXT, company_id TEXT)"))
            c.execute(text("INSERT INTO profiles (id, email) VALUES (:i, 'emp@x.com')"), {"i": BRIDGE_EMP})
        self._p = mock.patch.object(main_db, "engine", self.engine)
        self._p.start()
        self.addCleanup(self._p.stop)

    def _assignment(self, **over):
        a = {"id": "asgn-b", "case_id": BRIDGE_CASE, "canonical_case_id": BRIDGE_CASE,
             "employee_user_id": BRIDGE_EMP, "hr_user_id": "hr-legacy", "employee_contact_id": BRIDGE_EMP}
        a.update(over)
        return a

    def _derived(self, **over):
        d = {"origin_country": "France", "dest_country": "GB", "dest_city": "London", "purpose": "work"}
        d.update(over)
        return d

    def _cases_row(self):
        with self.engine.connect() as c:
            return c.execute(text("SELECT * FROM cases WHERE id = :i"), {"i": BRIDGE_CASE}).mappings().first()

    def test_bridge_creates_case_via_relocation_company(self) -> None:
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES (:i, 'co-reloc')"), {"i": BRIDGE_CASE})
        main_db._ensure_canonical_case_from_wizard(BRIDGE_CASE, self._derived(), self._assignment())
        row = self._cases_row()
        self.assertIsNotNone(row)
        self.assertEqual(row["company_id"], "co-reloc")
        self.assertEqual(row["employee_id"], BRIDGE_EMP)
        self.assertEqual(row["dest_country_code"], "GB")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["stage"], "discovery")

    def test_bridge_creates_case_via_hr_users_fallback(self) -> None:
        # No relocation_cases row at all — the durability win: hr_users resolves the tenant.
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO hr_users (profile_id, company_id) VALUES ('hr-legacy', 'co-hr')"))
        main_db._ensure_canonical_case_from_wizard(BRIDGE_CASE, self._derived(), self._assignment())
        row = self._cases_row()
        self.assertIsNotNone(row, "bridge should still materialize via hr_users fallback")
        self.assertEqual(row["company_id"], "co-hr")

    def test_bridge_resolves_legacy_login_id_employee(self) -> None:
        # employee_user_id is a login id, resolved to the profile via users.email->profiles.email.
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES (:i, 'co-reloc')"), {"i": BRIDGE_CASE})
            c.execute(text("INSERT INTO users (id, email) VALUES ('seed-emp-x', 'emp@x.com')"))
        main_db._ensure_canonical_case_from_wizard(
            BRIDGE_CASE, self._derived(), self._assignment(employee_user_id="seed-emp-x", employee_contact_id="seed-emp-x"))
        row = self._cases_row()
        self.assertIsNotNone(row)
        self.assertEqual(row["employee_id"], BRIDGE_EMP)

    def test_bridge_skips_when_no_company_anywhere(self) -> None:
        # No relocation_cases, no hr_users, no profile company -> never insert a partial row.
        main_db._ensure_canonical_case_from_wizard(BRIDGE_CASE, self._derived(), self._assignment())
        self.assertIsNone(self._cases_row())

    def test_bridge_skips_when_no_destination(self) -> None:
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES (:i, 'co-reloc')"), {"i": BRIDGE_CASE})
        main_db._ensure_canonical_case_from_wizard(BRIDGE_CASE, self._derived(dest_country=""), self._assignment())
        self.assertIsNone(self._cases_row())

    def test_get_company_id_for_assignment_id_hr_fallback(self) -> None:
        # relocation_cases absent -> resolve company via the assignment's hr_users link.
        with self.engine.begin() as c:
            c.execute(text(
                "INSERT INTO case_assignments (id, case_id, canonical_case_id, employee_user_id, hr_user_id, employee_contact_id) "
                "VALUES ('asgn-h', :i, :i, :e, 'hr-legacy', :e)"
            ), {"i": BRIDGE_CASE, "e": BRIDGE_EMP})
            c.execute(text("INSERT INTO hr_users (profile_id, company_id) VALUES ('hr-legacy', 'co-hr')"))
        self.assertEqual(main_db.get_company_id_for_assignment_id("asgn-h"), "co-hr")


if __name__ == "__main__":
    unittest.main()

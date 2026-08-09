"""[AIQ-1776] _assert_case_access returns the resolved canonical case id.

The defect class this closes (AIQ-1775 measured 29 live endpoints, 12 of them
this shape): ``_assert_case_access`` accepts THREE id forms — a ``public.cases``
UUID, ``case_assignments.case_id`` / ``canonical_case_id``, and an assignment id
— resolves them internally, and used to return ``None``. Callers therefore had
no resolved value to key on and ran ``WHERE case_id = :raw_path_param``. Pass an
assignment id and the access check PASSES while the SQL matches nothing, so the
endpoint silently returns empty. ``employee_quotes.list_hr_quote_requests``
shipped exactly that way: 0 of 51 rows ever matched.

Every test here is red before the fix:
  - the contract tests fail because the helper returned ``None``;
  - each router test fails with an empty result or a 404, because the query was
    keyed on the assignment id while the row is stored under the canonical id.

The fixture deliberately gives ``case_assignments`` a ``case_id`` that DIFFERS
from ``canonical_case_id`` so the COALESCE precedence is actually exercised —
if the two were equal, a wrong precedence would still pass.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_test_aiq1776.db")

import importlib
import unittest
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import case_service
from backend.app.services.case_service import _assert_case_access

# All ids must be well-formed UUIDs — _assert_case_access 404s malformed ones
# up front (the B24 fail-safe against a Postgres uuid-cast 500).
ASSIGNMENT_ID = "aaaaaaaa-0000-0000-0000-000000000001"
CANONICAL_ID = "cccccccc-0000-0000-0000-000000000001"
LEGACY_LINK_ID = "bbbbbbbb-0000-0000-0000-000000000001"  # ca.case_id, != canonical
LEGACY_CASE_ID = "dddddddd-0000-0000-0000-000000000001"  # public.cases only
FOREIGN_ID = "eeeeeeee-0000-0000-0000-000000000001"
UNKNOWN_ID = "ffffffff-0000-0000-0000-000000000001"

FORM_ID = "f0f0f0f0-0000-0000-0000-000000000001"
TEMPLATE_ID = "70707070-0000-0000-0000-000000000001"
DOSSIER_ID = "d0d0d0d0-0000-0000-0000-000000000001"

EMPLOYEE = {"id": "emp-1", "auth_uuid": "e0d4fd90-0000-0000-0000-000000000001",
            "role": "EMPLOYEE"}
OUTSIDER = {"id": "nobody-1", "auth_uuid": "b0b0b0b0-0000-0000-0000-000000000009",
            "role": "EMPLOYEE"}


def _build_engine():
    """Shared in-memory SQLite standing in for the conftest-mocked main_db.engine."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE case_assignments "
            "(id TEXT, case_id TEXT, canonical_case_id TEXT, "
            " employee_user_id TEXT, hr_user_id TEXT)"
        ))
        c.execute(text("CREATE TABLE relocation_cases (id TEXT, company_id TEXT)"))
        c.execute(text(
            "CREATE TABLE cases (id TEXT, company_id TEXT, employee_id TEXT, hr_owner_id TEXT)"
        ))
        c.execute(text("CREATE TABLE profiles (id TEXT, company_id TEXT, full_name TEXT)"))

        # The case under test: reachable by assignment id, by canonical id, and by
        # the (different) ca.case_id. canonical_case_id must win.
        c.execute(text(
            "INSERT INTO case_assignments "
            "(id, case_id, canonical_case_id, employee_user_id, hr_user_id) "
            "VALUES (:a, :legacy, :canon, 'emp-1', 'hr-1')"
        ), {"a": ASSIGNMENT_ID, "legacy": LEGACY_LINK_ID, "canon": CANONICAL_ID})
        c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, 'co-1')"),
                  {"c": CANONICAL_ID})

        # A case belonging to someone else — used for the 403 path.
        c.execute(text(
            "INSERT INTO case_assignments "
            "(id, case_id, canonical_case_id, employee_user_id, hr_user_id) "
            "VALUES (:a, :a, :a, 'someone-else', 'hr-9')"
        ), {"a": FOREIGN_ID})

        # A legacy public.cases row with NO assignment — the fallback path.
        c.execute(text(
            "INSERT INTO cases (id, company_id, employee_id, hr_owner_id) "
            "VALUES (:c, 'co-1', 'emp-1', 'hr-1')"
        ), {"c": LEGACY_CASE_ID})

        # ── Case-scoped rows, all stored under the CANONICAL id ──────────────
        c.execute(text(
            "CREATE TABLE pets (id TEXT, case_id TEXT, name TEXT, species TEXT, breed TEXT,"
            " microchip_number TEXT, date_of_birth TEXT, passport_number TEXT,"
            " health_cert_expiry TEXT, vaccinations TEXT, vet_name TEXT, vet_phone TEXT,"
            " vet_country TEXT, created_at TEXT, updated_at TEXT)"
        ))
        c.execute(text(
            "INSERT INTO pets (id, case_id, name, species, created_at, updated_at) "
            "VALUES ('pet-1', :c, 'Rex', 'dog', '2026-01-01', '2026-01-01')"
        ), {"c": CANONICAL_ID})

        c.execute(text(
            "CREATE TABLE case_forms (id TEXT, case_id TEXT, form_template_id TEXT,"
            " is_adhoc INTEGER DEFAULT 0, adhoc_name TEXT, adhoc_authority TEXT,"
            " original_file_url TEXT, flag_note TEXT, flagged_at TEXT, flagged_by TEXT,"
            " updated_at TEXT)"
        ))
        c.execute(text(
            "INSERT INTO case_forms (id, case_id, form_template_id, is_adhoc) "
            "VALUES (:f, :c, :t, 1)"
        ), {"f": FORM_ID, "c": CANONICAL_ID, "t": TEMPLATE_ID})

        c.execute(text(
            "CREATE TABLE form_templates (id TEXT, code TEXT, name TEXT, version TEXT,"
            " original_pdf_url TEXT)"
        ))
        c.execute(text(
            "INSERT INTO form_templates (id, code, name, version, original_pdf_url) "
            "VALUES (:t, 'UTL-2011', 'Test template', '1.0.0', NULL)"
        ), {"t": TEMPLATE_ID})

        c.execute(text(
            "CREATE TABLE dossier_packages (id TEXT, case_id TEXT, name TEXT, form_ids TEXT,"
            " cover_page INTEGER, pdf_url TEXT, generated_at TEXT, created_at TEXT,"
            " created_by TEXT)"
        ))
        c.execute(text(
            "INSERT INTO dossier_packages (id, case_id, name, form_ids, cover_page, created_at) "
            "VALUES (:d, :c, 'Pack', '[]', 0, '2026-01-01')"
        ), {"d": DOSSIER_ID, "c": CANONICAL_ID})

        c.execute(text(
            "CREATE TABLE case_form_comments (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " case_form_id TEXT, author_id TEXT, content TEXT,"
            " created_at TEXT DEFAULT '2026-01-01')"
        ))
    return engine


# Every module under test binds the ``backend.database`` singleton at import time,
# each under its own name: ``main_db`` in most, plain ``db`` in case_form_pdf.
_DB_BINDINGS = (
    ("backend.app.services.case_service", "main_db"),
    ("backend.app.routers.pets", "main_db"),
    ("backend.app.routers.cases_write", "main_db"),
    ("backend.app.routers.cases_admin", "main_db"),
    ("backend.app.routers.case_forms_adhoc", "main_db"),
    ("backend.app.routers.case_form_pdf", "db"),
)


class _EngineFixture(unittest.TestCase):
    """Points every module under test at one in-memory SQLite engine.

    Patching ``case_service.main_db.engine`` alone is NOT enough, and the failure
    is silent. Under full-suite collection some test modules put the repo root and
    ``backend/`` both on ``sys.path``, so ``backend/database.py`` gets imported
    twice under two module names — and the routers end up holding *different* ``db``
    singletons. Patching one leaves the others on whatever ``DATABASE_URL`` resolves
    to, which on a developer machine with a local ``.env`` is the production pooler:
    ``list_pets`` then SELECTed against prod, matched nothing, and returned 0 rows
    that read exactly like the bug this file is asserting is fixed.

    So resolve each module through ``sys.modules`` at setUp time and patch whichever
    ``db`` object it actually holds.
    """

    def setUp(self) -> None:
        self.engine = _build_engine()
        seen = set()
        for mod_name, attr in _DB_BINDINGS:
            module = importlib.import_module(mod_name)
            db_obj = getattr(module, attr)
            if id(db_obj) in seen:
                continue
            seen.add(id(db_obj))
            patcher = mock.patch.object(db_obj, "engine", self.engine)
            patcher.start()
            self.addCleanup(patcher.stop)


class AssertCaseAccessReturnContract(_EngineFixture):
    """Criterion 1 — the resolved id, and the raises, are both unchanged-or-correct."""

    def test_all_three_id_forms_return_the_same_canonical_id(self):
        for label, given in (
            ("assignment id", ASSIGNMENT_ID),
            ("canonical case id", CANONICAL_ID),
            ("case_assignments.case_id", LEGACY_LINK_ID),
        ):
            with self.subTest(form=label):
                self.assertEqual(
                    _assert_case_access(EMPLOYEE, given), CANONICAL_ID,
                    f"{label} must resolve to the canonical case id",
                )

    def test_canonical_case_id_wins_over_case_id(self):
        # The fixture's ca.case_id differs from ca.canonical_case_id on purpose.
        # COALESCE(NULLIF(TRIM(canonical_case_id),''), case_id) must prefer canonical,
        # matching resolve_case_forms_case_id exactly.
        self.assertNotEqual(LEGACY_LINK_ID, CANONICAL_ID)
        self.assertEqual(_assert_case_access(EMPLOYEE, ASSIGNMENT_ID), CANONICAL_ID)

    def test_agrees_with_resolve_case_forms_case_id(self):
        """The two resolvers must never disagree — that is the whole point of
        returning the id from the helper rather than adding a third path."""
        for given in (ASSIGNMENT_ID, CANONICAL_ID, LEGACY_LINK_ID, LEGACY_CASE_ID):
            with self.subTest(given=given):
                self.assertEqual(
                    _assert_case_access(EMPLOYEE, given),
                    case_service.resolve_case_forms_case_id(given),
                )

    def test_legacy_public_cases_row_returns_its_own_id(self):
        # No assignment resolves, so resolve_case_forms_case_id returns the input
        # unchanged — the id those legacy rows are actually keyed by.
        self.assertEqual(_assert_case_access(EMPLOYEE, LEGACY_CASE_ID), LEGACY_CASE_ID)

    def test_malformed_id_still_404s(self):
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access(EMPLOYEE, "not-a-uuid")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unknown_case_still_404s(self):
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access(EMPLOYEE, UNKNOWN_ID)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_other_tenants_case_still_403s_not_404s(self):
        # AUTH BOUNDARY: 403 here and 404 for a non-existent id are deliberately
        # different, so an attacker cannot probe which UUIDs exist by status code.
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access(OUTSIDER, FOREIGN_ID)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_db_failure_degrades_to_404_never_500(self):
        """B24-REGRESSION fail-safe: a lookup error must not become a 500."""
        broken = mock.Mock()
        broken.connect.side_effect = RuntimeError("connection lost")
        broken.dialect.name = "sqlite"
        with mock.patch.object(case_service.main_db, "engine", broken):
            with self.assertRaises(HTTPException) as ctx:
                _assert_case_access(EMPLOYEE, CANONICAL_ID)
        self.assertEqual(ctx.exception.status_code, 404)


class AssignmentIdReachesTheRows(_EngineFixture):
    """Criterion 2 — one test per router.

    Each passes an ASSIGNMENT id for a row stored under the CANONICAL id. Before
    the fix every one of these came back empty or 404.
    """

    def test_pets_list_pets(self):
        from backend.app.routers import pets

        result = pets.list_pets(case_id=ASSIGNMENT_ID, user=EMPLOYEE)
        self.assertEqual(len(result), 1, "an assignment id must reach the case's pets")
        self.assertEqual(result[0].name, "Rex")
        self.assertEqual(result[0].case_id, CANONICAL_ID)

    def test_pets_create_pet_stores_the_canonical_id(self):
        """The write side matters too: the guard's regex only sees `case_id = :bind`
        predicates, so this INSERT was never flagged — but storing the raw
        assignment id would make the new row invisible to list_pets."""
        from backend.app.routers import pets

        created = pets.create_pet(
            case_id=ASSIGNMENT_ID,
            payload=pets.PetCreate(name="Bella", species="cat"),
            user=EMPLOYEE,
        )
        self.assertEqual(created.case_id, CANONICAL_ID)
        self.assertEqual(len(pets.list_pets(case_id=ASSIGNMENT_ID, user=EMPLOYEE)), 2)

    def test_case_form_pdf_get_form_original_pdf(self):
        from backend.app.routers import case_form_pdf

        resp = case_form_pdf.get_form_original_pdf(
            case_id=ASSIGNMENT_ID, form_id=FORM_ID, user=EMPLOYEE
        )
        # The template has no PDF attached → documented 200 + signed_url=None.
        # Reaching that empty-state at all proves the form row was found.
        self.assertEqual(resp.template_code, "UTL-2011")
        self.assertIsNone(resp.signed_url)

    def test_cases_admin_delete_dossier(self):
        from backend.app.routers import cases_admin

        resp = cases_admin.delete_dossier(
            case_id=ASSIGNMENT_ID, dossier_id=DOSSIER_ID, user=EMPLOYEE
        )
        self.assertEqual(resp.status_code, 204)
        with self.engine.connect() as c:
            left = c.execute(text("SELECT count(*) FROM dossier_packages")).scalar()
        self.assertEqual(left, 0)

    def test_cases_write_create_form_comment(self):
        from backend.app.routers import cases_write

        item = cases_write.create_form_comment(
            case_id=ASSIGNMENT_ID,
            form_id=FORM_ID,
            payload=cases_write.CommentCreate(content="looks good"),
            user=EMPLOYEE,
        )
        self.assertEqual(item.content, "looks good")

    def test_case_forms_adhoc_replace_adhoc_pdf_finds_the_form(self):
        """replace_adhoc_pdf needs a real upload to run to completion, so assert the
        narrower thing that is still decisive: it gets PAST the form lookup. Before
        the fix that lookup raised 404 'Form not found' for an assignment id."""
        import asyncio

        from backend.app.routers import case_forms_adhoc

        class _EmptyUpload:
            filename = "x.pdf"
            content_type = "application/pdf"

            async def read(self):
                return b""

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(case_forms_adhoc.replace_adhoc_pdf(
                case_id=ASSIGNMENT_ID, form_id=FORM_ID,
                file=_EmptyUpload(), user=EMPLOYEE,
            ))
        self.assertNotEqual(
            ctx.exception.detail, "Form not found",
            "the form lookup must be keyed on the resolved canonical case id",
        )


if __name__ == "__main__":
    unittest.main()

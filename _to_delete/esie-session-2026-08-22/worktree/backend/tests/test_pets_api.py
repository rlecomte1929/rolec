"""
Tests for the AIQ-288 pets CRUD API.

Validation criteria covered:
  1. Migration applies — exercised implicitly by mirroring the schema in SQLite.
  2. INSERT of 2 pets on the same case_id succeeds (no UNIQUE on case_id).
  3. DELETE of one pet leaves the other intact.
  4. All 4 routes return correct status codes.
  5. RLS — employees can only operate on pets attached to a case they own
     (exercised via the shared _assert_case_access helper).

Same fixture pattern as test_case_dossier_forms.py: in-memory SQLite engine,
mock main_db.engine on the cases module, call router functions directly.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases as cases_module  # noqa: E402
from backend.app.routers import pets as pets_module  # noqa: E402
from backend.app.routers.pets import (  # noqa: E402
    PetCreate,
    PetPatch,
    create_pet,
    delete_pet,
    list_pets,
    update_pet,
)


SCHEMA = """
CREATE TABLE cases (
  id           TEXT PRIMARY KEY,
  company_id   TEXT,
  employee_id  TEXT,
  hr_owner_id  TEXT
);
CREATE TABLE profiles (
  id         TEXT PRIMARY KEY,
  email      TEXT,
  full_name  TEXT,
  company_id TEXT
);
CREATE TABLE pets (
  id                  TEXT PRIMARY KEY,
  case_id             TEXT NOT NULL,
  name                TEXT,
  species             TEXT NOT NULL,
  breed               TEXT,
  microchip_number    TEXT,
  date_of_birth       TEXT,
  passport_number     TEXT,
  health_cert_expiry  TEXT,
  vaccinations        TEXT NOT NULL DEFAULT '[]',
  vet_name            TEXT,
  vet_phone           TEXT,
  vet_country         TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _u() -> str:
    return str(uuid.uuid4())


def _emp_user(uid: str) -> dict:
    return {"id": uid, "role": "EMPLOYEE", "is_admin": False}


def _admin_user() -> dict:
    return {"id": _u(), "role": "ADMIN", "is_admin": True}


def _hr_user(uid: str) -> dict:
    return {"id": uid, "role": "HR", "is_admin": False}


class PetsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        # Both the cases module (for _assert_case_access) and the pets module
        # call into main_db.engine. Patch them both so they share our SQLite.
        self.cases_engine_patcher = mock.patch.object(
            cases_module.main_db, "engine", self.engine
        )
        self.pets_engine_patcher = mock.patch.object(
            pets_module.main_db, "engine", self.engine
        )
        self.cases_engine_patcher.start()
        self.pets_engine_patcher.start()
        self.addCleanup(self.cases_engine_patcher.stop)
        self.addCleanup(self.pets_engine_patcher.stop)

        self.company_id = _u()
        self.employee_id = _u()
        self.case_id = _u()
        self._insert_profile(self.employee_id, "emp@example.com", self.company_id)
        self._insert_case(self.case_id, self.company_id, self.employee_id)

    # ── helpers ────────────────────────────────────────────────────────────

    def _insert_profile(self, pid: str, email: str, company_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, email, full_name, company_id) "
                     "VALUES (:id, :e, :n, :c)"),
                {"id": pid, "e": email, "n": "User", "c": company_id},
            )

    def _insert_case(self, cid: str, company_id: str, employee_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id, hr_owner_id) "
                     "VALUES (:id, :c, :e, NULL)"),
                {"id": cid, "c": company_id, "e": employee_id},
            )

    # ── tests ──────────────────────────────────────────────────────────────

    def test_list_empty_returns_empty_list(self) -> None:
        result = list_pets(self.case_id, user=_emp_user(self.employee_id))
        self.assertEqual(result, [])

    def test_create_then_list_returns_one_pet(self) -> None:
        created = create_pet(
            self.case_id,
            PetCreate(species="dog", name="Rex", breed="Labrador"),
            user=_emp_user(self.employee_id),
        )
        self.assertEqual(created.species, "dog")
        self.assertEqual(created.name, "Rex")
        self.assertEqual(created.case_id, self.case_id)

        listed = list_pets(self.case_id, user=_emp_user(self.employee_id))
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, created.id)

    def test_create_two_pets_on_same_case_succeeds(self) -> None:
        # Validation criterion 2: multiple pets per case_id supported.
        a = create_pet(
            self.case_id, PetCreate(species="dog", name="Rex"),
            user=_emp_user(self.employee_id),
        )
        b = create_pet(
            self.case_id, PetCreate(species="cat", name="Whiskers"),
            user=_emp_user(self.employee_id),
        )
        listed = list_pets(self.case_id, user=_emp_user(self.employee_id))
        self.assertEqual(len(listed), 2)
        self.assertEqual({p.id for p in listed}, {a.id, b.id})

    def test_delete_one_pet_leaves_the_other(self) -> None:
        # Validation criterion 3.
        a = create_pet(
            self.case_id, PetCreate(species="dog", name="Rex"),
            user=_emp_user(self.employee_id),
        )
        b = create_pet(
            self.case_id, PetCreate(species="cat", name="Whiskers"),
            user=_emp_user(self.employee_id),
        )
        response = delete_pet(self.case_id, a.id, user=_emp_user(self.employee_id))
        self.assertEqual(response.status_code, 204)

        remaining = list_pets(self.case_id, user=_emp_user(self.employee_id))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, b.id)

    def test_update_pet_changes_fields_and_keeps_others(self) -> None:
        created = create_pet(
            self.case_id,
            PetCreate(species="dog", name="Rex", breed="Lab", microchip_number="123"),
            user=_emp_user(self.employee_id),
        )
        updated = update_pet(
            self.case_id, created.id,
            PetPatch(breed="Golden Retriever"),
            user=_emp_user(self.employee_id),
        )
        self.assertEqual(updated.breed, "Golden Retriever")
        self.assertEqual(updated.name, "Rex")  # untouched
        self.assertEqual(updated.microchip_number, "123")
        self.assertEqual(updated.species, "dog")

    def test_update_unknown_pet_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            update_pet(
                self.case_id, _u(),
                PetPatch(breed="x"),
                user=_emp_user(self.employee_id),
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_unknown_pet_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            delete_pet(self.case_id, _u(), user=_emp_user(self.employee_id))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_without_species_returns_400(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_pet(
                self.case_id, PetCreate(species="", name="Nameless"),
                user=_emp_user(self.employee_id),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_employee_cannot_read_another_employees_case(self) -> None:
        # Validation criterion 5: RLS-style access enforcement.
        other_employee = _u()
        other_company = _u()
        other_case = _u()
        self._insert_profile(other_employee, "other@example.com", other_company)
        self._insert_case(other_case, other_company, other_employee)

        with self.assertRaises(HTTPException) as ctx:
            list_pets(other_case, user=_emp_user(self.employee_id))
        # Either 403 (case exists, not yours) or 404 — our helper returns 403.
        self.assertIn(ctx.exception.status_code, (403, 404))

    def test_hr_in_same_company_can_list_pets(self) -> None:
        hr_id = _u()
        self._insert_profile(hr_id, "hr@example.com", self.company_id)
        create_pet(
            self.case_id, PetCreate(species="dog", name="Rex"),
            user=_emp_user(self.employee_id),
        )
        # HR user belongs to the same company → should see the pets.
        listed = list_pets(self.case_id, user=_hr_user(hr_id))
        self.assertEqual(len(listed), 1)

    def test_vaccinations_round_trip_as_array(self) -> None:
        vacc = [{"name": "rabies", "date": "2025-03-01", "expiry": "2026-03-01"}]
        created = create_pet(
            self.case_id,
            PetCreate(species="dog", name="Rex", vaccinations=vacc),
            user=_emp_user(self.employee_id),
        )
        self.assertEqual(created.vaccinations, vacc)
        listed = list_pets(self.case_id, user=_emp_user(self.employee_id))
        self.assertEqual(listed[0].vaccinations, vacc)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

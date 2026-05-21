"""
Tests for the [P1-5] dossier endpoint: GET /api/cases/{case_id}/forms.

Pattern matches test_trigger_engine.py: in-memory SQLite engine with the
needed table shapes, mock `main_db.engine`, call the router function
directly to bypass FastAPI DI.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases as cases_module  # noqa: E402
from backend.app.routers.cases import list_case_forms  # noqa: E402
from fastapi import HTTPException  # noqa: E402


# SQLite schema mirroring the Postgres tables (no schema prefix; jsonb→TEXT).
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
CREATE TABLE case_dependents (
  id            TEXT PRIMARY KEY,
  case_id       TEXT NOT NULL,
  relationship  TEXT NOT NULL,
  full_name     TEXT
);
CREATE TABLE form_templates (
  id              TEXT PRIMARY KEY,
  code            TEXT NOT NULL,
  name            TEXT NOT NULL,
  country         TEXT NOT NULL,
  authority_code  TEXT,
  authority_name  TEXT,
  category        TEXT,
  version         TEXT NOT NULL DEFAULT '1.0.0',
  fields          TEXT NOT NULL DEFAULT '[]',
  trigger_rules   TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE case_forms (
  id                TEXT PRIMARY KEY,
  case_id           TEXT NOT NULL,
  form_template_id  TEXT NOT NULL,
  person_id         TEXT,
  dependent_id      TEXT,
  status            TEXT NOT NULL DEFAULT 'not_started',
  completion_pct    INTEGER NOT NULL DEFAULT 0,
  deadline          TEXT,
  deadline_trigger  TEXT,
  blocker_form_id   TEXT,
  original_file_url TEXT,
  draft_pdf_url     TEXT,
  submitted_at      TEXT,
  receipt_ref       TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
  id            TEXT PRIMARY KEY,
  case_form_id  TEXT NOT NULL,
  field_id      TEXT NOT NULL,
  value         TEXT,
  filled_by     TEXT NOT NULL,
  ai_confidence REAL,
  reviewed      INTEGER NOT NULL DEFAULT 0,
  overridden    INTEGER NOT NULL DEFAULT 0,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
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


class CaseDossierFormsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        # The router uses main_db.engine (legacy alias in cases.py) but the
        # actual underlying module is backend.database, same as elsewhere.
        self.engine_patcher = mock.patch.object(cases_module.main_db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

        # Seed a baseline case + employee profile
        self.company_id = _u()
        self.employee_id = _u()
        self.case_id = _u()
        self._insert_profile(self.employee_id, "employee@example.com", "Employee Doe", self.company_id)
        self._insert_case(self.case_id, self.company_id, self.employee_id)

    # ── helpers ────────────────────────────────────────────────────────────

    def _insert_profile(self, pid: str, email: str, full_name: str, company_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, email, full_name, company_id) "
                     "VALUES (:id, :e, :n, :c)"),
                {"id": pid, "e": email, "n": full_name, "c": company_id},
            )

    def _insert_case(self, cid: str, company_id: str, employee_id: str,
                     hr_owner_id: str = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id, hr_owner_id) "
                     "VALUES (:id, :c, :e, :h)"),
                {"id": cid, "c": company_id, "e": employee_id, "h": hr_owner_id},
            )

    def _insert_template(self, *, code: str, name: str = None, country: str = "NO",
                         authority_code: str = "UDI", category: str = "work_permit",
                         fields: list = None) -> str:
        tid = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO form_templates "
                     "(id, code, name, country, authority_code, category, fields) "
                     "VALUES (:id, :code, :name, :country, :ac, :cat, :fields)"),
                {
                    "id": tid, "code": code, "name": name or code,
                    "country": country, "ac": authority_code, "cat": category,
                    "fields": json.dumps(fields or [
                        {"id": "first_name", "label": "First name"},
                        {"id": "last_name",  "label": "Last name"},
                        {"id": "dob",        "label": "Date of birth"},
                    ]),
                },
            )
        return tid

    def _insert_case_form(self, *, template_id: str, status: str = "not_started",
                          person_id: str = None, dependent_id: str = None,
                          blocker_form_id: str = None, completion_pct: int = 0) -> str:
        cf_id = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO case_forms "
                    "(id, case_id, form_template_id, person_id, dependent_id, "
                    " status, completion_pct, blocker_form_id) "
                    "VALUES (:id, :case_id, :tid, :pid, :did, :st, :pct, :blocker)"
                ),
                {
                    "id": cf_id, "case_id": self.case_id, "tid": template_id,
                    "pid": person_id, "did": dependent_id,
                    "st": status, "pct": completion_pct, "blocker": blocker_form_id,
                },
            )
        return cf_id

    def _insert_dependent(self, relationship: str, full_name: str = "") -> str:
        dep_id = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_dependents (id, case_id, relationship, full_name) "
                     "VALUES (:id, :cid, :rel, :name)"),
                {"id": dep_id, "cid": self.case_id, "rel": relationship, "name": full_name},
            )
        return dep_id

    def _insert_field_value(self, case_form_id: str, field_id: str,
                            filled_by: str, value: str = "x",
                            reviewed: bool = False, overridden: bool = False) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO case_form_field_values "
                    "(id, case_form_id, field_id, value, filled_by, reviewed, overridden) "
                    "VALUES (:id, :cfid, :fid, :v, :fb, :r, :o)"
                ),
                {
                    "id": _u(), "cfid": case_form_id, "fid": field_id,
                    "v": value, "fb": filled_by,
                    "r": 1 if reviewed else 0, "o": 1 if overridden else 0,
                },
            )

    # ── tests ──────────────────────────────────────────────────────────────

    def test_employee_owns_case_empty_list(self) -> None:
        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        self.assertEqual(result, [])

    def test_returns_form_with_template_summary(self) -> None:
        tid = self._insert_template(code="UTL-2011", name="Work permit", country="NO")
        cf_id = self._insert_case_form(template_id=tid, person_id=self.employee_id, status="auto_filled")

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row.id, cf_id)
        self.assertEqual(row.case_id, self.case_id)
        self.assertEqual(row.status, "auto_filled")
        self.assertEqual(row.template.code, "UTL-2011")
        self.assertEqual(row.template.country, "NO")
        self.assertEqual(row.template.fields_total, 3)
        self.assertEqual(row.person.kind, "employee")
        self.assertEqual(row.person.name, "Employee Doe")
        self.assertEqual(row.person.profile_id, self.employee_id)

    def test_dependent_person_resolution_spouse(self) -> None:
        spouse_id = self._insert_dependent("spouse", "Test Spouse")
        tid = self._insert_template(code="UTL-2011F", category="family")
        self._insert_case_form(template_id=tid, dependent_id=spouse_id)

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        self.assertEqual(result[0].person.kind, "spouse")
        self.assertEqual(result[0].person.name, "Test Spouse")
        self.assertEqual(result[0].person.dependent_id, spouse_id)
        self.assertIsNone(result[0].person.profile_id)

    def test_dependent_person_resolution_child(self) -> None:
        child_id = self._insert_dependent("child", "Test Child")
        tid = self._insert_template(code="UTL-2011B", category="family")
        self._insert_case_form(template_id=tid, dependent_id=child_id)

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        self.assertEqual(result[0].person.kind, "child")
        self.assertEqual(result[0].person.name, "Test Child")

    def test_fields_summary_counts(self) -> None:
        tid = self._insert_template(code="GP-7-04", fields=[
            {"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"},
        ])
        cf_id = self._insert_case_form(template_id=tid, person_id=self.employee_id)
        self._insert_field_value(cf_id, "a", filled_by="ai", reviewed=True)
        self._insert_field_value(cf_id, "b", filled_by="ai")
        self._insert_field_value(cf_id, "c", filled_by="employee", overridden=True)
        # field 'd' has no value → counted as missing_required

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        s = result[0].fields_summary
        self.assertEqual(s.total, 4)
        self.assertEqual(s.filled_by_ai, 2)
        self.assertEqual(s.filled_by_human, 1)
        self.assertEqual(s.reviewed, 1)
        self.assertEqual(s.overridden, 1)
        self.assertEqual(s.missing_required, 1)  # 4 total - 2 ai - 1 human

    def test_blocker_form_id_resolves_to_code(self) -> None:
        gp = self._insert_template(code="GP-7-04")
        helfo = self._insert_template(code="HELFO-1")
        gp_cf = self._insert_case_form(template_id=gp, person_id=self.employee_id)
        self._insert_case_form(
            template_id=helfo, person_id=self.employee_id, blocker_form_id=gp_cf,
            status="blocked",
        )

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        # blocked-status form is sorted first
        helfo_summary = next(r for r in result if r.template.code == "HELFO-1")
        self.assertEqual(helfo_summary.blocker_form_id, gp_cf)
        self.assertEqual(helfo_summary.blocker_form_code, "GP-7-04")

    def test_status_filter_narrows_results(self) -> None:
        t1 = self._insert_template(code="A")
        t2 = self._insert_template(code="B")
        self._insert_case_form(template_id=t1, person_id=self.employee_id, status="ready")
        self._insert_case_form(template_id=t2, person_id=self.employee_id, status="submitted")

        ready = list_case_forms(
            case_id=self.case_id, status="ready", user=_emp_user(self.employee_id)
        )
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].template.code, "A")

    def test_ordering_ui_blocked_first_then_status_priority(self) -> None:
        # 'blocked' is NOT a document_status enum value — it's a UI concept
        # derived from blocker_form_id being set. We model that here.
        t_ready   = self._insert_template(code="READY")
        t_pending = self._insert_template(code="PENDING")
        t_gp      = self._insert_template(code="GP-7-04")
        t_helfo   = self._insert_template(code="HELFO-1")

        # GP-7-04 is the blocker for HELFO-1
        gp_cf = self._insert_case_form(template_id=t_gp, person_id=self.employee_id, status="auto_filled")
        # HELFO-1 has a blocker → should sort first
        self._insert_case_form(
            template_id=t_helfo, person_id=self.employee_id,
            status="not_started", blocker_form_id=gp_cf,
        )
        self._insert_case_form(template_id=t_ready,   person_id=self.employee_id, status="ready")
        self._insert_case_form(template_id=t_pending, person_id=self.employee_id, status="pending_doc")

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_emp_user(self.employee_id)
        )
        codes = [r.template.code for r in result]
        # HELFO-1 (UI-blocked) first; then status-priority for the rest:
        # pending_doc (1) → auto_filled (2) → ready (4)
        self.assertEqual(codes, ["HELFO-1", "PENDING", "GP-7-04", "READY"])

    def test_404_when_case_missing(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            list_case_forms(
                case_id=_u(), status=None, user=_emp_user(self.employee_id)
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_403_when_employee_does_not_own_case(self) -> None:
        other_employee_id = _u()
        self._insert_profile(other_employee_id, "other@example.com", "Other", self.company_id)
        with self.assertRaises(HTTPException) as ctx:
            list_case_forms(
                case_id=self.case_id, status=None, user=_emp_user(other_employee_id)
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_can_access_any_case(self) -> None:
        tid = self._insert_template(code="UTL-2011")
        self._insert_case_form(template_id=tid, person_id=self.employee_id)
        result = list_case_forms(
            case_id=self.case_id, status=None, user=_admin_user()
        )
        self.assertEqual(len(result), 1)

    def test_hr_with_matching_company_can_access(self) -> None:
        hr_id = _u()
        self._insert_profile(hr_id, "hr@example.com", "HR User", self.company_id)
        tid = self._insert_template(code="UTL-2011")
        self._insert_case_form(template_id=tid, person_id=self.employee_id)

        result = list_case_forms(
            case_id=self.case_id, status=None, user=_hr_user(hr_id)
        )
        self.assertEqual(len(result), 1)

    def test_hr_from_different_company_is_forbidden(self) -> None:
        other_company = _u()
        hr_id = _u()
        self._insert_profile(hr_id, "outside-hr@example.com", "Outside HR", other_company)
        with self.assertRaises(HTTPException) as ctx:
            list_case_forms(
                case_id=self.case_id, status=None, user=_hr_user(hr_id)
            )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()

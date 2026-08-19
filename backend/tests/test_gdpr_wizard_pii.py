"""AIQ-1842 — wizard_cases and wizard_employee_profiles must be exportable and erasable.

THE DEFECT. `gdpr.py` defined `_SUBJECT_TABLES` (12) and `_CASE_TABLES` (5), mirrored by
`_ERASURE_ACTIONS`. `grep wizard` across `gdpr.py` AND `immigration_gdpr.py` returned ZERO
matches, so two tables holding intake PII — including nationality — were in neither the
Art. 15 export nor the Art. 17 erasure. Measured in prod on 2026-08-13: `wizard_cases`
1,455 rows, 949 carrying `employeeProfile.nationality`; `wizard_employee_profiles` 511 rows,
all 511 carrying `primaryApplicant.nationality`.

WHY THEY WERE MISSED. Neither is keyed by the subject. `wizard_employee_profiles` is keyed
by `assignment_id` (-> `case_assignments.id`, 505/511 in prod; against
`case_assignments.case_id` it matches 0/511), and `wizard_cases` is keyed by its own id,
which IS a case id. A grep for `employee_user_id` or `employee_id` finds neither.

THE NOT NULL TRAP, which is why `redact_json` exists. `wizard_cases.draft_json` is
`text NOT NULL`. The obvious action — `("anon", ["draft_json"])`, matching
`relocation_cases: ("anon", ["profile_json"])` — renders `SET draft_json = NULL`, which
raises 23502. `_apply_erasure` runs each table in a SAVEPOINT, so that rollback would
surface only as a bare table name in `summary["errors"]` while the caller sees a successful
erasure overall. That is the AIQ-1801 defect reproduced on a new table, and
`test_wizard_cases_redaction_never_writes_null` is the guard against it.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.routers import gdpr  # noqa: E402

UID = "11111111-1111-1111-1111-111111111111"
CASE_ID = "case-abc"

# The 17 tables that were exportable/erasable BEFORE this change. Criterion 4 is that none
# of them moved; spelling them out is what makes a silent removal fail rather than pass.
_PRE_EXISTING_SUBJECT = [
    "profiles", "employees", "cases", "relocation_cases", "case_assignments",
    "employee_tasks", "quote_requests", "consent_records", "imm_employee_profiles",
    "support_tickets", "erasure_requests", "data_access_log",
]
_PRE_EXISTING_CASE = [
    "case_documents", "case_forms", "case_messages", "pets", "exception_requests",
]


class _Rows:
    def __init__(self, rows, mapping_rows=None):
        self._rows = rows
        self._mapping_rows = mapping_rows or []

    def fetchall(self):
        return self._rows

    def all(self):
        return self._rows

    def mappings(self):
        return iter(self._mapping_rows)

    def __iter__(self):
        return iter(self._rows)


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Conn:
    """Answers information_schema and serves seeded rows per table, recording every SQL."""

    def __init__(self, rows_by_table=None, columns_by_table=None, case_ids=(CASE_ID,)):
        self._rows = rows_by_table or {}
        self._columns = columns_by_table or {}
        self._case_ids = list(case_ids)
        self.statements = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if "information_schema.columns" in sql:
            table = (params or {}).get("t")
            return _Rows([(c,) for c in self._columns.get(table, [])])
        if "UNION" in sql and "FROM public.cases" in sql:  # _resolve_case_ids
            return _Rows([(c,) for c in self._case_ids])
        if sql.strip().upper().startswith("SELECT * FROM PUBLIC."):
            table = sql.split("FROM public.")[1].split(" ")[0]
            return _Rows([], self._rows.get(table, []))
        return _Rows([])

    def begin_nested(self):
        return _Ctx()

    # db.engine.begin()
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _statements_touching(conn, table, verb):
    return [s for s, _ in conn.statements
            if s.strip().upper().startswith(verb) and f"public.{table} " in f"{s} "]


def _predicate_for(tables, name):
    return next(where for t, where in tables if t == name)


# --------------------------------------------------------------- criteria 1, 2: export


class TestWizardTablesAreExported(unittest.TestCase):
    """Criteria 1 & 2 — a seeded row for the subject reaches the export payload."""

    def _export(self):
        conn = _Conn(rows_by_table={
            "wizard_cases": [{"id": CASE_ID, "draft_json": '{"employeeProfile":'
                                                           '{"nationality":"BR"}}'}],
            "wizard_employee_profiles": [{"assignment_id": "asg-1",
                                          "profile_json": '{"primaryApplicant":'
                                                          '{"nationality":"BR"}}'}],
        })
        fake_db = MagicMock()
        fake_db.engine.begin.return_value = conn
        with patch.object(gdpr, "db", fake_db):
            return gdpr.build_subject_export(UID), conn

    def test_wizard_cases_appears_in_the_export_payload(self) -> None:
        export, _ = self._export()
        self.assertIn("wizard_cases", export["tables"])
        self.assertIn("nationality", export["tables"]["wizard_cases"][0]["draft_json"])

    def test_wizard_employee_profiles_appears_in_the_export_payload(self) -> None:
        export, _ = self._export()
        self.assertIn("wizard_employee_profiles", export["tables"])
        self.assertIn(
            "nationality", export["tables"]["wizard_employee_profiles"][0]["profile_json"]
        )

    def test_wizard_employee_profiles_is_scoped_through_the_subjects_assignments(self) -> None:
        """It must resolve via case_assignments.id — NOT case_assignments.case_id, which
        matches 0 of 511 rows in prod."""
        where = _predicate_for(gdpr._SUBJECT_TABLES, "wizard_employee_profiles")
        self.assertIn("case_assignments", where)
        self.assertIn("employee_user_id::text = :uid", where)
        self.assertIn("SELECT id::text", where)
        self.assertNotIn("case_id::text", where)

    def test_wizard_cases_is_scoped_by_the_subjects_case_ids(self) -> None:
        where = _predicate_for(gdpr._CASE_TABLES, "wizard_cases")
        self.assertEqual(where, "id::text = ANY(:case_ids)")

    def test_a_subject_with_no_cases_still_exports_without_error(self) -> None:
        """_CASE_TABLES is skipped when case-id resolution yields nothing."""
        conn = _Conn(rows_by_table={}, case_ids=[])
        fake_db = MagicMock()
        fake_db.engine.begin.return_value = conn
        with patch.object(gdpr, "db", fake_db):
            export = gdpr.build_subject_export(UID)
        self.assertNotIn("wizard_cases", export["tables"])
        self.assertEqual(_statements_touching(conn, "wizard_cases", "SELECT"), [])


# ------------------------------------------------------------------ criterion 3: erasure


class TestWizardTablesAreErased(unittest.TestCase):
    """Criterion 3 — erasure removes or redacts the PII in both."""

    def _apply(self, table, where, params, columns):
        conn = _Conn(columns_by_table={table: columns})
        summary = {"erased_tables": [], "anonymised_tables": [], "retained_tables": [],
                   "errors": [], "skipped_columns": []}
        gdpr._apply_erasure(conn, table, where, params, summary)
        return conn, summary

    def test_wizard_employee_profiles_row_is_deleted(self) -> None:
        conn, summary = self._apply(
            "wizard_employee_profiles",
            _predicate_for(gdpr._SUBJECT_TABLES, "wizard_employee_profiles"),
            {"uid": UID},
            ["assignment_id", "profile_json", "updated_at"],
        )
        deletes = _statements_touching(conn, "wizard_employee_profiles", "DELETE")
        self.assertEqual(len(deletes), 1)
        self.assertIn("wizard_employee_profiles", summary["erased_tables"])
        self.assertEqual(summary["errors"], [])

    def test_wizard_cases_pii_blobs_are_redacted(self) -> None:
        conn, summary = self._apply(
            "wizard_cases", "id::text = ANY(:case_ids)", {"case_ids": [CASE_ID]},
            ["id", "draft_json", "family_details", "status", "dest_country"],
        )
        updates = _statements_touching(conn, "wizard_cases", "UPDATE")
        self.assertEqual(len(updates), 1)
        sql = updates[0]
        self.assertIn("draft_json = '{}'", sql)
        self.assertIn("family_details = '{}'", sql)
        self.assertIn("wizard_cases", summary["anonymised_tables"])
        self.assertEqual(summary["errors"], [])

    def test_wizard_cases_redaction_never_writes_null(self) -> None:
        """THE test. draft_json is `text NOT NULL`, so `SET draft_json = NULL` raises
        23502, the SAVEPOINT rolls the table back, and the erasure is silently skipped —
        AIQ-1801 on a new table. This fails the moment the action is switched to `anon`.
        """
        conn, _ = self._apply(
            "wizard_cases", "id::text = ANY(:case_ids)", {"case_ids": [CASE_ID]},
            ["id", "draft_json", "family_details"],
        )
        sql = _statements_touching(conn, "wizard_cases", "UPDATE")[0]
        self.assertNotIn("NULL", sql.upper(), "a NOT NULL blob must not be set to NULL")

    def test_wizard_cases_keeps_its_non_pii_skeleton(self) -> None:
        """Redact, don't delete: case_feedback/case_participants/case_evidence all
        FK-reference wizard_cases, and the corridor/status columns are operational."""
        conn, _ = self._apply(
            "wizard_cases", "id::text = ANY(:case_ids)", {"case_ids": [CASE_ID]},
            ["id", "draft_json", "family_details", "status", "dest_country"],
        )
        self.assertEqual(_statements_touching(conn, "wizard_cases", "DELETE"), [])
        sql = _statements_touching(conn, "wizard_cases", "UPDATE")[0]
        for kept in ("status", "dest_country"):
            self.assertNotIn(f"{kept} = ", sql)

    def test_redaction_survives_column_drift(self) -> None:
        """Reuses _erasable_columns, so one renamed blob must not cost the other."""
        conn, summary = self._apply(
            "wizard_cases", "id::text = ANY(:case_ids)", {"case_ids": [CASE_ID]},
            ["id", "draft_json"],  # family_details gone
        )
        sql = _statements_touching(conn, "wizard_cases", "UPDATE")[0]
        self.assertIn("draft_json = '{}'", sql)
        self.assertNotIn("family_details", sql)
        self.assertIn("wizard_cases.family_details", summary["skipped_columns"])

    def test_a_fully_stale_redaction_list_is_an_error_not_a_success(self) -> None:
        conn, summary = self._apply(
            "wizard_cases", "id::text = ANY(:case_ids)", {"case_ids": [CASE_ID]},
            ["id", "status"],  # both blobs gone
        )
        self.assertIn("wizard_cases", summary["errors"])
        self.assertNotIn("wizard_cases", summary["anonymised_tables"])
        self.assertEqual(_statements_touching(conn, "wizard_cases", "UPDATE"), [])


# --------------------------------------------------- criteria 4, 5: the regression guard


class TestTheSetsAreNotSilentlyReduced(unittest.TestCase):
    """Criterion 5 — a test fails if either table is dropped from the set again.
    Criterion 4 — the pre-existing 17 tables are unchanged."""

    def test_wizard_tables_are_in_the_export_sets(self) -> None:
        self.assertIn("wizard_employee_profiles", [t for t, _ in gdpr._SUBJECT_TABLES])
        self.assertIn("wizard_cases", [t for t, _ in gdpr._CASE_TABLES])

    def test_wizard_tables_have_an_erasure_action(self) -> None:
        self.assertEqual(gdpr._ERASURE_ACTIONS["wizard_employee_profiles"], ("delete",))
        kind, cols = gdpr._ERASURE_ACTIONS["wizard_cases"]
        self.assertEqual(kind, "redact_json")
        self.assertIn("draft_json", cols)
        self.assertIn("family_details", cols)

    def test_the_pre_existing_seventeen_tables_are_untouched(self) -> None:
        subject = [t for t, _ in gdpr._SUBJECT_TABLES]
        case = [t for t, _ in gdpr._CASE_TABLES]
        for t in _PRE_EXISTING_SUBJECT:
            self.assertIn(t, subject, f"{t} was dropped from _SUBJECT_TABLES")
        for t in _PRE_EXISTING_CASE:
            self.assertIn(t, case, f"{t} was dropped from _CASE_TABLES")
        self.assertEqual(len(subject), len(_PRE_EXISTING_SUBJECT) + 1)
        self.assertEqual(len(case), len(_PRE_EXISTING_CASE) + 1)

    def test_every_exported_table_can_also_be_erased(self) -> None:
        """The invariant the module docstring claims: erasure removes exactly what the
        export exposes. This is what would have caught AIQ-1842 at the time."""
        for table, _ in gdpr._SUBJECT_TABLES + gdpr._CASE_TABLES:
            self.assertIn(table, gdpr._ERASURE_ACTIONS,
                          f"{table} is exported but has no erasure action")

    def test_every_redact_json_action_lists_at_least_one_column(self) -> None:
        for table, action in gdpr._ERASURE_ACTIONS.items():
            if action[0] == "redact_json":
                self.assertTrue(action[1], f"{table} names no columns to redact")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""AIQ-1801 — a stale column name must not silently cancel an Article 17 erasure.

THE DEFECT. `_ERASURE_ACTIONS["exception_requests"]` listed
`["reason", "resolution_notes", "ai_insight"]`, and `ai_insight` does not exist on the
table. The whole list is rendered into ONE `UPDATE ... SET a = NULL, b = NULL, c = NULL`,
so the single bad name made the statement raise, the SAVEPOINT rolled it back, and
`reason` and `resolution_notes` — case-linked free text belonging to the data subject —
were never erased. The failure surfaced only as a bare table name in `summary["errors"]`.

WHY THE EXISTING TESTS DID NOT CATCH IT, and why this file exists separately:
`test_priv001b_erasure.py` runs in CI and passes, but drives the handler with a bare
`MagicMock()` connection. A MagicMock accepts any SQL and never raises, so a column that
does not exist is indistinguishable from one that does — the tests were structurally
incapable of seeing this class of bug. The double below actually answers
`information_schema`, which is the whole difference.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.routers import gdpr  # noqa: E402


class _Conn:
    """Connection double that answers information_schema and records every statement."""

    def __init__(self, columns_by_table):
        self._columns = columns_by_table
        self.statements = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if "information_schema.columns" in sql:
            table = (params or {}).get("t")
            return _Rows([(c,) for c in self._columns.get(table, [])])
        return _Rows([])

    # SAVEPOINT
    def begin_nested(self):
        return _Ctx()


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _updates_for(conn, table):
    return [s for s, _ in conn.statements
            if s.strip().upper().startswith("UPDATE") and f"public.{table} " in s]


class TestColumnDriftDoesNotCancelErasure(unittest.TestCase):
    TABLE = "exception_requests"

    def _apply(self, wanted, existing):
        conn = _Conn({self.TABLE: existing})
        summary = {"erased_tables": [], "anonymised_tables": [], "retained_tables": [],
                   "errors": [], "skipped_columns": []}
        with patch.dict(gdpr._ERASURE_ACTIONS, {self.TABLE: ("anon", wanted)}):
            gdpr._apply_erasure(conn, self.TABLE, "case_id = :cid", {"cid": "c1"}, summary)
        return conn, summary

    def test_the_columns_that_exist_are_still_erased(self) -> None:
        """THE test. One phantom name must not cost the other two."""
        conn, summary = self._apply(
            wanted=["reason", "resolution_notes", "ai_insight"],
            existing=["id", "case_id", "reason", "resolution_notes"],
        )
        updates = _updates_for(conn, self.TABLE)
        self.assertEqual(len(updates), 1, "the erasure UPDATE must still run")
        sql = updates[0]
        self.assertIn("reason = NULL", sql)
        self.assertIn("resolution_notes = NULL", sql)
        self.assertNotIn("ai_insight", sql, "the phantom column must not reach the SQL")
        self.assertIn(self.TABLE, summary["anonymised_tables"])

    def test_the_phantom_column_is_reported_not_hidden(self) -> None:
        """A partial erasure must be distinguishable from a complete one."""
        _, summary = self._apply(
            wanted=["reason", "resolution_notes", "ai_insight"],
            existing=["reason", "resolution_notes"],
        )
        self.assertIn(f"{self.TABLE}.ai_insight", summary["skipped_columns"])

    def test_a_fully_stale_list_is_an_error_not_a_success(self) -> None:
        """If NOTHING can be erased, reporting the table as anonymised would be the
        exact lie this change exists to prevent."""
        conn, summary = self._apply(
            wanted=["ai_insight", "also_gone"],
            existing=["id", "case_id"],
        )
        self.assertIn(self.TABLE, summary["errors"])
        self.assertNotIn(self.TABLE, summary["anonymised_tables"])
        # ...and no UPDATE was attempted at all, rather than one that erases nothing.
        self.assertEqual(_updates_for(conn, self.TABLE), [])
        self.assertIn(f"{self.TABLE}.ai_insight", summary["skipped_columns"])

    def test_a_clean_map_is_untouched(self) -> None:
        """No behaviour change when the map matches reality — the common case."""
        conn, summary = self._apply(
            wanted=["reason", "resolution_notes"],
            existing=["id", "reason", "resolution_notes"],
        )
        sql = _updates_for(conn, self.TABLE)[0]
        self.assertIn("reason = NULL", sql)
        self.assertIn("resolution_notes = NULL", sql)
        self.assertEqual(summary["skipped_columns"], [])
        self.assertEqual(summary["errors"], [])


class TestIntrospectionFailsOpen(unittest.TestCase):
    """Erasure must never be WEAKENED by an introspection problem.

    On SQLite — the CI engine — information_schema does not exist, and the older tests
    drive the handler with a MagicMock that answers nothing usable. In both cases the
    filter must step aside and let the original statement run, exactly as before.
    """

    def test_unavailable_information_schema_does_not_filter(self) -> None:
        conn = MagicMock()  # .execute().fetchall() yields a non-iterable Mock
        summary = {"skipped_columns": []}
        out = gdpr._erasable_columns(conn, "t", ["a", "b"], summary)
        self.assertEqual(out, ["a", "b"], "must fall back to the requested columns")
        self.assertEqual(summary["skipped_columns"], [])

    def test_an_empty_column_set_is_treated_as_unknown_not_as_all_missing(self) -> None:
        """A table we cannot introspect must not look like a table with no columns —
        that would drop every column and erase nothing."""
        conn = _Conn({})  # information_schema returns zero rows for this table
        self.assertIsNone(gdpr._existing_columns(conn, "unknown_table"))


class TestTheSpecificDefectIsFixed(unittest.TestCase):
    def test_ai_insight_is_no_longer_in_the_erasure_map(self) -> None:
        action = gdpr._ERASURE_ACTIONS["exception_requests"]
        self.assertEqual(action[0], "anon")
        self.assertNotIn("ai_insight", action[1])
        # ...and the two real ones are still there — removing the phantom must not have
        # quietly removed the obligation with it.
        self.assertIn("reason", action[1])
        self.assertIn("resolution_notes", action[1])

    def test_every_anon_action_lists_at_least_one_column(self) -> None:
        for table, action in gdpr._ERASURE_ACTIONS.items():
            if action[0] in ("anon", "retain_null"):
                self.assertTrue(action[1], f"{table} names no columns to erase")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

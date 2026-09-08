"""Regression test for e2e_purge.guarded() — the psycopg2 `%` trap.

`guarded()` must NOT pass an empty tuple when there are no params. `params or ()`
(an empty tuple) still puts psycopg2 into %-interpolation mode, which chokes on a
literal `%` in the SQL — e.g. the ILIKE patterns in TEST_EMAIL_PREDICATE
('%@testco.com') used by the public.users / auth.users cleanup — raising
`IndexError: tuple index out of range` and failing the auto-delete teardown.
"""
import importlib.util
import pathlib
import sys
import types
import unittest

# Stub psycopg2 so importing the script doesn't sys.exit when it isn't installed.
if "psycopg2" not in sys.modules:
    _pg = types.ModuleType("psycopg2")

    class _Err(Exception):
        pgcode = None

    _pg.Error = _Err
    sys.modules["psycopg2"] = _pg

_PATH = pathlib.Path(__file__).resolve().parents[1] / "e2e_purge.py"
_spec = importlib.util.spec_from_file_location("e2e_purge", _PATH)
e2e_purge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e_purge)


class RecordingCursor:
    def __init__(self):
        self.calls = []
        self.rowcount = 0

    def execute(self, sql, *args):
        self.calls.append((sql, args))


class GuardedParamsTest(unittest.TestCase):
    def _delete_call(self, cur):
        return [c for c in cur.calls if "DELETE" in c[0]]

    def test_no_params_executes_without_a_param_arg(self):
        # A literal % (ILIKE) with no params must run as execute(sql) — NO param arg —
        # or psycopg2 %-interpolates and raises IndexError.
        cur = RecordingCursor()
        e2e_purge.guarded(cur, "DELETE FROM users WHERE email ILIKE '%@testco.com'")
        calls = self._delete_call(cur)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], (), "DELETE with no params must be execute(sql) with no param arg")

    def test_with_params_still_binds_them(self):
        cur = RecordingCursor()
        e2e_purge.guarded(cur, "DELETE FROM t WHERE id = ANY(%s)", (["a"],))
        calls = self._delete_call(cur)
        self.assertEqual(calls[0][1], ((["a"],),), "params must be passed through to execute")


class CanonicalAwarePurgeTest(unittest.TestCase):
    """[AIQ-1737·1] The purge must match case_assignments on canonical_case_id too, or a
    surviving assignment whose canonical points at a deleted case is left dangling."""

    def test_case_assignments_delete_matches_canonical(self):
        where = e2e_purge._case_child_where("case_assignments", "case_id", "case")
        self.assertIn("canonical_case_id", where, "case_assignments purge must consider canonical_case_id")
        self.assertIn("case_id", where)

    def test_assignment_scoped_children_resolve_canonical_aware(self):
        # A src='assignment' child selects assignment ids via case_assignments — that
        # sub-select must also match canonical, else children of a canonical-only match survive.
        where = e2e_purge._case_child_where("employee_answers", "assignment_id", "assignment")
        self.assertIn("canonical_case_id", where)
        self.assertIn("case_assignments", where)

    def test_plain_case_children_unchanged(self):
        # Tables without a canonical column keep the simple case_id match (no regression).
        where = e2e_purge._case_child_where("case_forms", "case_id", "case")
        self.assertEqual(where, "case_id::text = ANY(%s)")

    def test_ids_subquery_binds_single_param(self):
        # The canonical-aware predicate must still bind exactly ONE %s (the case-id array),
        # so the existing (case_ids,) call sites are unchanged.
        self.assertEqual(e2e_purge._ASSIGNMENT_CASE_MATCH.count("%s"), 1)


if __name__ == "__main__":
    unittest.main()

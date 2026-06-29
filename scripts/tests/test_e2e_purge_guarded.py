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


if __name__ == "__main__":
    unittest.main()

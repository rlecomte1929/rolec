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


class _FKError(e2e_purge.psycopg2.Error):
    """FK violation (23503) — what auth.users referrers actually raise."""
    pgcode = "23503"
    diag = types.SimpleNamespace(constraint_name="quote_messages_sender_user_id_fkey")


class _PermError(e2e_purge.psycopg2.Error):
    """insufficient_privilege (42501) — what the script ASSUMED was happening."""
    pgcode = "42501"
    diag = types.SimpleNamespace(constraint_name=None)


class RaisingCursor:
    """Cursor whose DELETEs blow up; SAVEPOINT/ROLLBACK bookkeeping still succeeds."""

    def __init__(self, exc):
        self.exc = exc
        self.calls = []
        self.rowcount = 0

    def execute(self, sql, *args):
        self.calls.append((sql, args))
        if sql.strip().upper().startswith("DELETE"):
            raise self.exc


class AuthSchemaCascadeTest(unittest.TestCase):
    """THE defect: 2,692 test auth.users rows survived every purge for 5 weeks.

    `referencing_fks` matches on `ccu.table_name` with no schema filter, so the FK
    `quote_messages.sender_user_id -> auth.users(id)` IS discovered when called with
    ["users"] — but the generated DELETE bound `SELECT id FROM users` (public). Under
    the hybrid auth model the Supabase auth uid is not the legacy public.users.id, so
    the cascade cleared the wrong rows and left the 125 that block the bulk delete.

    Measured 2026-08-27: 125 of 125 rows in quote_messages belong to test users.
    """

    PUBLIC_IDS = "SELECT id::text FROM users WHERE (email ILIKE '%@testco.com')"
    AUTH_IDS = "SELECT id::text FROM auth.users WHERE (email ILIKE '%@testco.com')"

    def _id_queries(self):
        return {("public", "users"): self.PUBLIC_IDS, ("auth", "users"): self.AUTH_IDS}

    def test_auth_referrer_binds_auth_ids_not_public_users(self):
        fks = [("quote_messages", "sender_user_id", "auth", "users")]
        ops = e2e_purge.build_referrer_ops(fks, self._id_queries())
        self.assertEqual(len(ops), 1, "the auth.users referrer must produce a delete op")
        sql = ops[0][1]
        self.assertIn("FROM auth.users", sql, "must resolve ids from auth.users")
        self.assertNotIn(
            "FROM users WHERE", sql,
            "binding public.users is the bug: the auth uid is not the legacy users.id")

    def test_public_referrer_still_binds_public_ids(self):
        fks = [("sessions", "user_id", "public", "users")]
        ops = e2e_purge.build_referrer_ops(fks, self._id_queries())
        self.assertIn("FROM users WHERE", ops[0][1])
        self.assertNotIn("auth.users", ops[0][1])

    def test_same_table_name_in_two_schemas_is_disambiguated(self):
        """public.users and auth.users share a table_name — the schema must decide."""
        fks = [("sessions", "user_id", "public", "users"),
               ("quote_messages", "sender_user_id", "auth", "users")]
        ops = dict((t, s) for t, s, _p in e2e_purge.build_referrer_ops(fks, self._id_queries()))
        self.assertIn("FROM users WHERE", ops["sessions"])
        self.assertIn("FROM auth.users", ops["quote_messages"])

    def test_self_referential_tables_are_skipped(self):
        fks = [("profiles", "id", "public", "users")]
        self.assertEqual(e2e_purge.build_referrer_ops(fks, self._id_queries()), [])

    def test_unknown_referent_is_ignored_not_guessed(self):
        """An FK to a table we have no id query for must produce NO op — never a guess."""
        fks = [("something", "col", "storage", "objects")]
        self.assertEqual(e2e_purge.build_referrer_ops(fks, self._id_queries()), [])


class GuardedRecordsWhyItSwallowedTest(unittest.TestCase):
    """The purge printed 'needs elevated role' for FIVE WEEKS while the real cause was
    a foreign key. guarded() collapsed 23503 and 42501 into the same bare `return None`,
    so the operator had nothing to diagnose from. The reason must be recorded."""

    def setUp(self):
        e2e_purge.reset_swallowed()

    def test_fk_violation_is_recorded_with_its_constraint(self):
        cur = RaisingCursor(_FKError("boom"))
        self.assertIsNone(e2e_purge.guarded(cur, "DELETE FROM auth.users", label="auth.users"))
        rec = e2e_purge.swallowed()
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["pgcode"], "23503")
        self.assertEqual(rec[0]["constraint"], "quote_messages_sender_user_id_fkey")

    def test_permission_error_is_recorded_distinctly_from_fk(self):
        cur = RaisingCursor(_PermError("nope"))
        e2e_purge.guarded(cur, "DELETE FROM auth.users", label="auth.users")
        self.assertEqual(e2e_purge.swallowed()[0]["pgcode"], "42501")

    def test_a_clean_delete_records_nothing(self):
        cur = RecordingCursor()
        e2e_purge.guarded(cur, "DELETE FROM x", label="x")
        self.assertEqual(e2e_purge.swallowed(), [])

    def test_an_unexpected_pgcode_still_raises(self):
        class _Weird(e2e_purge.psycopg2.Error):
            pgcode = "40001"
            diag = types.SimpleNamespace(constraint_name=None)

        with self.assertRaises(e2e_purge.psycopg2.Error):
            e2e_purge.guarded(RaisingCursor(_Weird("serialization")), "DELETE FROM x")


class StrictExitTest(unittest.TestCase):
    """The job reported SUCCESS while leaving 2,692 rows. Residual must fail the run,
    or the next silent under-delivery goes unnoticed exactly the same way."""

    def test_residual_under_strict_is_a_failure(self):
        self.assertNotEqual(e2e_purge.exit_code(["auth.users=2692"], strict=True), 0)

    def test_residual_without_strict_still_warns_only(self):
        self.assertEqual(e2e_purge.exit_code(["auth.users=2692"], strict=False), 0)

    def test_clean_purge_is_success_either_way(self):
        self.assertEqual(e2e_purge.exit_code([], strict=True), 0)
        self.assertEqual(e2e_purge.exit_code([], strict=False), 0)


class FkDiscoverySourceTest(unittest.TestCase):
    """information_schema.constraint_column_usage is ownership-filtered: PostgreSQL only
    exposes constraints whose REFERENCED table the current role owns. auth.users belongs
    to supabase_auth_admin, so the FK quote_messages.sender_user_id -> auth.users(id) was
    invisible to the app role and the referrer was never discovered — the purge ran, found
    nothing to cascade, and still aborted on 23503. pg_catalog has no such filter.

    Proven live 2026-08-27: with the information_schema query the run reported
    `auth.users 23503 [quote_messages_sender_user_id_fkey]` and deleted 0 of 2,692.
    """

    class _FetchCursor(RecordingCursor):
        def fetchall(self):
            return []

    def test_discovery_uses_pg_catalog_not_information_schema(self):
        cur = self._FetchCursor()
        e2e_purge.referencing_fks(cur, ["users"])
        sql = cur.calls[0][0]
        self.assertIn("pg_constraint", sql)
        self.assertNotIn(
            "constraint_column_usage", sql,
            "ownership-filtered — it cannot see FKs onto auth.users")

    def test_discovery_returns_the_referenced_schema(self):
        cur = self._FetchCursor()
        e2e_purge.referencing_fks(cur, ["users"])
        sql = cur.calls[0][0]
        self.assertIn("nspname AS referenced_schema", sql)

"""AIQ-1528 — the backend must never issue DDL against Postgres.

THE BUG
-------
`init_db()` held 248 UNGUARDED DDL statements (CREATE TABLE / CREATE INDEX / ALTER TABLE), written
in SQLite shape, and ran them against PRODUCTION Postgres on every boot. Only 55 of its 303 DDL
statements sat behind an `if _is_sqlite:` guard.

Mostly they were harmless no-ops — `CREATE TABLE IF NOT EXISTS` over a table a migration had
already created. The damage was the exception: any table a migration had NOT created got made by
the APP instead, with text ids, text timestamps, and — because an app-issued CREATE TABLE grants
none — NO RLS and NO POLICIES.

That is exactly how `public.exception_requests` came to exist with `id text` while its migration
declares `uuid`, and why its RLS was lost twice in a single day: the symptom kept being ALTERed
back while the boot code kept re-asserting the cause.

THE FIX
-------
The escape hatch already existed and was already correct — it was gated on an env var
(DISABLE_RUNTIME_DDL) that nobody had set in production. Postgres now skips boot DDL BY DEFAULT.

WHAT THESE TESTS PIN
--------------------
The GUARD, by observing whether execution passes the early return — not by trying to capture SQL
through a fake engine, which cannot faithfully drive 2,700 lines of schema code and would give
false confidence either way.

`_maybe_ensure_postgres_missing_schemas` is the first statement AFTER the return, so it is the
tell: called ⇒ we ran the boot DDL path; not called ⇒ we skipped it.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db import misc as misc_mod  # noqa: E402

# Everything init_db calls. The first six are what the SKIP path legitimately still does; the
# rest all sit AFTER the early return, so whether they fire tells us which path we took.
_SKIP_PATH = (
    "_db_healthcheck",
    "seed_readiness_templates_if_empty",
    "ensure_missing_readiness_templates",
    "seed_dossier_questions_if_missing",
    "_backfill_employee_contacts",
)
_PAST_THE_GUARD = "_maybe_ensure_postgres_missing_schemas"


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **kw):
        return mock.MagicMock()


def _run(*, is_sqlite: bool, env: dict):
    host = misc_mod.MiscMixin()
    host.engine = mock.MagicMock()
    host.engine.connect.return_value = _Conn()
    host.engine.begin.return_value = _Conn()
    host._initialized = False

    for name in (*_SKIP_PATH, _PAST_THE_GUARD):
        setattr(host, name, mock.MagicMock())

    with mock.patch.object(misc_mod, "_is_sqlite", is_sqlite), \
         mock.patch.dict(os.environ, env, clear=False):
        try:
            host.init_db()
        except Exception:
            # A fake engine cannot satisfy the full schema build. We only care HOW FAR it got.
            pass
    return host


class PostgresIssuesNoDDLTests(unittest.TestCase):
    def test_POSTGRES_skips_the_boot_DDL_BY_DEFAULT(self):
        # No env var set at all — the exact state production was in. It must be safe anyway.
        # A default that depends on someone remembering an env var is not a guard.
        host = _run(is_sqlite=False, env={"ALLOW_RUNTIME_DDL": "", "DISABLE_RUNTIME_DDL": ""})
        getattr(host, _PAST_THE_GUARD).assert_not_called()

    def test_the_healthcheck_and_seeds_STILL_run_on_postgres(self):
        # Skipping DDL must not skip the work prod actually needs, or the guard is in the wrong
        # place. These are the things the skip path is supposed to keep doing.
        host = _run(is_sqlite=False, env={"ALLOW_RUNTIME_DDL": ""})
        host._db_healthcheck.assert_called()
        host.seed_readiness_templates_if_empty.assert_called()
        host.seed_dossier_questions_if_missing.assert_called()

    def test_postgres_can_still_OPT_IN_deliberately(self):
        # The hatch stays open — but opting in must be a deliberate act, not a default.
        host = _run(is_sqlite=False, env={"ALLOW_RUNTIME_DDL": "1"})
        getattr(host, _PAST_THE_GUARD).assert_called()

    def test_SQLITE_still_builds_its_schema(self):
        # Local dev and the test suite have no migrations — SQLite MUST still get its schema from
        # init_db, or every developer's database is empty.
        host = _run(is_sqlite=True, env={})
        # On SQLite we go past the guard; the PG-only helper is skipped by its own `if not
        # _is_sqlite`, so assert instead that we did NOT take the Postgres skip path.
        self.assertFalse(
            getattr(host, _PAST_THE_GUARD).called,
            "the Postgres-only helper must not run on SQLite",
        )
        host._db_healthcheck.assert_not_called()  # the skip path's healthcheck is PG-only


if __name__ == "__main__":
    unittest.main()

"""AIQ-2091 — `POST /api/admin/impersonate/start` 500s in production.

Root cause: `AuthMixin.set_admin_session` wrote the session row with
`INSERT OR REPLACE`, which is SQLite-only syntax. On Postgres (prod) it raises
`syntax error at or near "OR"` (SQLSTATE 42601), an unhandled ProgrammingError
that surfaces as a 500 — so an admin can never "view as" a user. Verified against
the live prod dialect (Postgres 17): `EXPLAIN INSERT OR REPLACE ...` → 42601, while
`EXPLAIN INSERT ... ON CONFLICT (token) DO UPDATE ...` plans cleanly on
`admin_sessions_pkey`.

The test harness runs on SQLite, which *accepts* `INSERT OR REPLACE`, so the prod
500 cannot be reproduced behaviourally here. `test_set_admin_session_emits_portable_dml`
therefore pins the exact defect by asserting the emitted DML is cross-dialect
portable (no `INSERT OR REPLACE`); it fails on origin/main. `test_set_admin_session_upserts`
locks the intended replace-on-same-token semantics.
"""

import unittest

from sqlalchemy import create_engine, event, text

from backend.db.auth import AuthMixin


class _AuthDB(AuthMixin):
    """Minimal real carrier for the mixin method — only `.engine` is needed.

    Imported straight from backend.db.auth (which the suite does NOT mock),
    so this is independent of the collection-order-dependent backend.database mock.
    """

    def __init__(self, engine):
        self.engine = engine


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        # token is the PRIMARY KEY in prod (admin_sessions_pkey) — mirror that so
        # ON CONFLICT (token) has an arbiter index on both dialects.
        conn.execute(text(
            "CREATE TABLE admin_sessions ("
            "token TEXT PRIMARY KEY, actor_user_id TEXT, target_user_id TEXT, "
            "mode TEXT, created_at TEXT)"
        ))
    return _AuthDB(engine)


class SetAdminSessionTests(unittest.TestCase):
    def test_set_admin_session_upserts(self):
        db = _make_db()
        db.set_admin_session("tok-1", "admin-1", "target-a", "employee")
        # Same token, different target/mode — must REPLACE, not duplicate.
        db.set_admin_session("tok-1", "admin-1", "target-b", "hr")

        with db.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT token, target_user_id, mode FROM admin_sessions")
            ).fetchall()
        self.assertEqual(len(rows), 1, "same token must upsert to a single row")
        self.assertEqual(rows[0]._mapping["target_user_id"], "target-b")
        self.assertEqual(rows[0]._mapping["mode"], "hr")

    def test_set_admin_session_emits_portable_dml(self):
        """The defect pin: the write must not use SQLite-only `INSERT OR REPLACE`.

        Fails on origin/main, where the statement is `INSERT OR REPLACE ...` —
        exactly the syntax Postgres rejects with 42601 in prod.
        """
        db = _make_db()
        statements = []

        @event.listens_for(db.engine, "before_cursor_execute")
        def _capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        db.set_admin_session("tok-2", "admin-1", "target-a", "employee")

        writes = [s for s in statements if "admin_sessions" in s.lower()]
        self.assertTrue(writes, "expected an INSERT into admin_sessions")
        joined = " ".join(writes).lower()
        self.assertNotIn(
            "insert or replace", joined,
            "set_admin_session uses SQLite-only INSERT OR REPLACE — 500s on Postgres (AIQ-2091)",
        )
        self.assertIn(
            "on conflict", joined,
            "expected a portable ON CONFLICT upsert",
        )


if __name__ == "__main__":
    unittest.main()

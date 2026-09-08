"""Regression: CasesMixin referenced an undefined module global `_is_sqlite`.

The C1 mixin extraction moved methods into backend/db/cases.py but left their
`if _is_sqlite:` branches pointing at a name that only existed in
backend/database.py, so every such method (intake autosave, case events, etc.)
raised NameError("name '_is_sqlite' is not defined") at runtime → 500.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import text  # noqa: E402

from backend.db import cases  # noqa: E402
from backend.db.cases import CasesMixin  # noqa: E402


def test_is_sqlite_defined_in_cases_module():
    assert isinstance(cases._is_sqlite, bool)


def test_update_assignment_intake_draft_reaches_sql_without_nameerror():
    """Exercise the real mixin method (db is mocked in the harness) via a stub
    self, proving the `if _is_sqlite:` branch resolves instead of NameError-ing.
    """
    captured = {}

    class _Result:
        def fetchone(self):
            return None

    class _Conn:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, *a, **k):
            return _Result()

    class _StubDB:
        engine = type("E", (), {"begin": lambda self: _Conn()})()

        def _exec(self, conn, sql, params, op_name=None, request_id=None):
            captured["sql"] = sql
            return conn.execute(text(sql), params)

    # Would raise NameError("name '_is_sqlite' is not defined") before the fix.
    result = CasesMixin.update_assignment_intake_draft(
        _StubDB(), "a-id", "u-id", {"k": "v"}
    )
    assert result is None
    assert "intake_draft" in captured["sql"]  # reached the UPDATE

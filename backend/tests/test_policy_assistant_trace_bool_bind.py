"""
OBS-1 (AIQ-1242) regression: insert_policy_assistant_trace must bind
`verification_skipped` as a real boolean (or NULL) — never an int.

`policy_assistant_traces.verification_skipped` is a Postgres `boolean` column.
Binding int 1/0 makes Postgres reject the INSERT ("column is of type boolean but
expression is of type integer"), and the tracer swallows that error at debug
level — so EVERY successful policy-assistant answer (which sets
verification_skipped=False) silently failed to persist a trace, while fallbacks
(verification_skipped=None → NULL) wrote fine. SQLite (the unit-test DB) accepts
int-into-boolean, so this is a Postgres-only failure; this test asserts the bound
*type* directly so it catches the regression without a live Postgres.
"""
from __future__ import annotations

import os
import sys
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.policies import PoliciesMixin  # noqa: E402


class _CapturingConn:
    """Captures the bind-parameter dict passed to conn.execute()."""

    def __init__(self) -> None:
        self.params: list = []

    def execute(self, statement, parameters=None):
        self.params.append(parameters)
        return None


class _CapturingEngine:
    def __init__(self, conn: _CapturingConn) -> None:
        self._conn = conn

    def begin(self):
        conn = self._conn

        class _Ctx:
            def __enter__(self):
                return conn

            def __exit__(self, *exc):
                return False

        return _Ctx()


class _Host(PoliciesMixin):
    """Minimal host exposing insert_policy_assistant_trace (uses only self.engine)."""

    def __init__(self, conn: _CapturingConn) -> None:
        self.engine = _CapturingEngine(conn)


def _bind_for(verification_skipped):
    conn = _CapturingConn()
    _Host(conn).insert_policy_assistant_trace(
        trace_id=str(uuid.uuid4()),
        session_id=None,
        query_hash="h",
        company_id="c",
        steps_json="[]",
        total_latency_ms=1,
        fallback_triggered=False,
        verification_skipped=verification_skipped,
        answer_kind="answer",
    )
    return conn.params[-1]


def test_verification_skipped_true_binds_boolean_not_int():
    params = _bind_for(True)
    assert params["vs"] is True, f"expected bool True, got {params['vs']!r}"
    assert type(params["vs"]) is bool


def test_verification_skipped_false_binds_boolean_not_int():
    # The bug: False → int 0 → Postgres rejects on the boolean column → the
    # successful-answer trace is silently dropped. Must stay a real bool.
    params = _bind_for(False)
    assert params["vs"] is False, f"expected bool False, got {params['vs']!r}"
    assert type(params["vs"]) is bool


def test_verification_skipped_none_binds_null():
    params = _bind_for(None)
    assert params["vs"] is None

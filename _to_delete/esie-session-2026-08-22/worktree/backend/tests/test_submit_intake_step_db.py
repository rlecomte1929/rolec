"""
AIQ-1243 (C-01b) regression: set_assignment_submitted must advance intake_step to
intake_total_steps in the SAME UPDATE that flips status to 'submitted'.

Before the fix, intake_step was only advanced by a separate best-effort call
(update_assignment_intake_progress) that keys on employee_user_id — so an
id-resolution mismatch left submitted cases reading intake_step < total, and the
dashboard active-cases card showed "4/5 steps · Continue" for a submitted case.

Exercises the REAL CasesMixin.set_assignment_submitted (+ MiscMixin._exec) against
an in-memory SQLite, on an isolated host (no global db singleton), so it validates
the actual SQL without conftest/singleton coupling.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.cases import CasesMixin  # noqa: E402
from backend.db.misc import MiscMixin  # noqa: E402


class _Host(MiscMixin, CasesMixin):
    """Minimal host: real _exec (MiscMixin) + set_assignment_submitted (CasesMixin)."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self._initialized = True  # skip init_db in _exec
        self._init_lock = threading.Lock()


def _make_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE case_assignments "
                "(id TEXT, status TEXT, intake_step INTEGER, intake_total_steps INTEGER, "
                " submitted_at TEXT, updated_at TEXT, employee_user_id TEXT)"
            )
        )
        c.execute(
            text(
                "INSERT INTO case_assignments "
                "(id, status, intake_step, intake_total_steps, employee_user_id) "
                "VALUES ('asgn-1', 'created', 2, 5, 'emp-1')"
            )
        )
    return engine


def test_set_assignment_submitted_advances_intake_step_to_total():
    engine = _make_engine()
    _Host(engine).set_assignment_submitted("asgn-1")
    with engine.begin() as c:
        row = c.execute(
            text("SELECT status, intake_step FROM case_assignments WHERE id = 'asgn-1'")
        ).fetchone()
    assert row[0] == "submitted"
    # The bug: intake_step stayed at 2. The fix advances it to intake_total_steps (5)
    # in the same write, so the dashboard can't show "2/5 · Continue" on a submitted case.
    assert row[1] == 5

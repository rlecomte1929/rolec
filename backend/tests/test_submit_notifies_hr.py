"""AIQ-1342 — submit must notify the assigned HR user that intake was submitted.

`submit_assignment` flips the assignment to submitted and inserts a case event but
historically never told HR, so cases stalled silently until HR happened to look.
It now calls `db.create_notification_with_preferences` (the same helper powering
`/api/notifications/notify-hr`) for `assignment['hr_user_id']` after the status flip.

A full end-to-end submit needs a ≥90% profile plus the background plan executor, so
— consistent with the rest of the submit_assignment suite (see
`test_submit_status_parity.py`) — these are source-structure guards. Each maps to one
of the task's Validation Criteria:
  1) a notification is created for the HR user, after the status flip;
  2) it is best-effort so the submit still returns 200 if it raises;
  3) it is skipped when hr_user_id is null.
"""

from __future__ import annotations

import os


def _submit_assignment_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "main.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def submit_assignment(")
    end = src.index("\n@app.", start + 1)
    return src[start:end]


def test_submit_creates_hr_notification_after_status_flip():
    """Criterion 1: a notification is created (via the existing preferences-aware
    helper) for the assigned HR user, and only after the assignment is submitted."""
    src = _submit_assignment_source()
    assert "create_notification_with_preferences" in src
    # Targets the assignment's HR user, with an intake-submission type.
    assert "hr_user_id" in src
    assert 'type_="INTAKE_SUBMITTED"' in src
    assert "user_id=hr_user_id" in src
    # The notification must fire AFTER the status transition, not before.
    assert src.index("set_assignment_submitted") < src.index("db.create_notification_with_preferences(")


def test_submit_notification_links_the_case():
    """Criterion 1 (cont.): the notification references the assignment/case so HR can
    navigate to it."""
    src = _submit_assignment_source()
    notif_idx = src.index("db.create_notification_with_preferences(")
    block = src[notif_idx:notif_idx + 600]
    assert "assignment_id=assignment_id" in block
    assert "case_id=case_id" in block


def test_submit_notification_is_best_effort():
    """Criterion 2: a notification failure must never fail the submit — the call is
    wrapped in try/except that logs a warning rather than propagating."""
    src = _submit_assignment_source()
    notif_idx = src.index("db.create_notification_with_preferences(")
    # A try: precedes the call within the handler …
    assert "try:" in src[:notif_idx]
    # … and the except logs instead of re-raising.
    assert "submit_assignment: HR notification failed" in src
    # The handler still returns success at the end (the submit is not aborted).
    assert 'return {"success": True}' in src


def test_submit_skips_notification_when_no_hr_user():
    """Criterion 3: no notification is attempted when the assignment has no HR user."""
    src = _submit_assignment_source()
    notif_idx = src.index("db.create_notification_with_preferences(")
    # The call is guarded by an `if hr_user_id:` check that precedes it.
    guard_idx = src.rfind("if hr_user_id:", 0, notif_idx)
    assert guard_idx != -1, "create_notification_with_preferences must be guarded by `if hr_user_id:`"

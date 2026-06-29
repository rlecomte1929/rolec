"""AIQ-1376 — HR assigning an employee must fire an in-app notification.

`_dispatch_hr_assign_side_effects` ran the deferred assign side-effects (invite
email, case-participant, `assignment.created` case event, draft message) but never
created an in-app notification, so the employee's NotificationBell showed nothing
on assignment and the MSG-02 sentinel's notification check failed. It now calls
`db.create_notification_with_preferences` (the helper powering the other in-app
notifications) for `employee_user_id`, best-effort, after the case event.

Consistent with the rest of the assign/submit suites (a full assign needs the
provisioning + background executor), these are source-structure guards. Each maps
to one of the task's Validation Criteria:
  1) a notification is created for the employee, after the case event;
  2) it links the assignment/case so the employee can navigate;
  3) it is best-effort (failure never breaks the assign);
  4) it is skipped when employee_user_id is null.
"""

from __future__ import annotations

import os


def _side_effects_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "main.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def _dispatch_hr_assign_side_effects(")
    end = src.index("\ndef ", start + 1)
    return src[start:end]


def test_assign_creates_employee_notification_after_case_event():
    """Criterion 1: a notification is created for the employee, with the assignment
    type, and only after the `assignment.created` case event is recorded."""
    src = _side_effects_source()
    assert "create_notification_with_preferences" in src
    assert 'type_="ASSIGNMENT_CREATED"' in src
    assert "user_id=employee_user_id" in src
    # Fires AFTER the case event, not before.
    assert src.index('event_type="assignment.created"') < src.index(
        "db.create_notification_with_preferences("
    )


def test_assign_notification_links_the_case():
    """Criterion 2: the notification references the assignment + case so the
    employee can navigate to it."""
    src = _side_effects_source()
    notif_idx = src.index("db.create_notification_with_preferences(")
    block = src[notif_idx:notif_idx + 600]
    # kwargs are built once in _notif_kwargs and splatted into both writers.
    kw_idx = src.index("_notif_kwargs")
    kw_block = src[kw_idx:kw_idx + 600]
    assert "assignment_id=assignment_id" in kw_block
    assert "case_id=case_id" in kw_block


def test_assign_notification_is_best_effort():
    """Criterion 3: a notification failure must never fail the assign — the call is
    wrapped in try/except with a logged fallback rather than propagating."""
    src = _side_effects_source()
    notif_idx = src.index("db.create_notification_with_preferences(")
    assert "try:" in src[:notif_idx]
    # Fallback to a raw insert, then a warning log — never re-raise.
    assert "db.insert_notification(" in src
    assert "assignment notification skipped" in src


def test_assign_skips_notification_when_no_employee_user():
    """Criterion 4: no notification is attempted when the assignment has no resolved
    employee user id."""
    src = _side_effects_source()
    notif_idx = src.index("db.create_notification_with_preferences(")
    guard_idx = src.rfind("if employee_user_id:", 0, notif_idx)
    assert guard_idx != -1, "notification must be guarded by `if employee_user_id:`"

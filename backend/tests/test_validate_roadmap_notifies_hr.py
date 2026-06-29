"""CASE_STATUS_CHANGED — validating the roadmap must notify the assigned HR.

`CASE_STATUS_CHANGED` was a defined notification type with a NotificationSettings
toggle, but nothing ever emitted it. `validate_roadmap` (the employee's 'start
tasks' checkpoint) is the one clean case-status milestone HR cares about, so it now
fires CASE_STATUS_CHANGED to the case's hr_user_id, best-effort, after the audit.

Consistent with the other notification suites (a full validate needs a provisioned
case + roadmap), these are source-structure guards. Each maps to a criterion:
  1) a CASE_STATUS_CHANGED notification is created for the assigned HR, after the
     roadmap_validated audit event;
  2) it links the case;
  3) it is best-effort (a failure never fails the validate);
  4) it is skipped when the case has no hr_user_id.
"""

from __future__ import annotations

import os


def _validate_roadmap_source() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "backend", "app", "routers", "cases_write.py",
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def validate_roadmap(")
    end = src.index("\n@router.", start + 1)
    return src[start:end]


def test_validate_creates_hr_notification_after_audit():
    src = _validate_roadmap_source()
    assert "create_notification_with_preferences" in src
    assert 'type_="CASE_STATUS_CHANGED"' in src
    assert "user_id=hr_user_id" in src
    # Fires AFTER the roadmap_validated audit event, not before.
    assert src.index('"event": "roadmap_validated"') < src.index(
        "create_notification_with_preferences("
    )


def test_validate_notification_links_the_case():
    src = _validate_roadmap_source()
    notif_idx = src.index("create_notification_with_preferences(")
    block = src[notif_idx:notif_idx + 600]
    assert "case_id=case_id" in block


def test_validate_notification_is_best_effort():
    src = _validate_roadmap_source()
    notif_idx = src.index("create_notification_with_preferences(")
    assert "try:" in src[:notif_idx]
    assert "validate_roadmap: HR notification failed" in src
    # The handler still returns the validated payload (validate is not aborted).
    assert '"roadmap_validated": True' in src


def test_validate_skips_notification_when_no_hr_user():
    src = _validate_roadmap_source()
    notif_idx = src.index("create_notification_with_preferences(")
    guard_idx = src.rfind("if hr_user_id:", 0, notif_idx)
    assert guard_idx != -1, "create_notification_with_preferences must be guarded by `if hr_user_id:`"

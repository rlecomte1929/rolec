"""AIQ-1342 behavioral test — submit_assignment actually creates the HR notification.

Complements the source-structure guards in test_submit_notifies_hr.py with a real
call. A full HTTP/E2E submit needs a ≥90% profile + the background plan executor +
live DB, so instead we call the handler function directly with its collaborators
monkeypatched: profile completeness is forced ≥90 (skips the wizard-draft branch),
the relocation-case id is forced None (skips the case-event / SessionLocal / plan
blocks), and `db` is a fake that records create_notification_with_preferences calls.

This proves the three validation criteria behaviorally:
  1) a notification is created for the assigned HR user, referencing the assignment;
  2) the submit still returns success even if the notification raises;
  3) no notification is created when hr_user_id is null.
"""
from __future__ import annotations

import os

# Calling submit_assignment directly imports backend.main, which attaches a
# SQLAlchemy query-counter listener at import time. Disable it (app-mounted-harness
# convention) so import is robust when other test modules have swapped the engine.
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import backend.main as bm

EMP = "emp-1"
HR = "hr-1"
AID = "assignment-1"


class _FakeDB:
    def __init__(self, hr_user_id, raise_on_notify=False):
        self.notif_calls = []
        self.raise_on_notify = raise_on_notify
        self._assignment = {"employee_user_id": EMP, "hr_user_id": hr_user_id, "case_id": "case-1"}

    def get_assignment_by_id(self, _aid):
        return dict(self._assignment)

    def get_employee_profile(self, _aid):
        return {"primaryApplicant": {"firstName": "A"}}  # truthy → profile present

    def set_assignment_submitted(self, _aid):
        self.submitted = _aid

    def get_assignment_intake(self, **_kw):
        return {"intake_total_steps": 5}

    def update_assignment_intake_progress(self, **_kw):
        pass

    def create_notification_with_preferences(self, **kwargs):
        self.notif_calls.append(kwargs)
        if self.raise_on_notify:
            raise RuntimeError("notify boom")
        return "notif-id"


def _patch_common(monkeypatch, fake_db):
    monkeypatch.setattr(bm, "db", fake_db)
    monkeypatch.setattr(bm, "_deny_if_impersonating", lambda _u: None)
    monkeypatch.setattr(bm, "_effective_user", lambda _u, _r=None: {"id": EMP, "role": "EMPLOYEE"})
    monkeypatch.setattr(bm, "_effective_relocation_case_id", lambda _a: None)
    monkeypatch.setattr(bm, "track_event", lambda *a, **k: None)
    monkeypatch.setattr(bm.orchestrator, "compute_completion_state", lambda _p: {"profileCompleteness": 100})


def test_submit_creates_hr_notification(monkeypatch):
    fake = _FakeDB(hr_user_id=HR)
    _patch_common(monkeypatch, fake)

    result = bm.submit_assignment(AID, user={"id": EMP, "role": "EMPLOYEE"})

    assert result == {"success": True}
    assert len(fake.notif_calls) == 1
    call = fake.notif_calls[0]
    assert call["user_id"] == HR
    assert call["type_"] == "INTAKE_SUBMITTED"
    assert call["assignment_id"] == AID
    assert "case_id" in call


def test_submit_succeeds_when_notification_raises(monkeypatch):
    fake = _FakeDB(hr_user_id=HR, raise_on_notify=True)
    _patch_common(monkeypatch, fake)

    # Must NOT propagate — the submit the employee just completed cannot fail here.
    result = bm.submit_assignment(AID, user={"id": EMP, "role": "EMPLOYEE"})

    assert result == {"success": True}
    assert len(fake.notif_calls) == 1  # attempted exactly once


def test_submit_skips_notification_without_hr_user(monkeypatch):
    fake = _FakeDB(hr_user_id=None)
    _patch_common(monkeypatch, fake)

    result = bm.submit_assignment(AID, user={"id": EMP, "role": "EMPLOYEE"})

    assert result == {"success": True}
    assert fake.notif_calls == []

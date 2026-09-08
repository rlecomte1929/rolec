"""AIQ-1608: notify the employee when HR requests roadmap changes."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from unittest.mock import MagicMock

import pytest

from backend.app.services import roadmap_review_notification as mod
from backend.app.routers.hr_roadmap_review import _is_new_change_round

_UUID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture()
def mocks(monkeypatch):
    monkeypatch.setattr(mod, "_corridor", lambda cid: "FR → DE")
    send = MagicMock(return_value={"status": "sent"})
    import backend.app.services.assignment_invite_email as aie

    monkeypatch.setattr(aie, "_resend_send", send)
    from backend.database import db as real_db

    inapp = MagicMock(return_value="notif-1")
    monkeypatch.setattr(real_db, "create_notification_with_preferences", inapp)
    return send, inapp


def _recipient(monkeypatch, *, uid, email="employee@example.com"):
    monkeypatch.setattr(
        mod, "_resolve_employee_recipient",
        lambda cid: {"email": email, "employee_name": "Alex", "employee_user_id": uid},
    )


# ── idempotency predicate ─────────────────────────────────────────────────────
def test_new_round_predicate():
    # first request (was released) → notify
    assert _is_new_change_round(True, "", "add a bank step") is True
    # identical re-request (already not-released, same note) → skip
    assert _is_new_change_round(False, "add a bank step", "add a bank step") is False
    assert _is_new_change_round(False, " add a bank step ", "add a bank step") is False
    # changed note on a new round → notify
    assert _is_new_change_round(False, "old note", "new note") is True
    # request after an approve (was released) → notify
    assert _is_new_change_round(True, "old note", "old note") is True


# ── notify function ───────────────────────────────────────────────────────────
def test_email_and_inapp_for_uuid_employee(mocks, monkeypatch):
    send, inapp = mocks
    _recipient(monkeypatch, uid=_UUID)
    out = mod.notify_employee_roadmap_changes("case-1", "Please add a bank-account step")
    assert out["status"] == "ok"
    assert out["email_status"] == "sent"
    assert send.call_count == 1
    assert "Please add a bank-account step" in send.call_args.kwargs["plain"]
    assert inapp.call_count == 1
    assert inapp.call_args.kwargs["user_id"] == _UUID
    assert "Please add a bank-account step" in inapp.call_args.kwargs["body"]


def test_inapp_skipped_for_legacy_id_but_email_still_sent(mocks, monkeypatch):
    send, inapp = mocks
    _recipient(monkeypatch, uid="seed-emp-testingapril")
    out = mod.notify_employee_roadmap_changes("case-1", "note")
    assert out["email_status"] == "sent"
    assert out["inapp"] == "skipped_legacy_id"
    assert send.call_count == 1
    assert inapp.call_count == 0


def test_unreachable_when_no_recipient(mocks, monkeypatch):
    send, inapp = mocks
    monkeypatch.setattr(mod, "_resolve_employee_recipient", lambda cid: None)
    out = mod.notify_employee_roadmap_changes("case-1", "note")
    assert out["status"] == "unreachable"
    assert send.call_count == 0
    assert inapp.call_count == 0


def test_never_raises_on_inapp_error(mocks, monkeypatch):
    send, inapp = mocks
    inapp.side_effect = RuntimeError("db down")
    _recipient(monkeypatch, uid=_UUID)
    out = mod.notify_employee_roadmap_changes("case-1", "note")  # must not raise
    assert out["email_status"] == "sent"
    assert out["inapp"] == "error"

"""[AIQ-1610 follow-up] Exception notifications reach EVERY party, including legacy accounts.

Two gaps this pins closed:
  * legacy non-uuid HR / employee ids were silently skipped (no in-app row possible → the notify
    bailed entirely, so no email either). They now get the email via a direct Resend send.
  * the employee-decision path now instant-fires (symmetric to the HR-request path), and its type
    emails by default.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.routers import exception_requests as exc

_UUID = "11111111-1111-4111-8111-111111111111"
_LEGACY = "seed-hr-legacy-1"  # non-uuid, like the seed-hr-* / seed-emp-* demo accounts


@pytest.fixture(autouse=True)
def _force_pg(monkeypatch):
    # The uuid guard only engages off sqlite; force the pg path so the legacy branch is exercised.
    monkeypatch.setattr(exc, "_is_sqlite_engine", lambda: False)


def _resend(monkeypatch, sink):
    monkeypatch.setattr(
        "backend.app.services.assignment_invite_email._resend_send",
        lambda **kw: sink.append(kw) or {"status": "sent"},
    )


def _instant_fire(monkeypatch, sink):
    monkeypatch.setattr(
        "backend.app.services.notification_outbox_dispatch.dispatch_outbox_soon",
        lambda *a, **k: sink.append(True),
    )


def _body():
    return SimpleNamespace(
        requested_amount=5000.0, cap_amount=3000.0, currency="EUR",
        type_label="Host housing cap", category="housing", exception_type="cap_override",
    )


class TestHrRequestNotify:
    def test_legacy_hr_gets_a_direct_email(self, monkeypatch):
        monkeypatch.setattr(exc.db, "get_assignment_by_case_id",
                            lambda cid: {"hr_user_id": _LEGACY, "id": "a1"}, raising=False)
        monkeypatch.setattr(exc.db, "get_user_by_id",
                            lambda uid: {"email": "legacyhr@x.com"}, raising=False)
        created, sent = [], []
        monkeypatch.setattr(exc.db, "create_notification_with_preferences",
                            lambda **kw: created.append(kw), raising=False)
        _resend(monkeypatch, sent)

        exc._notify_hr_of_exception_request(request_id="r1", case_id="c1", body=_body())

        assert created == [], "legacy HR must NOT hit the uuid in-app/outbox path"
        assert len(sent) == 1 and sent[0]["to_email"] == "legacyhr@x.com"
        assert "3,000 EUR" in sent[0]["plain"] and "5,000 EUR" in sent[0]["plain"]

    def test_uuid_hr_uses_inapp_outbox_and_instant_fires(self, monkeypatch):
        monkeypatch.setattr(exc.db, "get_assignment_by_case_id",
                            lambda cid: {"hr_user_id": _UUID, "id": "a1"}, raising=False)
        created, fired, sent = [], [], []
        monkeypatch.setattr(exc.db, "create_notification_with_preferences",
                            lambda **kw: created.append(kw), raising=False)
        _instant_fire(monkeypatch, fired)
        _resend(monkeypatch, sent)

        exc._notify_hr_of_exception_request(request_id="r1", case_id="c1", body=_body())

        assert len(created) == 1
        assert created[0]["type_"] == exc.NOTIFICATION_TYPE_EXCEPTION_REQUESTED
        assert fired == [True], "uuid path instant-fires"
        assert sent == [], "uuid path never uses the legacy direct-send"

    def test_legacy_hr_with_no_email_is_a_safe_noop(self, monkeypatch):
        monkeypatch.setattr(exc.db, "get_assignment_by_case_id",
                            lambda cid: {"hr_user_id": _LEGACY, "id": "a1"}, raising=False)
        monkeypatch.setattr(exc.db, "get_user_by_id", lambda uid: {"email": ""}, raising=False)
        sent = []
        _resend(monkeypatch, sent)

        exc._notify_hr_of_exception_request(request_id="r1", case_id="c1", body=_body())  # no raise

        assert sent == [], "no email on file → nothing sent, no crash"


class TestEmployeeDecisionNotify:
    def _existing(self, emp_id):
        return {"requested_by_user_id": emp_id, "category": "housing", "currency": "EUR",
                "requested_amount": 5000.0, "case_id": "c1"}

    def test_uuid_employee_emailed_and_instant_fired(self, monkeypatch):
        created, fired = [], []
        monkeypatch.setattr(exc.db, "create_notification_with_preferences",
                            lambda **kw: created.append(kw), raising=False)
        _instant_fire(monkeypatch, fired)

        exc._notify_employee_of_decision(request_id="r1", existing=self._existing(_UUID),
                                         status="approved", hr_note="ok")

        assert len(created) == 1
        assert created[0]["type_"] == exc.NOTIFICATION_TYPE_EXCEPTION_DECIDED
        assert "approved" in created[0]["title"]
        assert fired == [True], "decision path now instant-fires, symmetric to the HR side"

    def test_legacy_employee_gets_direct_email(self, monkeypatch):
        monkeypatch.setattr(exc.db, "get_user_by_id",
                            lambda uid: {"email": "legacyemp@x.com"}, raising=False)
        created, sent = [], []
        monkeypatch.setattr(exc.db, "create_notification_with_preferences",
                            lambda **kw: created.append(kw), raising=False)
        _resend(monkeypatch, sent)

        exc._notify_employee_of_decision(request_id="r1", existing=self._existing(_LEGACY),
                                         status="declined", hr_note="over budget")

        assert created == []
        assert len(sent) == 1 and sent[0]["to_email"] == "legacyemp@x.com"
        assert "declined" in sent[0]["subject"]

"""[AIQ-1610] Policy-exception notifications email HR by default.

`create_notification_with_preferences` previously defaulted email OFF, so a policy-exception
HR notification only enqueued an outbox row (→ email) if the HR user had explicitly toggled email
on — which almost nobody had. The over-cap → HR-notify chain therefore never emailed anyone.

The fix defaults email ON for the types in `_EMAIL_DEFAULT_ON` (POLICY_EXCEPTION_REQUESTED) when
the recipient has NO explicit preference row, while a stored preference still wins (opt-out honored).
These tests pin exactly that gate.
"""
from __future__ import annotations

from backend.db.support import SupportMixin


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, *_a, **_k):
        return None


class _FakeEngine:
    def begin(self):
        return _FakeConn()


class _DB(SupportMixin):
    """SupportMixin with its collaborators stubbed, so we exercise the real
    create_notification_with_preferences gate without a live database."""

    def __init__(self, pref):
        self._pref = pref
        self.engine = _FakeEngine()
        self.outbox_calls = []

    def _get_notification_preference(self, _uid, _type):
        return self._pref

    def get_user_by_id(self, _uid):
        return {"email": "hr@acme.com"}

    def _insert_notification_outbox(self, **kwargs):  # capture instead of hitting the queue
        self.outbox_calls.append(kwargs)


_EXC = "POLICY_EXCEPTION_REQUESTED"
_OTHER = "SOME_OTHER_TYPE"


def _notify(db, type_):
    return db.create_notification_with_preferences(
        user_id="hr-1", type_=type_, title="t", body="b", case_id="c1"
    )


def test_exception_type_emails_by_default_when_no_preference():
    db = _DB(pref=None)
    nid = _notify(db, _EXC)
    assert nid is not None
    assert len(db.outbox_calls) == 1, "policy-exception must enqueue an outbox row by default"
    assert db.outbox_calls[0]["to_email"] == "hr@acme.com"


def test_decision_type_also_emails_by_default_when_no_preference():
    # [AIQ-1610 follow-up] POLICY_EXCEPTION_DECIDED joined the default-on set so the employee is
    # emailed the outcome of the request they filed.
    db = _DB(pref=None)
    nid = _notify(db, "POLICY_EXCEPTION_DECIDED")
    assert nid is not None
    assert len(db.outbox_calls) == 1, "the decision notification must enqueue an outbox row by default"


def test_non_default_type_does_not_email_by_default():
    db = _DB(pref=None)
    _notify(db, _OTHER)
    assert db.outbox_calls == [], "a non-default type stays in-app-only unless opted in"


def test_explicit_opt_out_still_wins_for_default_on_type():
    db = _DB(pref={"in_app": True, "email": False})
    _notify(db, _EXC)
    assert db.outbox_calls == [], "an explicit email=false preference must be respected"


def test_explicit_opt_in_emails_a_non_default_type():
    db = _DB(pref={"in_app": True, "email": True})
    _notify(db, _OTHER)
    assert len(db.outbox_calls) == 1

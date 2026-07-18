"""[AIQ-1526] HR gets told when a roadmap is waiting on them.

The failure mode this feature exists to prevent is SILENCE: a roadmap is generated, held
for HR approval, the employee can't start their tasks — and nobody tells HR. They find out
by opening the case, or they don't.

So the tests that matter most here are not "does the happy path send an email". They are:

  * an unreachable HR is RECORDED, not skipped (a silent skip looks exactly like success)
  * a failed send stays visibly undelivered (notified_at NOT set)
  * a mail problem never costs the employee their roadmap
  * we never mail HR twice for the same case
"""
from __future__ import annotations

import os

import pytest

os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from backend.app.services import roadmap_review_notification as svc


@pytest.fixture(autouse=True)
def _no_real_engine(monkeypatch):
    """Every test drives the DB through explicit fakes; nothing touches a real engine."""
    monkeypatch.setattr(svc, "_engine", lambda: pytest.fail("test touched the real engine"))


def _stub_db(monkeypatch, *, recipient, already=False, corridor="FR → DE"):
    monkeypatch.setattr(svc, "resolve_hr_recipient", lambda _cid: recipient)
    monkeypatch.setattr(svc, "_already_notified", lambda _cid: already)
    monkeypatch.setattr(svc, "_corridor", lambda _cid: corridor)
    recorded = {}
    monkeypatch.setattr(
        svc, "_record", lambda cid, status, to: recorded.update(case_id=cid, status=status, to=to)
    )
    return recorded


_HR = {"email": "hr@acme.com", "hr_name": "Hannah", "employee_name": "Lucas Martin"}


class _Row:
    def __init__(self, mapping):
        self._mapping = mapping


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, by_sql):
        self._by_sql = by_sql

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, sql, _params):
        return _Result(self._by_sql.get(sql))


def _wire_engine(monkeypatch, *, assigned=None, company=None):
    """Point svc._engine at a fake connection that returns `assigned` for the tier-1 SQL and
    `company` for the tier-2 SQL — so we can test the resolution ORDER without a real DB."""
    by_sql = {svc._ASSIGNED_HR_SQL: assigned, svc._COMPANY_HR_SQL: company}

    class _Engine:
        def connect(self):
            return _Conn(by_sql)

    monkeypatch.setattr(svc, "_engine", lambda: _Engine())


class TestRecipientResolvesAcrossTiers:
    """[AIQ-1606] resolve_hr_recipient tries the assigned HR first, then the case's company HR."""

    def test_tier1_assigned_hr_wins(self, monkeypatch):
        _wire_engine(monkeypatch, assigned=_Row(
            {"email": "a@x.com", "hr_name": "A", "employee_name": "Jane Doe"}))
        assert svc.resolve_hr_recipient("c1") == {
            "email": "a@x.com", "hr_name": "A", "employee_name": "Jane Doe"}

    def test_falls_back_to_company_hr_when_no_assignment(self, monkeypatch):
        _wire_engine(monkeypatch, assigned=None, company=_Row(
            {"email": "co@x.com", "hr_name": "Co", "employee_name": ""}))
        r = svc.resolve_hr_recipient("c1")
        assert r["email"] == "co@x.com"
        # no assignment → no employee name → the copy uses a safe default
        assert r["employee_name"] == "Your employee"

    def test_none_when_neither_tier_resolves(self, monkeypatch):
        _wire_engine(monkeypatch, assigned=None, company=None)
        assert svc.resolve_hr_recipient("c1") is None


class TestAnUnreachableHrIsRecordedNotSwallowed:
    """10 of the 47 cases with a roadmap resolve to NO HR email (no case_assignments row,
    or an HR id with no email). For those, an employee is blocked and there is nobody to
    tell. If we quietly `continue`, that case is indistinguishable from a successful send
    and the employee waits forever. It must land in the metrics."""

    def test_no_recipient_is_recorded_as_unreachable(self, monkeypatch):
        recorded = _stub_db(monkeypatch, recipient=None)

        out = svc.notify_hr_roadmap_pending("c1")

        assert out["status"] == "unreachable"
        assert recorded["status"] == "unreachable", "an unreachable HR must be RECORDED"
        assert recorded["to"] is None

    def test_unreachable_does_not_mark_the_case_as_notified(self, monkeypatch):
        """`_record` only sets notified_at for sent/no_key — never for unreachable."""
        _stub_db(monkeypatch, recipient=None)
        sent = []
        monkeypatch.setattr(svc, "_resend_send", lambda **kw: sent.append(kw), raising=False)

        svc.notify_hr_roadmap_pending("c1")

        assert sent == [], "we must not try to send to nobody"


class TestAFailedSendStaysVisiblyUndelivered:
    """Instant-fire has no retry sweep. A failed send is therefore NOT re-sent — which is
    exactly why it must not be marked delivered. `notified_at` stays NULL and the metrics
    show it as undelivered, so a human can see HR was never actually told."""

    @pytest.mark.parametrize("resend_status", ["failed", "error"])
    def test_a_failed_resend_is_recorded_as_such(self, monkeypatch, resend_status):
        recorded = _stub_db(monkeypatch, recipient=_HR)
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: {"status": resend_status},
        )

        out = svc.notify_hr_roadmap_pending("c1")

        assert out["status"] == resend_status
        assert recorded["status"] == resend_status

    def test_a_successful_send_is_recorded_as_sent(self, monkeypatch):
        recorded = _stub_db(monkeypatch, recipient=_HR)
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: {"status": "sent"},
        )

        out = svc.notify_hr_roadmap_pending("c1")

        assert out["status"] == "sent"
        assert recorded["status"] == "sent"
        assert recorded["to"] == "hr@acme.com"


class TestAnEmailProblemNeverCostsTheEmployeeTheirRoadmap:
    def test_an_exploding_resend_does_not_propagate(self, monkeypatch):
        """This runs inside the background task that builds the roadmap. If it raised, a
        Resend outage would take the plan down with it."""
        recorded = _stub_db(monkeypatch, recipient=_HR)

        def boom(**_kw):
            raise RuntimeError("resend is down")

        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send", boom
        )

        out = svc.notify_hr_roadmap_pending("c1")  # must not raise

        assert out["status"] == "error"
        assert recorded["status"] == "error"


class TestWeNeverMailHrTwice:
    def test_an_already_notified_case_is_a_no_op(self, monkeypatch):
        _stub_db(monkeypatch, recipient=_HR, already=True)
        sent = []
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: sent.append(kw) or {"status": "sent"},
        )

        out = svc.notify_hr_roadmap_pending("c1")

        assert out["status"] == "already_notified"
        assert sent == [], "re-running the roadmap build must not re-mail HR"


class TestTheEmailSaysWhatIsAtStake:
    def test_it_names_the_employee_the_corridor_and_the_consequence(self):
        email = svc.render_email(case_id="c1", employee_name="Lucas Martin", corridor="FR → DE")

        assert "Lucas Martin" in email["subject"]
        assert "FR → DE" in email["subject"]
        # AIQ-1605: roadmaps are released-by-default (AIQ-1377), so the email invites review
        # (approve / request changes) rather than falsely claiming the employee is blocked.
        assert "review it" in email["plain"].lower()
        assert "keep preparing" in email["plain"].lower()
        assert "/hr/cases/c1" in email["plain"], "HR needs a way to act, not just be told"

    def test_a_missing_corridor_is_omitted_not_invented(self):
        email = svc.render_email(case_id="c1", employee_name="Lucas Martin", corridor="")

        assert email["subject"] == "Roadmap ready for your review — Lucas Martin"
        assert "None" not in email["subject"] and "()" not in email["subject"]


class TestDryRunSendsNothing:
    """The way to verify the wiring in PRODUCTION without mailing a real person."""

    def test_dry_run_resolves_and_renders_but_does_not_send(self, monkeypatch):
        _stub_db(monkeypatch, recipient=_HR)
        sent = []
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: sent.append(kw) or {"status": "sent"},
        )

        out = svc.notify_hr_roadmap_pending("c1", dry_run=True)

        assert out["status"] == "dry_run"
        assert out["would_send_to"] == "hr@acme.com"
        assert sent == []

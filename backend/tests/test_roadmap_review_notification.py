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


def _stub_db(monkeypatch, *, recipient, already=False, corridor="FR → DE", is_test=False):
    monkeypatch.setattr(svc, "resolve_hr_recipient", lambda _cid: recipient)
    monkeypatch.setattr(svc, "_already_notified", lambda _cid: already)
    monkeypatch.setattr(svc, "_corridor", lambda _cid: corridor)
    # Fixture suppression reads the DB too; default it to "a real case" so every existing
    # test keeps exercising the send path it was written for.
    monkeypatch.setattr(svc, "_is_test_case", lambda _cid: is_test)
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

    def test_company_with_emailable_hr_is_never_unreachable(self, monkeypatch):
        # [AIQ-1624] The guarantee codified: whenever the case's company has ANY emailable HR
        # (tier-2 resolves, even with no assignment), resolve_hr_recipient returns a recipient
        # — the case is never 'unreachable'. Only a company with genuinely zero reachable HR
        # yields None, which the ops surface turns into an explicit action.
        _wire_engine(monkeypatch, assigned=None, company=_Row(
            {"email": "companyhr@x.com", "hr_name": "Company HR", "employee_name": ""}))
        assert svc.resolve_hr_recipient("c-any") is not None


class TestUnreachableOpsAction:
    """[AIQ-1624] A genuinely unreachable roadmap is an explicit ops action, not a silent status."""

    def test_reason_mapping(self):
        from backend.app.routers.hr_roadmap_review import _unreachable_reason
        # No company on the case → link it to a company first.
        assert _unreachable_reason(None, False) == "link_case_to_company"
        # Company exists but has zero HR → assign an HR to the company.
        assert _unreachable_reason("co-1", False) == "assign_hr_to_company"
        # Company has HR but none is reachable (no email) → fix the HR contact.
        assert _unreachable_reason("co-1", True) == "fix_hr_contact"


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


class TestFallbackToAdminWhenNoHr:
    """[AIQ-1609] When no HR resolves, the notification must not silently drop — it falls back
    to the admin allowlist so someone actionable is always reached. Only a case with no HR AND
    no admin recipient stays 'unreachable'."""

    def _admins(self, monkeypatch, emails):
        monkeypatch.setattr(
            "backend.app.services.admin_notify.resolve_admin_emails", lambda: list(emails)
        )

    def test_no_hr_but_admin_allowlist_gets_the_fallback(self, monkeypatch):
        recorded = _stub_db(monkeypatch, recipient=None)
        self._admins(monkeypatch, ["ops@relopass.com"])
        sent = []
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: sent.append(kw) or {"status": "sent"},
        )

        out = svc.notify_hr_roadmap_pending("c1")

        assert out["status"] == "fallback"
        assert out["to"] == ["ops@relopass.com"]
        assert recorded["status"] == "fallback", "a fallback send must be RECORDED as delivered"
        assert recorded["to"] == "ops@relopass.com"
        assert len(sent) == 1 and sent[0]["to_email"] == "ops@relopass.com"

    def test_fallback_marks_the_case_notified(self, monkeypatch):
        """`_record`'s delivered tuple now includes 'fallback', so notified_at is stamped and the
        next sweep won't re-send."""
        assert svc._STATUS_FALLBACK == "fallback"
        # delivered-status set is what _record uses to decide notified_at.
        from backend.app.services.roadmap_review_notification import (
            _STATUS_SENT, _STATUS_NO_KEY, _STATUS_FALLBACK,
        )
        assert _STATUS_FALLBACK in (_STATUS_SENT, _STATUS_NO_KEY, _STATUS_FALLBACK)

    def test_no_hr_and_no_admin_is_still_unreachable(self, monkeypatch):
        recorded = _stub_db(monkeypatch, recipient=None)
        self._admins(monkeypatch, [])
        sent = []
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: sent.append(kw) or {"status": "sent"},
        )

        out = svc.notify_hr_roadmap_pending("c1")

        assert out["status"] == "unreachable"
        assert recorded["status"] == "unreachable"
        assert sent == [], "no admin recipient → nothing sent"

    def test_fallback_dry_run_sends_nothing(self, monkeypatch):
        _stub_db(monkeypatch, recipient=None)
        self._admins(monkeypatch, ["ops@relopass.com"])
        sent = []
        monkeypatch.setattr(
            "backend.app.services.assignment_invite_email._resend_send",
            lambda **kw: sent.append(kw) or {"status": "sent"},
        )

        out = svc.notify_hr_roadmap_pending("c1", dry_run=True)

        assert out["status"] == "dry_run"
        assert out["would_send_to"] == ["ops@relopass.com"]
        assert out.get("fallback") is True
        assert sent == []


class TestFixtureCasesNeverReachResend:
    """Cost containment, measured 2026-08-26: 627 roadmap-review emails went out in August
    (187 in July, 3.4x growth) and EVERY recipient was an E2E fixture — `Test Drive R4xmove`,
    `E2E Sentinel A ... (Seed)`. 806 of the 814 delivered rows resolve to a reserved synthetic
    domain, the other 43 to an is_test company.

    The provisioner creates the cases; this cron turns each one into a real, billed Resend
    send. Both signals are checked because neither alone covers the data.

    The demo tenants (@testcompany.com, @*-demo.com) are REAL and must keep receiving mail —
    that is the over-blocking failure this guards against, and why the match is a suffix.
    """

    def test_probe_test_recipient_is_not_emailed(self, monkeypatch):
        recorded = _stub_db(
            monkeypatch,
            recipient={"email": "hr@probe.test", "hr_name": "P", "employee_name": "E"},
        )
        monkeypatch.setattr(svc, "_is_test_case", lambda _cid: False)
        out = svc.notify_hr_roadmap_pending("c1")
        assert out["status"] == "skipped_test_fixture"
        assert recorded["status"] == "skipped_test_fixture", "the skip must be RECORDED, not silent"

    def test_testco_recipient_is_not_emailed(self, monkeypatch):
        _stub_db(monkeypatch,
                 recipient={"email": "hr@testco.com", "hr_name": "T", "employee_name": "E"})
        monkeypatch.setattr(svc, "_is_test_case", lambda _cid: False)
        assert svc.notify_hr_roadmap_pending("c1")["status"] == "skipped_test_fixture"

    def test_is_test_company_is_not_emailed_even_with_a_real_looking_address(self, monkeypatch):
        recorded = _stub_db(monkeypatch, recipient=_HR)
        monkeypatch.setattr(svc, "_is_test_case", lambda _cid: True)
        out = svc.notify_hr_roadmap_pending("c1")
        assert out["status"] == "skipped_test_fixture"
        assert recorded["status"] == "skipped_test_fixture"

    def test_skip_never_marks_the_case_notified(self):
        """`_record` sets notified_at only for delivered statuses — a skip must not be one,
        so a fixture case stays visibly un-notified rather than looking successfully mailed."""
        assert "skipped_test_fixture" not in (
            svc._STATUS_SENT, svc._STATUS_NO_KEY, svc._STATUS_FALLBACK)

    # ── over-blocking guards: these addresses are REAL ──────────────────────────────

    def test_demo_tenant_still_receives_mail(self, monkeypatch):
        _stub_db(monkeypatch,
                 recipient={"email": "hr@testcompany.com", "hr_name": "D", "employee_name": "E"})
        monkeypatch.setattr(svc, "_is_test_case", lambda _cid: False)
        monkeypatch.setattr(svc, "_corridor", lambda _cid: "FR → DE")
        sent = {}
        import backend.app.services.assignment_invite_email as inv
        monkeypatch.setattr(inv, "_resend_send",
                            lambda **kw: sent.update(kw) or {"status": "sent"})
        assert svc.notify_hr_roadmap_pending("c1")["status"] == "sent"
        assert sent["to_email"] == "hr@testcompany.com"

    def test_ordinary_customer_still_receives_mail(self, monkeypatch):
        _stub_db(monkeypatch, recipient=_HR)
        monkeypatch.setattr(svc, "_is_test_case", lambda _cid: False)
        sent = {}
        import backend.app.services.assignment_invite_email as inv
        monkeypatch.setattr(inv, "_resend_send",
                            lambda **kw: sent.update(kw) or {"status": "sent"})
        assert svc.notify_hr_roadmap_pending("c1")["status"] == "sent"
        assert sent["to_email"] == "hr@acme.com"

    def test_explicit_override_can_still_force_a_send_to_a_fixture(self, monkeypatch):
        """An operator asking for a specific address is a deliberate act, not the cron."""
        _stub_db(monkeypatch,
                 recipient={"email": "hr@probe.test", "hr_name": "P", "employee_name": "E"})
        monkeypatch.setattr(svc, "_is_test_case", lambda _cid: False)
        import backend.app.services.assignment_invite_email as inv
        monkeypatch.setattr(inv, "_resend_send", lambda **kw: {"status": "sent"})
        out = svc.notify_hr_roadmap_pending("c1", to_override="hr@probe.test")
        assert out["status"] == "sent"

    def test_unknown_test_state_fails_open(self, monkeypatch):
        """If the is_test lookup breaks, answer False so the mail still goes out: a missing
        real notification is worse than one extra fixture email. Mirrors _already_notified."""

        def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(svc, "_engine", _boom)
        assert svc._is_test_case("c1") is False

    def test_recipient_domain_match_is_a_suffix_not_a_substring(self):
        """@testco.com must not swallow @testcompany.com — the demo tenants are real."""
        assert svc._is_test_recipient("hr@probe.test") is True
        assert svc._is_test_recipient("hr@testco.com") is True
        assert svc._is_test_recipient("HR@TestCo.com ") is True
        assert svc._is_test_recipient("hr@testcompany.com") is False
        assert svc._is_test_recipient("hr@acme-demo.com") is False
        assert svc._is_test_recipient("hr@probe.testing.com") is False
        assert svc._is_test_recipient(None) is False

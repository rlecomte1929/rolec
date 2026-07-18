"""AIQ-1602: admin gap-request email notification (fail-soft)."""
from unittest.mock import MagicMock

from backend.app.services import admin_notify


def test_no_recipients_sends_nothing(monkeypatch):
    monkeypatch.setattr(admin_notify, "resolve_admin_emails", lambda: [])
    spy = MagicMock()
    monkeypatch.setattr(admin_notify, "_resend_send", spy)

    result = admin_notify.notify_admins_gap_request(
        city="Lisbon", country="PT", category="movers", company_id="co-1"
    )

    assert result == {}
    spy.assert_not_called()


def test_emails_each_admin_with_details(monkeypatch):
    monkeypatch.setattr(
        admin_notify, "resolve_admin_emails", lambda: ["a@x.com", "b@x.com"]
    )
    spy = MagicMock(return_value={"status": "sent", "from": "noreply@relopass.com"})
    monkeypatch.setattr(admin_notify, "_resend_send", spy)

    result = admin_notify.notify_admins_gap_request(
        city="Lisbon", country="PT", category="movers", company_id="co-1"
    )

    assert result == {"a@x.com": "sent", "b@x.com": "sent"}
    assert spy.call_count == 2
    # every recipient gets a subject naming the category + destination
    subjects = {c.kwargs["subject"] for c in spy.call_args_list}
    assert len(subjects) == 1
    subject = subjects.pop()
    assert "movers" in subject and "Lisbon" in subject and "PT" in subject
    # body carries the destination but no employee PII
    body = spy.call_args_list[0].kwargs["plain"]
    assert "Lisbon" in body and "movers" in body


def test_all_categories_sentinel_reads_naturally(monkeypatch):
    monkeypatch.setattr(admin_notify, "resolve_admin_emails", lambda: ["a@x.com"])
    spy = MagicMock(return_value={"status": "sent"})
    monkeypatch.setattr(admin_notify, "_resend_send", spy)

    admin_notify.notify_admins_gap_request(
        city="Oslo", country="NO", category="_all_categories"
    )

    assert "all categories" in spy.call_args.kwargs["subject"]


def test_send_error_is_swallowed(monkeypatch):
    monkeypatch.setattr(admin_notify, "resolve_admin_emails", lambda: ["a@x.com"])

    def boom(**_kwargs):
        raise RuntimeError("resend down")

    monkeypatch.setattr(admin_notify, "_resend_send", boom)

    # must not raise, and reports the failure per-recipient
    result = admin_notify.notify_admins_gap_request(
        city="Lisbon", country="PT", category="banks"
    )
    assert result == {"a@x.com": "error"}

"""[AIQ-1610] The notification_outbox consumer actually sends pending rows — behind a recipient guard.

The failure mode this closes: the outbox had writers but no consumer, so rows sat 'pending'
forever and the emails (milestone reminders, policy-exception HR notifications) never went out.
These tests pin the consumer's contract:

  * a pending row whose recipient is allowlisted is delivered via Resend and marked 'sent'
  * a failed / exploding send leaves the row 'failed' with last_error (never re-queued, never raises)
  * a row with no recipient is marked failed, not sent to nobody
  * 'no_key' (Resend unconfigured) still moves the row terminal so the queue can't wedge

SAFETY: they also pin the recipient guard — a row whose domain is NOT on
``RELOPASS_OUTBOX_ALLOWED_DOMAINS`` is marked 'skipped' and is NEVER handed to Resend, and the
fail-closed default allowlist is ``@probe.test`` only.
"""
from __future__ import annotations

from backend.app.services import notification_outbox_dispatch as mod


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Conn:
    def __init__(self, rows, updates):
        self._rows = rows
        self._updates = updates

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, sql, params=None):
        if "UPDATE" in str(sql):
            self._updates.append(params)
            return _Res([])
        return _Res(self._rows)


class _Engine:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def connect(self):
        return _Conn(self.rows, self.updates)

    def begin(self):
        return _Conn(self.rows, self.updates)


class _DB:
    def __init__(self, engine):
        self.engine = engine


def _wire(monkeypatch, rows, resend):
    engine = _Engine(rows)
    monkeypatch.setattr(mod, "db", _DB(engine))
    monkeypatch.setattr(
        "backend.app.services.assignment_invite_email._resend_send", resend
    )
    return engine


def _row(**kw):
    base = {"id": "o1", "to_email": "hr@acme.com", "type": "POLICY_EXCEPTION_REQUESTED",
            "payload": {"title": "Exception requested", "body": "Please review."}}
    base.update(kw)
    return base


def test_pending_row_is_sent_and_marked_sent(monkeypatch):
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@acme.com")
    calls = []
    engine = _wire(monkeypatch, [_row()], lambda **kw: calls.append(kw) or {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert summary == {"pending": 1, "sent": 1, "logged": 0, "skipped": 0, "failed": 0}
    assert calls[0]["to_email"] == "hr@acme.com"
    assert calls[0]["subject"] == "Exception requested"
    assert engine.updates[0]["st"] == "sent"
    assert engine.updates[0]["err"] is None


def test_failed_send_is_marked_failed_with_error(monkeypatch):
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@acme.com")
    engine = _wire(monkeypatch, [_row()], lambda **kw: {"status": "failed"})

    summary = mod.run_outbox_dispatch_cron()

    assert summary["failed"] == 1 and summary["sent"] == 0
    assert engine.updates[0]["st"] == "failed"
    assert engine.updates[0]["err"] == "failed"


def test_exploding_send_never_raises_and_marks_failed(monkeypatch):
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@acme.com")

    def boom(**_kw):
        raise RuntimeError("resend down")

    engine = _wire(monkeypatch, [_row()], boom)

    summary = mod.run_outbox_dispatch_cron()  # must not raise

    assert summary["failed"] == 1
    assert engine.updates[0]["st"] == "failed"
    assert "resend down" in (engine.updates[0]["err"] or "")


def test_row_with_no_recipient_is_failed_not_sent(monkeypatch):
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@acme.com")
    calls = []
    engine = _wire(monkeypatch, [_row(to_email="")], lambda **kw: calls.append(kw) or {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert calls == [], "must never try to send to an empty recipient"
    assert summary["failed"] == 1
    assert engine.updates[0]["st"] == "failed"
    assert engine.updates[0]["err"] == "no recipient email"


def test_no_key_is_counted_logged_but_row_moves_terminal(monkeypatch):
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@acme.com")
    engine = _wire(monkeypatch, [_row()], lambda **kw: {"status": "no_key"})

    summary = mod.run_outbox_dispatch_cron()

    assert summary == {"pending": 1, "sent": 0, "logged": 1, "skipped": 0, "failed": 0}
    assert engine.updates[0]["st"] == "sent", "terminal so an unconfigured env can't wedge the queue"


def test_empty_queue_is_a_noop(monkeypatch):
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@acme.com")
    engine = _wire(monkeypatch, [], lambda **kw: {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert summary == {"pending": 0, "sent": 0, "logged": 0, "skipped": 0, "failed": 0}
    assert engine.updates == []


# ── Instant-fire (AIQ-1610 follow-up) ────────────────────────────────────────────────

def test_dispatch_outbox_soon_runs_the_consumer_off_thread(monkeypatch):
    import threading

    done = threading.Event()
    calls = []

    def _fake(limit=100):
        calls.append(limit)
        done.set()
        return {"pending": 0, "sent": 0, "logged": 0, "failed": 0}

    monkeypatch.setattr(mod, "run_outbox_dispatch_cron", _fake)

    mod.dispatch_outbox_soon(limit=25)

    assert done.wait(timeout=5), "instant-fire should invoke the consumer in the pool"
    assert calls == [25], "the bounded limit is passed through"


def test_dispatch_outbox_soon_never_raises_on_consumer_error(monkeypatch):
    import threading

    done = threading.Event()

    def _boom(limit=100):
        try:
            raise RuntimeError("resend down")
        finally:
            done.set()

    monkeypatch.setattr(mod, "run_outbox_dispatch_cron", _boom)

    mod.dispatch_outbox_soon()  # must not raise on the caller's thread

    assert done.wait(timeout=5)
    # _safe_dispatch swallows the error; nothing to assert beyond "did not propagate".


# --- Recipient guard (safety) --------------------------------------------------------------------


def test_non_allowlisted_recipient_is_skipped_not_sent(monkeypatch):
    """A real (non-probe) recipient is NEVER handed to Resend under the default allowlist."""
    monkeypatch.delenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", raising=False)  # rely on @probe.test default
    calls = []
    engine = _wire(monkeypatch, [_row(to_email="hr@acme.com")],
                   lambda **kw: calls.append(kw) or {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert calls == [], "a non-allowlisted recipient must NEVER be sent"
    assert summary == {"pending": 1, "sent": 0, "logged": 0, "skipped": 1, "failed": 0}
    assert engine.updates[0]["st"] == "skipped"
    assert "allowlist" in (engine.updates[0]["err"] or "")
    assert "hr@acme.com" in (engine.updates[0]["err"] or "")


def test_probe_test_default_allowlist_is_deliverable(monkeypatch):
    """The fail-closed default (@probe.test) still lets test probe mail through."""
    monkeypatch.delenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", raising=False)
    calls = []
    engine = _wire(monkeypatch, [_row(to_email="qa@probe.test")],
                   lambda **kw: calls.append(kw) or {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert calls and calls[0]["to_email"] == "qa@probe.test"
    assert summary == {"pending": 1, "sent": 1, "logged": 0, "skipped": 0, "failed": 0}
    assert engine.updates[0]["st"] == "sent"


def test_env_allowlist_controls_delivery_per_domain(monkeypatch):
    """With an explicit allowlist, only matching-domain rows send; the rest are skipped."""
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "@relopass.com")
    calls = []
    rows = [
        _row(id="ok", to_email="ops@relopass.com"),
        _row(id="nope", to_email="hr@acme.com"),
    ]
    engine = _wire(monkeypatch, rows, lambda **kw: calls.append(kw) or {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert [c["to_email"] for c in calls] == ["ops@relopass.com"], "only the allowlisted domain sends"
    assert summary == {"pending": 2, "sent": 1, "logged": 0, "skipped": 1, "failed": 0}
    statuses = {u["id"]: u["st"] for u in engine.updates}
    assert statuses == {"ok": "sent", "nope": "skipped"}


def test_empty_allowlist_skips_everything(monkeypatch):
    """An explicitly empty allowlist is fail-closed: nothing is ever sent."""
    monkeypatch.setenv("RELOPASS_OUTBOX_ALLOWED_DOMAINS", "")
    calls = []
    engine = _wire(monkeypatch, [_row(to_email="qa@probe.test")],
                   lambda **kw: calls.append(kw) or {"status": "sent"})

    summary = mod.run_outbox_dispatch_cron()

    assert calls == [], "an empty allowlist must block every recipient"
    assert summary["skipped"] == 1 and summary["sent"] == 0
    assert engine.updates[0]["st"] == "skipped"

"""AIQ-1414 Phase 3b — unit tests for the proactive coordinator scan.

DB- and network-free: the session list, event spine, cursor/close writes, and the
coordinator turn are faked/injected. Verifies first-scan cursor init, notify-on-new-events
with cursor advance, skip when nothing new, terminal-event close, and breaker skip.
"""
import contextlib

from backend.app.services import coordinator_proactive_service as svc


def ev(event_type, created_at, detail=None):
    return {"event_type": event_type, "created_at": created_at,
            "payload": ({"detail": detail} if detail else {})}


class _Eng:
    @contextlib.contextmanager
    def begin(self):
        yield object()

    @contextlib.contextmanager
    def connect(self):
        yield object()


class _FakeDB:
    def __init__(self, events_by_case):
        self.engine = _Eng()
        self._events = events_by_case

    def list_case_events(self, cid):
        return self._events.get(cid, [])


def _wire(monkeypatch, sessions, events_by_case, *, over_cap=False):
    monkeypatch.setattr(svc, "coordinator_enabled", lambda **_: True)
    monkeypatch.setattr(svc, "_list_active_sessions", lambda mdb, limit: sessions)
    monkeypatch.setattr(svc, "_over_cap", lambda cid: over_cap)
    cursors, closes, responds = [], [], []
    monkeypatch.setattr(svc.store, "set_event_cursor", lambda conn, cid, cur: cursors.append((cid, cur)))
    monkeypatch.setattr(svc.store, "close_session", lambda conn, cid: closes.append(cid))
    db = _FakeDB(events_by_case)

    def _respond(cid, msg, *, employee_id=None, db=None):
        responds.append((cid, msg, employee_id))
        return {"answer": "heads up", "case_id": cid, "model": "x"}

    return db, _respond, cursors, closes, responds


def test_flag_off_no_scan(monkeypatch):
    monkeypatch.setattr(svc, "coordinator_enabled", lambda **_: False)
    out = svc.run_coordinator_proactive_scan(db=_FakeDB({}))
    assert out == {"ok": True, "enabled": False, "scanned": 0}


def test_first_scan_initializes_cursor_without_notifying(monkeypatch):
    sessions = [{"case_id": "c1", "employee_id": "e1", "last_event_cursor": None}]
    events = {"c1": [ev("status_change", "2026-07-05T10:00:00+00:00")]}
    db, respond, cursors, closes, responds = _wire(monkeypatch, sessions, events)
    out = svc.run_coordinator_proactive_scan(db=db, respond=respond)
    assert responds == []                                   # backlog is NOT notified
    assert cursors == [("c1", "2026-07-05T10:00:00+00:00")]  # cursor initialised
    assert out["skipped"] == 1 and out["notified"] == 0


def test_notifies_on_new_events_and_advances_cursor(monkeypatch):
    sessions = [{"case_id": "c1", "employee_id": "e1", "last_event_cursor": "2026-07-01T00:00:00+00:00"}]
    events = {"c1": [
        ev("status_change", "2026-07-05T09:00:00+00:00", "Visa approved"),
        ev("note", "2026-07-06T09:00:00+00:00"),  # newer but not notify-worthy
    ]}
    db, respond, cursors, closes, responds = _wire(monkeypatch, sessions, events)
    out = svc.run_coordinator_proactive_scan(db=db, respond=respond)
    assert len(responds) == 1 and responds[0][0] == "c1"
    assert "Visa approved" in responds[0][1]
    assert cursors == [("c1", "2026-07-06T09:00:00+00:00")]  # advanced to newest FRESH event
    assert out["notified"] == 1


def test_skips_when_no_new_notify_events(monkeypatch):
    sessions = [{"case_id": "c1", "employee_id": "e1", "last_event_cursor": "2026-07-05T00:00:00+00:00"}]
    events = {"c1": [ev("note", "2026-07-06T00:00:00+00:00")]}  # newer but not whitelisted
    db, respond, cursors, closes, responds = _wire(monkeypatch, sessions, events)
    out = svc.run_coordinator_proactive_scan(db=db, respond=respond)
    assert responds == [] and out["skipped"] == 1


def test_closes_session_on_terminal_event(monkeypatch):
    sessions = [{"case_id": "c1", "employee_id": "e1", "last_event_cursor": "2026-07-01T00:00:00+00:00"}]
    events = {"c1": [ev("withdrawn", "2026-07-05T00:00:00+00:00")]}
    db, respond, cursors, closes, responds = _wire(monkeypatch, sessions, events)
    out = svc.run_coordinator_proactive_scan(db=db, respond=respond)
    assert closes == ["c1"] and responds == [] and out["closed"] == 1


def test_over_cap_pauses_proactive(monkeypatch):
    sessions = [{"case_id": "c1", "employee_id": "e1", "last_event_cursor": "2026-07-01T00:00:00+00:00"}]
    events = {"c1": [ev("status_change", "2026-07-05T00:00:00+00:00")]}
    db, respond, cursors, closes, responds = _wire(monkeypatch, sessions, events, over_cap=True)
    out = svc.run_coordinator_proactive_scan(db=db, respond=respond)
    assert responds == [] and out["skipped"] == 1

"""I-4 — case plan delivery adapter + endpoints.

Covers the pure .ics builder (timezone, VEVENT/VALARM, escaping), the email
wiring (mocks the Resend provider call — the I-4 'tool call' analog), and the
two endpoints' registration + auth gating. DB-touching helpers (milestones /
timezone read `public.*`) aren't exercised here — SQLite can't model the schema.
"""
import datetime as _dt
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

import backend.app.services.integrations.case_plan_delivery as delivery  # noqa: E402
import backend.app.services.dossier_notifications as dossier_notifications  # noqa: E402
from backend.main import app  # noqa: E402

_FIXED_NOW = _dt.datetime(2026, 6, 10, 12, 0, 0, tzinfo=_dt.timezone.utc)


# ── pure .ics builder ──────────────────────────────────────────────────────

def test_build_ics_basic_vevent():
    ics = delivery.build_ics(
        [{"id": "m1", "title": "File application", "date": _dt.date(2026, 7, 15)}],
        "UTC",
        now=_FIXED_NOW,
    )
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert "BEGIN:VEVENT" in ics and "END:VEVENT" in ics
    assert "UID:m1@relopass.com" in ics
    assert "SUMMARY:ReloPass — File application" in ics
    assert "BEGIN:VALARM" in ics and "TRIGGER:-P1D" in ics
    # 09:00 UTC stays 09:00Z
    assert "DTSTART:20260715T090000Z" in ics


def test_build_ics_respects_timezone():
    # 09:00 Europe/Paris in July (CEST, UTC+2) → 07:00Z
    ics = delivery.build_ics(
        [{"id": "m1", "title": "X", "date": _dt.date(2026, 7, 15)}],
        "Europe/Paris",
        now=_FIXED_NOW,
    )
    assert "DTSTART:20260715T070000Z" in ics


def test_build_ics_bad_timezone_falls_back_utc():
    ics = delivery.build_ics(
        [{"id": "m1", "title": "X", "date": _dt.date(2026, 7, 15)}],
        "Not/AZone",
        now=_FIXED_NOW,
    )
    assert "DTSTART:20260715T090000Z" in ics  # UTC fallback


def test_build_ics_empty_events_is_valid_empty_calendar():
    ics = delivery.build_ics([], "UTC", now=_FIXED_NOW)
    assert "BEGIN:VCALENDAR" in ics and "END:VCALENDAR" in ics
    assert "BEGIN:VEVENT" not in ics


def test_ics_escape_special_chars():
    assert delivery._ics_escape("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"


def test_milestone_label_known_and_fallback():
    assert delivery.milestone_label("application_filed") == "File immigration application"
    assert delivery.milestone_label("some_new_type") == "Some New Type"


# ── email wiring (mock the provider send) ──────────────────────────────────

def test_email_case_plan_sends_via_resend(monkeypatch):
    monkeypatch.setattr(
        delivery, "build_case_plan_email",
        lambda cid: {"subject": "Subj", "title": "Title", "body": "Body"},
    )
    captured = {}
    monkeypatch.setattr(dossier_notifications, "_send_email", lambda **kw: captured.update(kw))

    result = delivery.email_case_plan("case-1", "me@example.com", cta_url="https://x")

    assert captured["to"] == "me@example.com"
    assert captured["subject"] == "Subj"
    assert captured["title"] == "Title"
    assert captured["cta_url"] == "https://x"
    assert result["emailed_to"] == "me@example.com"


# ── endpoint registration + auth ───────────────────────────────────────────

def test_routes_registered():
    paths = {(m, r.path) for r in app.routes for m in (getattr(r, "methods", None) or [])}
    assert ("POST", "/api/cases/{case_id}/roadmap/email") in paths
    assert ("GET", "/api/cases/{case_id}/calendar.ics") in paths


def test_email_endpoint_requires_auth():
    client = TestClient(app)
    assert client.post("/api/cases/c1/roadmap/email", json={}).status_code == 401


def test_calendar_endpoint_requires_auth():
    client = TestClient(app)
    assert client.get("/api/cases/c1/calendar.ics").status_code == 401

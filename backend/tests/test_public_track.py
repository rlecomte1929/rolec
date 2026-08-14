import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_track_accepts_allowed_event():
    r = client.post("/api/public/track", json={
        "event": "landing_page_view", "properties": {"utm_source": "google"},
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_track_rejects_unknown_event():
    r = client.post("/api/public/track", json={"event": "arbitrary_event"})
    assert r.status_code == 422 or r.status_code == 400


# ── [AIQ-1783] engagement events for the paid-ad landing pages ────────────────

def test_track_accepts_the_two_engagement_events():
    """Cold ad traffic converts too sparsely to read conversion alone, so scroll
    depth and dwell are the early campaign signals. Both must be accepted."""
    for event, props in (
        ("landing_scroll_depth", {"page": "mobility-teams", "depth": 50}),
        ("landing_time_on_page", {"page": "relocation-checklist", "seconds": 30}),
    ):
        r = client.post("/api/public/track", json={"event": event, "properties": props})
        assert r.status_code == 200, f"{event} rejected: {r.text}"
        assert r.json()["ok"] is True


def test_track_still_rejects_events_outside_the_allowlist():
    """The allow-list must stay an allow-list. Widening it for AIQ-1783 must not
    have turned it into a passthrough for arbitrary events from the public web."""
    r = client.post("/api/public/track", json={"event": "landing_scroll_depth_evil"})
    assert r.status_code in (400, 422)


def test_track_drops_free_text_properties():
    """Property keys are allow-listed so no free-text/PII can arrive from an
    unauthenticated caller. An un-listed key must not reach the event sink."""
    captured = {}

    import backend.app.routers.public_analytics as pa

    original = pa.emit_event
    pa.emit_event = lambda name, extra=None: captured.update({"name": name, "extra": extra or {}})
    try:
        r = client.post("/api/public/track", json={
            "event": "landing_scroll_depth",
            "properties": {"depth": 50, "email": "someone@example.com"},
        })
    finally:
        pa.emit_event = original

    assert r.status_code == 200
    assert "email" not in captured["extra"], "un-listed property leaked to the sink"
    assert captured["extra"].get("depth") == 50


# ── [AIQ-1781] the anonymity this endpoint's lawful basis depends on ───────────

def test_track_attaches_no_identifier_to_the_event():
    """This path runs BEFORE the ConsentBanner is answered, and deliberately so.

    That is defensible only while the stored event is genuinely anonymous: no user id,
    no case id, no request id, no IP — just an event name, a timestamp, and allow-listed
    campaign/engagement scalars. Nothing is written to or read from the visitor's device
    either, so ePrivacy Art. 5(3) is not engaged. On that basis EU ad traffic can be
    measured without consent, which is what the ADS geography rule relies on
    (docs/gtm/ADS-5_otto_campaign_brief.md, Geography) and what
    docs/security/ADS_public_track_lawful_basis.md records.

    Adding `user_id=`, `case_id=` or any client identifier to this call would quietly
    make that basis false while every other test still passed. This test is the tripwire.
    """
    captured = {}

    import backend.app.routers.public_analytics as pa

    original = pa.emit_event

    def _spy(name, **kwargs):
        captured.update({"name": name, "kwargs": kwargs})

    pa.emit_event = _spy
    try:
        r = client.post("/api/public/track", json={
            "event": "landing_page_view",
            "properties": {"utm_source": "meta", "utm_content": "A1", "page": "mobility-teams"},
        })
    finally:
        pa.emit_event = original

    assert r.status_code == 200
    identifying = {"user_id", "case_id", "canonical_case_id", "assignment_id", "request_id", "user_role"}
    leaked = identifying & set(captured["kwargs"])
    assert not leaked, (
        f"public track attached identifier(s) {sorted(leaked)} — this endpoint fires before "
        "consent, so it must stay anonymous. See docs/security/ADS_public_track_lawful_basis.md"
    )
    assert set(captured["kwargs"]) == {"extra"}, (
        f"unexpected kwargs on the pre-consent path: {sorted(set(captured['kwargs']) - {'extra'})}"
    )

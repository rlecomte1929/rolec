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

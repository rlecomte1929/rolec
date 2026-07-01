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

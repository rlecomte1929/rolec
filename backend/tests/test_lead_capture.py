import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient
from backend.main import app
from backend.app.db import Base, engine

Base.metadata.create_all(bind=engine)  # ensure leads table exists on SQLite harness

client = TestClient(app)


def test_capture_creates_lead_and_derives_domain():
    r = client.post("/api/public/lead-capture", json={
        "email": "jane@acme.com", "first_name": "Jane", "source": "marketing_site",
        "utm_source": "google", "utm_campaign": "brand",
    })
    assert r.status_code == 201, r.text
    assert r.json()["id"]


def test_capture_rejects_bad_email():
    r = client.post("/api/public/lead-capture", json={"email": "not-an-email"})
    assert r.status_code == 422

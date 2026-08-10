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


# ── [AIQ-1783] admin notification on capture ──────────────────────────────────

def test_capture_notifies_admins_without_personal_data():
    """ADS-3 requires leads to reach a MONITORED destination. The lead row alone is
    not that — Admin > Leads is a page someone must remember to open.

    The notification must carry the signal (domain, campaign, prospect match) and NOT
    the person: admin_notify's contract is non-PII content, and the lead's name, email
    and free-text message stay in the admin UI.
    """
    import backend.app.routers.lead_capture as lc

    calls = []
    original = lc.notify_admins_new_lead
    lc.notify_admins_new_lead = lambda **kw: calls.append(kw) or {}
    try:
        r = client.post("/api/public/lead-capture", json={
            "email": "carlos@globex.com", "first_name": "Carlos",
            "message": "Who do you work for? Globex", "utm_campaign": "ads-segment-b",
        })
    finally:
        lc.notify_admins_new_lead = original

    assert r.status_code == 201, r.text
    assert len(calls) == 1, "admins were not notified of a captured lead"
    kw = calls[0]
    assert kw["company_domain"] == "globex.com"
    assert kw["utm_campaign"] == "ads-segment-b"
    blob = repr(kw)
    assert "carlos@globex.com" not in blob, "lead email leaked into the notification"
    assert "Carlos" not in blob, "lead name leaked into the notification"


def test_capture_survives_a_failing_notification():
    """Fail-soft by contract. On paid traffic a notification error must never turn a
    captured lead into a failed submission — that is a bought click thrown away."""
    import backend.app.routers.lead_capture as lc

    def _boom(**_kw):
        raise RuntimeError("resend down")

    original = lc.notify_admins_new_lead
    lc.notify_admins_new_lead = _boom
    try:
        r = client.post("/api/public/lead-capture", json={"email": "dana@initech.com"})
    finally:
        lc.notify_admins_new_lead = original

    assert r.status_code == 201, "a notification failure broke lead capture"
    assert r.json()["id"]

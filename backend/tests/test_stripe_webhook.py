"""Transport tests for the Stripe webhook (Path A) — portable-webhook spec §4 + §8.

These exercise the router's HTTP contract with REAL Stripe signatures (so
`stripe.Webhook.construct_event` actually runs), while the fulfilment brain is patched
out — the brain's DB behaviour is covered by test_stripe_fulfillment.py. What we pin here:

  disabled → 503                     (spec §7, test #9)
  no secret configured → 503
  valid signature → 200 + brain result
  duplicate/ignored brain result → still 200   (spec §4, tests #2/#4)
  invalid signature → 400, brain NOT called    (spec §4, test #3)
  second secret in the comma-list verifies     (spec §2 dual-endpoint cutover)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("stripe")

from backend.app.routers import stripe_webhook as mod  # noqa: E402


class _DummySession:
    def __enter__(self):
        return object()

    def __exit__(self, *a):
        return False


@pytest.fixture
def client(monkeypatch):
    # Patch the brain (DB-free) and SessionLocal so no real connection is opened.
    calls = []

    def fake_fulfil(db, event):
        calls.append(event)
        return {"status": "applied", "case_id": "c1", "tier": "roadmap"}

    monkeypatch.setattr(mod, "fulfil_stripe_event", fake_fulfil)
    monkeypatch.setattr(mod, "SessionLocal", lambda: _DummySession())

    app = FastAPI()
    app.include_router(mod.router)
    c = TestClient(app)
    c._fulfil_calls = calls  # type: ignore[attr-defined]
    return c


def _payload(event_id="evt_1", event_type="checkout.session.completed") -> bytes:
    return json.dumps({
        "id": event_id,
        "type": event_type,
        "data": {"object": {"id": "cs_1", "amount_total": 80000, "currency": "eur",
                            "metadata": {"case_id": "c1", "tier": "roadmap"}}},
    }).encode()


def _sign(payload: bytes, secret: str, ts: int = 1_700_000_000) -> str:
    # Stripe v1 signature: HMAC-SHA256 over "<ts>.<payload>". construct_event recomputes
    # this and compares timing-safe; we disable tolerance in tests via a fixed ts.
    signed = f"{ts}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def _post(client, payload: bytes, sig: str):
    return client.post("/api/stripe/webhook", content=payload,
                       headers={"Stripe-Signature": sig, "Content-Type": "application/json"})


def test_disabled_returns_503(client, monkeypatch):
    monkeypatch.delenv("RELOPASS_STRIPE_ENABLED", raising=False)
    r = _post(client, _payload(), "t=1,v1=x")
    assert r.status_code == 503
    assert client._fulfil_calls == []


def test_enabled_but_no_secret_returns_503(client, monkeypatch):
    monkeypatch.setenv("RELOPASS_STRIPE_ENABLED", "true")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = _post(client, _payload(), "t=1,v1=x")
    assert r.status_code == 503


def test_valid_signature_fulfils_and_returns_200(client, monkeypatch):
    secret = "whsec_test_abc"
    monkeypatch.setenv("RELOPASS_STRIPE_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    payload = _payload()
    # construct_event enforces a 300s timestamp tolerance; pass no tolerance override by
    # signing with the current time.
    import time
    ts = int(time.time())
    r = _post(client, payload, _sign(payload, secret, ts))
    assert r.status_code == 200
    assert r.json() == {"status": "applied", "case_id": "c1", "tier": "roadmap"}
    assert len(client._fulfil_calls) == 1
    assert client._fulfil_calls[0]["id"] == "evt_1"  # brain got a plain dict


def test_invalid_signature_returns_400_and_skips_brain(client, monkeypatch):
    monkeypatch.setenv("RELOPASS_STRIPE_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_real")
    payload = _payload()
    bad = _sign(payload, "whsec_WRONG")  # signed with a different secret
    r = _post(client, payload, bad)
    assert r.status_code == 400
    assert client._fulfil_calls == []  # never fulfilled on a bad signature


def test_second_secret_in_list_verifies(client, monkeypatch):
    # Dual-endpoint cutover: STRIPE_WEBHOOK_SECRET is a comma-separated list; a payload
    # signed with the SECOND secret must still verify.
    import time
    good = "whsec_second"
    monkeypatch.setenv("RELOPASS_STRIPE_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", f"whsec_first, {good}")
    payload = _payload()
    r = _post(client, payload, _sign(payload, good, int(time.time())))
    assert r.status_code == 200
    assert len(client._fulfil_calls) == 1


def test_duplicate_brain_result_still_200(client, monkeypatch):
    import time
    secret = "whsec_dup"
    monkeypatch.setenv("RELOPASS_STRIPE_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(mod, "fulfil_stripe_event",
                        lambda db, event: {"status": "duplicate", "event_id": event["id"]})
    payload = _payload()
    r = _post(client, payload, _sign(payload, secret, int(time.time())))
    assert r.status_code == 200
    assert r.json()["status"] == "duplicate"

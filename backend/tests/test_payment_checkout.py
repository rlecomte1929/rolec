"""Checkout hardening (Phase 5) — kill switch + metadata.case_id resolution.

The checkout endpoint already had server-side pricing + auth (Phase A). Phase 5 adds:
  * RELOPASS_STRIPE_ENABLED kill switch → 503 when off
  * metadata.case_id (the value the webhook brain fulfils against) — WITHOUT it a paid
    checkout can never unlock the roadmap; if no billable case resolves → 409, not a
    Stripe session that takes un-fulfillable money.

Stripe is never contacted: requests.post + the case resolver are patched.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import payment as payment_mod
from backend.app.auth_deps import require_hr_or_employee


class _FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.text = ""

    def json(self):
        return self._p


def _client(monkeypatch, *, enabled=True, resolve="rc-1", post_resp=None, capture=None):
    if enabled:
        monkeypatch.setenv("RELOPASS_STRIPE_ENABLED", "true")
    else:
        monkeypatch.delenv("RELOPASS_STRIPE_ENABLED", raising=False)
    monkeypatch.setattr(payment_mod, "require_assignment_visibility",
                        lambda aid, u: {"id": aid, "canonical_case_id": "rc-1"})
    monkeypatch.setattr(payment_mod, "_resolve_billable_case_id", lambda a: resolve)
    if post_resp is not None:
        def fake_post(url, data=None, auth=None, timeout=None):
            if capture is not None:
                capture["data"] = data
            return post_resp
        monkeypatch.setattr(payment_mod.requests, "post", fake_post)

    app = FastAPI()
    app.include_router(payment_mod.router)
    app.dependency_overrides[require_hr_or_employee] = lambda: {"id": "u1", "role": "employee"}
    return TestClient(app)


def _post(client, tier="roadmap"):
    return client.post("/api/payment/checkout", json={"assignmentId": "a1", "tier": tier})


def test_checkout_disabled_returns_503(monkeypatch):
    r = _post(_client(monkeypatch, enabled=False))
    assert r.status_code == 503


def test_checkout_bad_tier_returns_400(monkeypatch):
    r = _post(_client(monkeypatch), tier="premium")
    assert r.status_code == 400


def test_checkout_unresolvable_case_returns_409(monkeypatch):
    # No billable relocation_cases id → refuse, don't take un-fulfillable money.
    r = _post(_client(monkeypatch, resolve=None))
    assert r.status_code == 409


def test_checkout_missing_secret_returns_500(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    r = _post(_client(monkeypatch, resolve="rc-1"))
    assert r.status_code == 500


def test_checkout_sets_case_id_metadata(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    cap = {}
    client = _client(monkeypatch, resolve="rc-99",
                     post_resp=_FakeResp(200, {"url": "https://checkout.stripe/x"}), capture=cap)
    r = _post(client)
    assert r.status_code == 200
    assert r.json()["checkoutUrl"] == "https://checkout.stripe/x"
    # the resolved case_id is what the webhook brain will flip access_tier on
    assert cap["data"]["metadata[case_id]"] == "rc-99"
    assert cap["data"]["metadata[tier]"] == "roadmap"
    # server-side price is still fixed (not client-forgeable)
    assert cap["data"]["line_items[0][price_data][unit_amount]"] == "80000"

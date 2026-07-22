"""POST /api/payment/checkout must require an authenticated, authorised caller.

The endpoint hits Stripe with the platform secret key and embeds an assignmentId.
Unauthenticated, it was an IDOR + unauthenticated-resource-consumption hole. These
pin: 401 without auth, 403 for a cross-case assignmentId, and — with valid auth +
visibility — the request gets PAST authz (to the Stripe-config branch).
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import payment

_BODY = {"assignmentId": "a1", "tier": "roadmap"}


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_checkout_requires_authentication(client):
    # No auth header, no override → the dependency rejects.
    r = client.post("/api/payment/checkout", json=_BODY)
    assert r.status_code in (401, 403)


def test_checkout_rejects_cross_case_assignment(client, monkeypatch):
    app.dependency_overrides[auth_deps.get_current_user] = lambda: {"id": "u1", "role": "EMPLOYEE"}

    def _deny(_aid, _user):
        raise HTTPException(status_code=403, detail="not your case")

    monkeypatch.setattr(payment, "require_assignment_visibility", _deny)
    r = client.post("/api/payment/checkout", json={"assignmentId": "someone-elses", "tier": "roadmap"})
    assert r.status_code == 403


def test_checkout_passes_authz_then_reaches_stripe_config(client, monkeypatch):
    app.dependency_overrides[auth_deps.get_current_user] = lambda: {"id": "u1", "role": "EMPLOYEE"}
    monkeypatch.setattr(payment, "require_assignment_visibility", lambda _aid, _user: {"id": _aid})
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    r = client.post("/api/payment/checkout", json=_BODY)
    # Past auth + authz — now blocked only by the (unset) Stripe config, proving the
    # gate lets a legitimate caller through.
    assert r.status_code == 500
    assert "not configured" in r.text.lower()

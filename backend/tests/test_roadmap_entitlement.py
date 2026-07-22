"""Server-side roadmap paywall (Phase 4a) — flag-gated, fail-open enforcement.

Pins the decision logic (is_roadmap_unlocked / assert_roadmap_access) and the status
endpoint contract. The resolver SQL is validated separately against the real Postgres
schema via a rollback transaction (the access_tier column isn't in the sqlite test DB).

The load-bearing property: with the flag OFF (default) everything is unlocked, so wiring
the gate into the roadmap endpoints is a no-op until an operator turns it on.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.services import roadmap_entitlement as ent


# ── decision logic ───────────────────────────────────────────────────────────

def test_paywall_off_is_always_unlocked(monkeypatch):
    monkeypatch.delenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", raising=False)
    # Flag off short-circuits before any DB lookup — a free tier is still unlocked.
    monkeypatch.setattr(ent, "resolve_entitlement",
                        lambda cid: pytest.fail("must not resolve when flag off"))
    assert ent.is_roadmap_unlocked("c1") is True
    ent.assert_roadmap_access("c1")  # no raise


def test_paywall_on_free_tier_locks(monkeypatch):
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    monkeypatch.setattr(ent, "resolve_entitlement",
                        lambda cid: {"access_tier": "free", "payment_status": "unpaid"})
    assert ent.is_roadmap_unlocked("c1") is False
    with pytest.raises(HTTPException) as ei:
        ent.assert_roadmap_access("c1")
    assert ei.value.status_code == 402
    assert ei.value.detail["error"] == "roadmap_locked"


@pytest.mark.parametrize("tier", ["roadmap", "essentials"])
def test_paywall_on_paid_tier_unlocks(monkeypatch, tier):
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    monkeypatch.setattr(ent, "resolve_entitlement", lambda cid: {"access_tier": tier})
    assert ent.is_roadmap_unlocked("c1") is True
    ent.assert_roadmap_access("c1")  # no raise


def test_paywall_on_unresolved_fails_open(monkeypatch):
    # Unknown case / missing column → None → GRANT (never lock a legit user out).
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    monkeypatch.setattr(ent, "resolve_entitlement", lambda cid: None)
    assert ent.is_roadmap_unlocked("c1") is True
    ent.assert_roadmap_access("c1")  # no raise


# ── status endpoint ──────────────────────────────────────────────────────────

def _status_client(monkeypatch, ent_row, flag_on):
    from backend.app.routers import payment as payment_mod
    from backend.app.auth_deps import require_hr_or_employee

    monkeypatch.setattr(payment_mod, "require_case_access", lambda cid, u: {})
    monkeypatch.setattr(payment_mod, "resolve_entitlement", lambda cid: ent_row)
    monkeypatch.setattr(payment_mod, "roadmap_paywall_enabled", lambda: flag_on)

    app = FastAPI()
    app.include_router(payment_mod.router)
    app.dependency_overrides[require_hr_or_employee] = lambda: {"id": "u1", "role": "employee"}
    return TestClient(app)


def test_status_flag_off_reports_unlocked(monkeypatch):
    c = _status_client(monkeypatch, {"access_tier": "free", "payment_status": "unpaid"}, False)
    r = c.get("/api/payment/status/case-1")
    assert r.status_code == 200
    body = r.json()
    assert body["access_tier"] == "free"
    assert body["roadmap_unlocked"] is True   # flag off → unlocked


def test_status_flag_on_free_reports_locked(monkeypatch):
    c = _status_client(monkeypatch, {"access_tier": "free", "payment_status": "unpaid"}, True)
    body = c.get("/api/payment/status/case-1").json()
    assert body["roadmap_unlocked"] is False


def test_status_flag_on_paid_reports_unlocked(monkeypatch):
    c = _status_client(monkeypatch, {"access_tier": "roadmap", "payment_status": "roadmap_paid"}, True)
    body = c.get("/api/payment/status/case-1").json()
    assert body["access_tier"] == "roadmap"
    assert body["payment_status"] == "roadmap_paid"
    assert body["roadmap_unlocked"] is True


def test_status_flag_on_unresolved_fails_open(monkeypatch):
    c = _status_client(monkeypatch, None, True)  # resolve returns None
    body = c.get("/api/payment/status/case-1").json()
    assert body["access_tier"] == "free"
    assert body["roadmap_unlocked"] is True   # fail-open

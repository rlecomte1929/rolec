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

def _stub_lookup(monkeypatch, row, available=True):
    """Pin the entitlement lookup. `available=False` = the store was unreachable."""
    monkeypatch.setattr(
        ent, "lookup_entitlement",
        lambda cid: ent.EntitlementLookup(row, available),
    )


def test_paywall_off_is_always_unlocked(monkeypatch):
    monkeypatch.delenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", raising=False)
    # Flag off short-circuits before any DB lookup — a free tier is still unlocked.
    monkeypatch.setattr(ent, "lookup_entitlement",
                        lambda cid: pytest.fail("must not resolve when flag off"))
    assert ent.is_roadmap_unlocked("c1") is True
    ent.assert_roadmap_access("c1")  # no raise


def test_paywall_on_free_tier_locks(monkeypatch):
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    _stub_lookup(monkeypatch, {"access_tier": "free", "payment_status": "unpaid"})
    assert ent.is_roadmap_unlocked("c1") is False
    with pytest.raises(HTTPException) as ei:
        ent.assert_roadmap_access("c1")
    assert ei.value.status_code == 402
    assert ei.value.detail["error"] == "roadmap_locked"


@pytest.mark.parametrize("tier", ["roadmap", "essentials"])
def test_paywall_on_paid_tier_unlocks(monkeypatch, tier):
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    _stub_lookup(monkeypatch, {"access_tier": tier})
    assert ent.is_roadmap_unlocked("c1") is True
    ent.assert_roadmap_access("c1")  # no raise


def test_paywall_on_store_unreachable_fails_open(monkeypatch):
    # DB error / un-migrated column → we know NOTHING about this case → GRANT.
    # Never lock a paying user out because the pooler blipped.
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    _stub_lookup(monkeypatch, None, available=False)
    assert ent.is_roadmap_unlocked("c1") is True
    ent.assert_roadmap_access("c1")  # no raise


def test_paywall_on_unknown_case_fails_closed(monkeypatch):
    # AIQ-1699: the store WAS consulted and no case matches → a resolved "not
    # entitled", not an outage. This used to grant the €800 roadmap for free.
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    _stub_lookup(monkeypatch, None, available=True)
    assert ent.is_roadmap_unlocked("c1") is False
    with pytest.raises(HTTPException) as ei:
        ent.assert_roadmap_access("c1")
    assert ei.value.status_code == 402


def test_blank_case_id_is_resolved_not_an_outage():
    # An empty id can't be a DB failure — it must not buy a fail-open.
    assert ent.lookup_entitlement("") == ent.EntitlementLookup(None, True)
    assert ent.lookup_entitlement("   ") == ent.EntitlementLookup(None, True)


def test_resolve_entitlement_still_returns_the_row(monkeypatch):
    # Back-compat wrapper: callers that only want the row keep working.
    _stub_lookup(monkeypatch, {"access_tier": "roadmap"})
    assert ent.resolve_entitlement("c1") == {"access_tier": "roadmap"}
    _stub_lookup(monkeypatch, None, available=False)
    assert ent.resolve_entitlement("c1") is None


# ── status endpoint ──────────────────────────────────────────────────────────

def _status_client(monkeypatch, ent_row, flag_on, available=True):
    from backend.app.routers import payment as payment_mod
    from backend.app.auth_deps import require_hr_or_employee

    monkeypatch.setattr(payment_mod, "require_case_access", lambda cid, u: {})
    monkeypatch.setattr(payment_mod, "lookup_entitlement",
                        lambda cid: ent.EntitlementLookup(ent_row, available))
    # The decision now lives in the service module, so the flag has to be set for real —
    # stubbing a `roadmap_paywall_enabled` name on the router would no longer affect it.
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true" if flag_on else "false")

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


def test_status_flag_on_store_unreachable_fails_open(monkeypatch):
    c = _status_client(monkeypatch, None, True, available=False)
    body = c.get("/api/payment/status/case-1").json()
    assert body["access_tier"] == "free"
    assert body["roadmap_unlocked"] is True   # outage → fail open, as before


def test_status_flag_on_unknown_case_fails_closed(monkeypatch):
    # AIQ-1699: the status endpoint must agree with assert_roadmap_access. It used to
    # report unlocked=true here, so the UI showed the roadmap for an id with no case row.
    c = _status_client(monkeypatch, None, True, available=True)
    body = c.get("/api/payment/status/case-1").json()
    assert body["access_tier"] == "free"
    assert body["roadmap_unlocked"] is False


# ── [AIQ-2142] entitlement served as data (replaces the old client roadmap-paywall build flag) ──

def _view(monkeypatch, row, *, flag_on, available=True):
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true" if flag_on else "false")
    return ent.roadmap_entitlement_view(ent.EntitlementLookup(row, available))


def test_view_flag_off_is_unlocked_no_gate(monkeypatch):
    v = _view(monkeypatch, {"access_tier": "free"}, flag_on=False)
    assert v["unlocked"] is True
    assert v["gate_stage"] == "none"
    assert v["price_cents"] == ent.ROADMAP_PRICE_CENTS
    assert v["reason"] == ""


def test_view_flag_on_free_unknown_funder_locks_with_default_view(monkeypatch):
    # No funder → no enabled policy speaks → descriptive fields stay default, but the tier
    # check still locks a free case.
    v = _view(monkeypatch, {"access_tier": "free"}, flag_on=True)
    assert v["unlocked"] is False
    assert v["gate_stage"] == "none"


def test_view_sponsor_funder_never_gated_and_priced_zero(monkeypatch):
    v = _view(monkeypatch, {"access_tier": "free", "funding_source": "sponsor"}, flag_on=True)
    assert v["unlocked"] is True          # a sponsored move's gate falls nowhere
    assert v["gate_stage"] == "none"
    assert v["price_cents"] == 0
    assert v["reason"]                    # the sponsor rationale is surfaced to the client


def test_view_store_unreachable_fails_open_default_view(monkeypatch):
    v = _view(monkeypatch, None, flag_on=True, available=False)
    assert v["unlocked"] is True
    assert v["gate_stage"] == "none"


def test_view_unlocked_never_disagrees_with_the_enforcement_gate(monkeypatch):
    # The whole point of serving entitlement as data: what the client renders can never
    # diverge from what assert_roadmap_access enforces, because both read the same decision.
    monkeypatch.setenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "true")
    for row, avail in [
        ({"access_tier": "free"}, True),
        ({"access_tier": "roadmap"}, True),
        ({"access_tier": "free", "funding_source": "sponsor"}, True),
        (None, True),
        (None, False),
    ]:
        found = ent.EntitlementLookup(row, avail)
        assert ent.roadmap_entitlement_view(found)["unlocked"] == ent.unlocked_from_lookup(found)


def test_status_serves_the_entitlement_object(monkeypatch):
    # The client reads `entitlement` (data), not a build flag; the top-level roadmap_unlocked
    # alias stays consistent with entitlement.unlocked.
    c = _status_client(monkeypatch, {"access_tier": "free", "payment_status": "unpaid"}, True)
    body = c.get("/api/payment/status/case-1").json()
    assert "entitlement" in body
    e = body["entitlement"]
    assert set(e) == {"unlocked", "gate_stage", "price_cents", "reason"}
    assert e["unlocked"] == body["roadmap_unlocked"]
    assert e["unlocked"] is False   # flag on + free tier → locked

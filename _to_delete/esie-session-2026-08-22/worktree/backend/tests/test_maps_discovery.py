"""
GAP 5 — maps discovery adapter + admin discover/import endpoints.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app.services import maps_discovery, supplier_registry  # noqa: E402
from backend.app.routers import admin_catalog  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

def test_disabled_returns_empty(monkeypatch):
    monkeypatch.setenv("DISCOVERY_PROVIDER", "disabled")
    assert maps_discovery.search_businesses("movers", "Oslo", "Norway") == []


def test_unset_provider_returns_empty(monkeypatch):
    monkeypatch.delenv("DISCOVERY_PROVIDER", raising=False)
    assert maps_discovery.search_businesses("movers", "Oslo", "Norway") == []


def test_google_places_without_key_returns_empty(monkeypatch):
    monkeypatch.setenv("DISCOVERY_PROVIDER", "google_places")
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    assert maps_discovery.search_businesses("movers", "Oslo", "Norway") == []


def test_build_query_from_config():
    # sourced from VEN-01 SERVICE_CATEGORY_SEARCH_TERMS (first template, {city} filled)
    assert maps_discovery._build_query("movers", "Berlin") == "international removals Berlin"
    assert maps_discovery._build_query("legal_admin", "Paris") == "immigration lawyer Paris"
    # registry slug 'living_areas' aliases to config key 'housing'
    assert maps_discovery._build_query("living_areas", "Paris") == "relocation housing agency Paris"
    # unknown slug → bare fallback
    assert maps_discovery._build_query("weird_cat", "Oslo") == "Oslo weird_cat"


def test_provider_status_disabled(monkeypatch):
    monkeypatch.setenv("DISCOVERY_PROVIDER", "disabled")
    monkeypatch.delenv("DISCOVERY_MAX_RESULTS", raising=False)
    st = maps_discovery.provider_status()
    assert st["provider"] == "disabled" and st["configured"] is False
    assert st["max_results"] == 20  # default cap = config max_candidates_to_fetch


def test_max_results_env_and_clamp(monkeypatch):
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "3")
    assert maps_discovery._max_results() == 3
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "999")  # clamped to 60
    assert maps_discovery._max_results() == 60
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "junk")  # falls back to config default
    assert maps_discovery._max_results() == 20


def test_google_places_v1_parses_website_and_caps(monkeypatch):
    # New Places v1 API: POST → data['places']; returns websiteUri in one call.
    monkeypatch.setenv("DISCOVERY_PROVIDER", "google_places")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "3")

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"places": [
                {"id": f"p{i}", "displayName": {"text": f"biz{i}"},
                 "websiteUri": f"https://biz{i}.example", "nationalPhoneNumber": "+1",
                 "formattedAddress": "Berlin", "rating": 4.5, "userRatingCount": 40,
                 "businessStatus": "OPERATIONAL"}
                for i in range(5)
            ]}

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp())
    out = maps_discovery.search_businesses("movers", "Berlin", "DE")
    assert len(out) == 3  # capped
    assert out[0]["website"] == "https://biz0.example"  # v1 returns website
    assert out[0]["name"] == "biz0" and out[0]["place_id"] == "p0"


def test_refresh_vendor_by_place_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "p1", "rating": 4.2, "userRatingCount": 55, "businessStatus": "OPERATIONAL"}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    r = maps_discovery.refresh_vendor_by_place_id("p1")
    assert r["rating"] == 4.2 and r["user_ratings_total"] == 55
    # no key → None
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    assert maps_discovery.refresh_vendor_by_place_id("p1") is None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def app_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    # admin_catalog imports SessionLocal lazily from ..db inside the endpoints.
    import backend.app.db as appdb
    monkeypatch.setattr(appdb, "SessionLocal", maker, raising=False)
    monkeypatch.setattr(supplier_registry, "SessionLocal", maker, raising=False)
    app = FastAPI()
    app.include_router(admin_catalog.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "is_admin": True}
    return TestClient(app), maker


def _stub_ss(monkeypatch, *, allowlisted=True, quota_allowed=True, remaining=19):
    import backend.app.services.scrape_safety as ss
    monkeypatch.setattr(ss, "is_destination_allowlisted", lambda c, co: allowlisted)
    monkeypatch.setattr(ss, "get_quota_state", lambda k: {"day": "d", "used": 0, "limit": 20, "remaining": remaining})
    monkeypatch.setattr(ss, "check_and_increment_quota",
                        lambda k: {"allowed": quota_allowed, "day": "d", "used": 20 - remaining, "limit": 20, "remaining": remaining})


def _stub_provider(monkeypatch, provider="apify", configured=True, results=None, max_results=10):
    monkeypatch.setattr(maps_discovery, "provider_status",
                        lambda: {"provider": provider, "configured": configured, "max_results": max_results})
    if results is not None:
        monkeypatch.setattr(maps_discovery, "search_businesses", lambda cat, city, country: results)


def test_discover_requires_allowlist(app_client, monkeypatch):
    client, _ = app_client
    _stub_ss(monkeypatch, allowlisted=False)
    resp = client.post("/api/admin/catalog/discover", json={"category": "movers", "city": "Nowhere", "country": "Narnia"})
    assert resp.status_code == 400


def test_discover_disabled_no_quota_charged(app_client, monkeypatch):
    client, _ = app_client
    _stub_ss(monkeypatch, remaining=20)
    _stub_provider(monkeypatch, provider="disabled", configured=False)
    resp = client.post("/api/admin/catalog/discover", json={"category": "movers", "city": "Oslo", "country": "Norway"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0 and body["provider"] == "disabled"
    assert body["daily_remaining"] == 20  # not charged when provider is off


def test_discover_returns_results_when_configured(app_client, monkeypatch):
    client, _ = app_client
    _stub_ss(monkeypatch, quota_allowed=True, remaining=17)
    _stub_provider(monkeypatch, configured=True, results=[
        {"name": "Oslo Movers AS", "website": "https://oslomovers.no", "place_id": "p1",
         "formatted_address": "Oslo", "rating": 4.6, "user_ratings_total": 40}])
    resp = client.post("/api/admin/catalog/discover", json={"category": "movers", "city": "Oslo", "country": "Norway"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["already_in_catalog"] is False
    assert body["daily_remaining"] == 17


def test_discover_429_when_quota_exhausted(app_client, monkeypatch):
    client, _ = app_client
    _stub_ss(monkeypatch, quota_allowed=False, remaining=0)
    _stub_provider(monkeypatch, configured=True, results=[{"name": "X"}])
    resp = client.post("/api/admin/catalog/discover", json={"category": "movers", "city": "Oslo", "country": "Norway"})
    assert resp.status_code == 429


def test_discovery_status_includes_budget(app_client, monkeypatch):
    client, _ = app_client
    _stub_ss(monkeypatch, remaining=15)
    resp = client.get("/api/admin/catalog/discovery-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_remaining"] == 15
    assert "max_results" in body and "provider" in body


def test_import_creates_pending_suppliers(app_client, monkeypatch):
    client, maker = app_client
    resp = client.post("/api/admin/catalog/discover/import", json={
        "category": "movers", "city": "Oslo", "country": "Norway",
        "items": [{"name": "Oslo Movers AS", "website": "https://oslomovers.no", "place_id": "p1"}],
    })
    assert resp.status_code == 200
    assert resp.json()["created"] == 1
    # The created supplier is source=scraper_discovery with a pending capability.
    with maker() as session:
        rows = supplier_registry.list_pending_capabilities(session)
    assert any(r["supplier_name"] == "Oslo Movers AS" and r["source"] == "scraper_discovery" for r in rows)


def test_import_dedupes_existing(app_client, monkeypatch):
    client, maker = app_client
    with maker() as session:
        supplier_registry.create_supplier(session, {"name": "Oslo Movers AS", "status": "active"})
    resp = client.post("/api/admin/catalog/discover/import", json={
        "category": "movers", "city": "Oslo", "country": "Norway",
        "items": [{"name": "Oslo Movers AS", "place_id": "p1"}],
    })
    assert resp.json()["created"] == 0

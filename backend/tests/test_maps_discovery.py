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


def test_keyword_mapping():
    assert maps_discovery._keyword_for("movers") == "international moving company"
    assert maps_discovery._keyword_for("legal_admin") == "immigration lawyer expats"
    # unknown slug falls back to itself
    assert maps_discovery._keyword_for("weird_cat") == "weird_cat"


def test_provider_status_disabled(monkeypatch):
    monkeypatch.setenv("DISCOVERY_PROVIDER", "disabled")
    st = maps_discovery.provider_status()
    assert st["provider"] == "disabled" and st["configured"] is False
    assert st["max_results"] == 10  # default cap


def test_max_results_env_and_clamp(monkeypatch):
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "3")
    assert maps_discovery._max_results() == 3
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "999")  # clamped to 60
    assert maps_discovery._max_results() == 60
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "junk")  # falls back to default
    assert maps_discovery._max_results() == 10


def test_search_caps_google_places_results(monkeypatch):
    # google_places path slices results to the cap (5 raw → 3 with cap=3)
    monkeypatch.setenv("DISCOVERY_PROVIDER", "google_places")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    monkeypatch.setenv("DISCOVERY_MAX_RESULTS", "3")

    class _Resp:
        def json(self):
            return {"results": [{"name": f"biz{i}", "place_id": f"p{i}"} for i in range(5)]}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    out = maps_discovery.search_businesses("movers", "Oslo", "Norway")
    assert len(out) == 3


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

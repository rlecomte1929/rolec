"""
VEN-10 — HR self-serve vendor discovery: real Places → service_catalog_items
(the store the HR curation view reads).
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import maps_discovery, service_catalog  # noqa: E402
import backend.app.services.scrape_safety as scrape_safety  # noqa: E402
from backend.app.services.vendor_discovery import orchestrator  # noqa: E402
from backend.app.routers import hr_catalog  # noqa: E402
from backend.app.auth_deps import require_admin_or_hr  # noqa: E402

_SCHEMA = """
CREATE TABLE service_catalog_items (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  category TEXT NOT NULL, city TEXT, country TEXT, name TEXT NOT NULL,
  attributes_json TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT 'manual',
  active INTEGER NOT NULL DEFAULT 1, external_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by_user_id TEXT,
  UNIQUE (category, external_id)
);
"""

_CANDIDATES = [
    {"name": "Crown Relocations", "website": "https://www.crownrelo.com", "place_id": "p1",
     "rating": 4.6, "user_ratings_total": 120, "business_status": "OPERATIONAL"},
    {"name": "Dodgy Movers", "website": "https://dodgy.example", "place_id": "p2",
     "rating": 2.0, "user_ratings_total": 3, "business_status": "OPERATIONAL"},  # filtered out
]


@pytest.fixture
def catalog_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    monkeypatch.setattr(service_catalog.db, "engine", engine, raising=False)
    monkeypatch.setattr(maps_discovery, "search_businesses", lambda cat, city, country: list(_CANDIDATES))
    return engine


def test_discover_to_catalog_upserts_ranked(catalog_db):
    top = orchestrator.discover_to_catalog("movers", "Berlin", "Germany")
    assert [v["name"] for v in top] == ["Crown Relocations"]  # dodgy filtered by quality gate
    items = service_catalog.list_items(category="movers")
    assert len(items) == 1
    item = items[0]
    assert item["source"] == "scraper" and item["external_id"] == "p1"
    attrs = item["attributes_json"]
    assert attrs["rating"] == 4.6 and attrs["review_count"] == 120
    assert attrs["accreditation_tags"] == ["FIDI", "IAM"] and attrs["_provenance"] == "google_places"


def test_discover_to_catalog_idempotent(catalog_db):
    orchestrator.discover_to_catalog("movers", "Berlin", "Germany")
    orchestrator.discover_to_catalog("movers", "Berlin", "Germany")  # same place_id → upsert
    assert len(service_catalog.list_items(category="movers")) == 1


# ---- endpoint ----

def _app():
    app = FastAPI()
    app.include_router(hr_catalog.router)
    app.dependency_overrides[require_admin_or_hr] = lambda: {"id": "hr-1", "role": "HR", "company": "c1"}
    return TestClient(app)


@pytest.fixture
def hr_ready(catalog_db, monkeypatch):
    monkeypatch.setattr(hr_catalog.db, "get_hr_company_id", lambda uid: "c1", raising=False)
    monkeypatch.setattr(maps_discovery, "provider_status",
                        lambda: {"provider": "google_places", "configured": True, "max_results": 20})
    monkeypatch.setattr(scrape_safety, "is_destination_allowlisted", lambda c, co: True)
    monkeypatch.setattr(scrape_safety, "check_and_increment_quota",
                        lambda cid: {"allowed": True, "limit": 20, "remaining": 19, "used": 1, "day": "d"})
    return None


def test_hr_discover_success_populates_catalog(hr_ready):
    resp = _app().post("/api/hr/catalog/discover",
                       json={"category": "movers", "destination_city": "Berlin", "country": "Germany"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1 and body["vendors"][0]["name"] == "Crown Relocations"
    # appears in the curation source
    assert service_catalog.list_items(category="movers")[0]["name"] == "Crown Relocations"


def test_hr_discover_off_allowlist_opens_ticket(hr_ready, monkeypatch):
    monkeypatch.setattr(scrape_safety, "is_destination_allowlisted", lambda c, co: False)
    monkeypatch.setattr(scrape_safety, "open_destination_request",
                        lambda **k: {"id": "t1", "status": "pending"})
    resp = _app().post("/api/hr/catalog/discover",
                       json={"category": "movers", "destination_city": "Nowhere", "country": "Narnia"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_admin_approval" and resp.json()["count"] == 0


def test_hr_discover_provider_unconfigured_no_cost(hr_ready, monkeypatch):
    monkeypatch.setattr(maps_discovery, "provider_status",
                        lambda: {"provider": "disabled", "configured": False, "max_results": 20})
    called = {"n": 0}
    monkeypatch.setattr(scrape_safety, "check_and_increment_quota",
                        lambda cid: called.__setitem__("n", called["n"] + 1) or {"allowed": True})
    resp = _app().post("/api/hr/catalog/discover",
                       json={"category": "movers", "destination_city": "Berlin", "country": "Germany"})
    assert resp.json()["count"] == 0
    assert called["n"] == 0  # quota not charged when provider is off

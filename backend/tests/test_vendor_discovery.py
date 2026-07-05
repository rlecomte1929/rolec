"""
Tests for the vendor-discovery orchestrator slice (VEN-06/07/08/09), reconciled
to the suppliers registry.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app.services import maps_discovery, supplier_registry  # noqa: E402
from backend.app.services.vendor_discovery import orchestrator  # noqa: E402
from backend.app.services.vendor_discovery.vendor_ranker import filter_and_rank_vendors  # noqa: E402
from backend.app.services.vendor_discovery.accreditation_checker import check_accreditation  # noqa: E402
from backend.scripts import seed_priority_corridors as seeder  # noqa: E402


# ---- VEN-06 ranking ----

def test_ranker_quality_gates():
    result = filter_and_rank_vendors([
        {"name": "A", "rating": 4.5, "review_count": 100, "business_status": "OPERATIONAL"},
        {"name": "B", "rating": 2.0, "review_count": 5, "business_status": "OPERATIONAL"},   # fails rating+reviews
        {"name": "C", "rating": 4.2, "review_count": 200, "business_status": "CLOSED_PERMANENTLY"},  # fails status
    ])
    assert [v["name"] for v in result] == ["A"]


def test_ranker_reads_user_ratings_total_alias_and_caps_top_n():
    # maps_discovery emits user_ratings_total (not review_count) — must still count.
    cands = [
        {"name": f"V{i}", "rating": 4.5, "user_ratings_total": 50, "business_status": "OPERATIONAL"}
        for i in range(8)
    ]
    result = filter_and_rank_vendors(cands)
    assert len(result) == 5  # top_n from config


# ---- VEN-07 accreditation ----

def test_accreditation():
    assert check_accreditation({"name": "Crown Worldwide", "website": "https://www.crownrelo.com"}, "movers") == ["FIDI", "IAM"]
    assert check_accreditation({"name": "Random Movers", "website": "https://example.com"}, "movers") == []
    assert check_accreditation({"name": "Any Vendor", "website": "https://example.com"}, "schools") == []


# ---- VEN-08 orchestrator (→ suppliers pending) ----

@pytest.fixture
def sqlite(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(orchestrator, "SessionLocal", maker, raising=False)
    return maker


def test_orchestrator_imports_ranked_as_pending(sqlite, monkeypatch):
    monkeypatch.setattr(maps_discovery, "search_businesses", lambda cat, city, country: [
        {"name": "Crown Relocations", "website": "https://www.crownrelo.com", "place_id": "p1",
         "rating": 4.6, "user_ratings_total": 120, "business_status": "OPERATIONAL"},
        {"name": "Dodgy Movers", "website": "https://dodgy.example", "place_id": "p2",
         "rating": 2.1, "user_ratings_total": 3, "business_status": "OPERATIONAL"},  # filtered out
    ])
    imported = orchestrator.discover_and_store_vendors("movers", "Berlin", "DE")
    assert [v["name"] for v in imported] == ["Crown Relocations"]
    with sqlite() as session:
        pending = supplier_registry.list_pending_capabilities(session)
    row = next(r for r in pending if r["supplier_name"] == "Crown Relocations")
    assert row["source"] == "scraper_discovery" and row["service_category"] == "movers"
    assert row["country_code"] == "DE" and row["city_name"] == "Berlin"


def test_orchestrator_dedupes_on_rerun(sqlite, monkeypatch):
    monkeypatch.setattr(maps_discovery, "search_businesses", lambda cat, city, country: [
        {"name": "Crown Relocations", "website": "https://www.crownrelo.com", "place_id": "p1",
         "rating": 4.6, "user_ratings_total": 120, "business_status": "OPERATIONAL"},
    ])
    assert len(orchestrator.discover_and_store_vendors("movers", "Berlin", "DE")) == 1
    assert orchestrator.discover_and_store_vendors("movers", "Berlin", "DE") == []  # already exists


# ---- VEN-09 seeding script ----

def test_seeder_dry_run_counts_cells(monkeypatch):
    res = seeder.run(category="movers", dry_run=True)
    assert res["cells"] > 0 and res["imported"] == 0  # dry-run makes no calls/writes


def test_seeder_noop_when_provider_unconfigured(monkeypatch):
    monkeypatch.setattr(maps_discovery, "provider_status",
                        lambda: {"provider": "disabled", "configured": False, "max_results": 20})
    res = seeder.run(category="movers", dry_run=False)
    assert res == {"cells": 0, "imported": 0}  # safe no-op, zero cost

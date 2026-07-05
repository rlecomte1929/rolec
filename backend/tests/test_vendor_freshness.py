"""
VEN-11 — vendor freshness refresh, reconciled to the suppliers registry.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app.services import supplier_registry  # noqa: E402
from backend.app.tasks import vendor_freshness_refresh as job  # noqa: E402


@pytest.fixture
def sqlite(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(job, "SessionLocal", maker, raising=False)
    monkeypatch.setattr(supplier_registry, "SessionLocal", maker, raising=False)
    return maker


def _seed_discovery_supplier(session, name="Crown Relocations"):
    supplier_registry.create_supplier(session, {
        "name": name,
        "status": "active",
        "source": "scraper_discovery",
        "source_url": "https://www.google.com/maps/place/?q=place_id:PID123",
        "capabilities": [{"service_category": "movers", "coverage_scope_type": "city",
                          "country_code": "DE", "city_name": "Berlin",
                          "platform_vetting_status": "approved"}],
    })


def test_place_id_extraction():
    assert job._place_id_from("https://www.google.com/maps/place/?q=place_id:ABC") == "ABC"
    assert job._place_id_from("https://example.com") is None
    assert job._place_id_from(None) is None


def test_dry_run_checks_but_writes_nothing(sqlite, monkeypatch):
    with sqlite() as s:
        _seed_discovery_supplier(s)
    called = {"n": 0}
    monkeypatch.setattr(job, "refresh_vendor_by_place_id", lambda pid: called.__setitem__("n", called["n"] + 1))
    stats = job.refresh_stale_vendors(dry_run=True)
    assert stats["checked"] == 1 and stats["updated"] == 0
    assert called["n"] == 0  # no fetch in dry-run


def test_refresh_updates_scoring(sqlite, monkeypatch):
    with sqlite() as s:
        _seed_discovery_supplier(s)
    monkeypatch.setattr(job, "refresh_vendor_by_place_id",
                        lambda pid: {"place_id": pid, "rating": 4.7, "user_ratings_total": 210, "business_status": "OPERATIONAL"})
    stats = job.refresh_stale_vendors()
    assert stats == {"checked": 1, "updated": 1, "closed": 0, "errors": 0}
    with sqlite() as s:
        supplier = supplier_registry.list_suppliers(s)[0]
        full = supplier_registry.get_supplier(s, supplier["id"])
    assert full["scoring"]["average_rating"] == 4.7 and full["scoring"]["review_count"] == 210


def test_closed_vendor_suspended(sqlite, monkeypatch):
    with sqlite() as s:
        _seed_discovery_supplier(s)
    monkeypatch.setattr(job, "refresh_vendor_by_place_id",
                        lambda pid: {"place_id": pid, "rating": 3.0, "user_ratings_total": 5, "business_status": "CLOSED_PERMANENTLY"})
    stats = job.refresh_stale_vendors()
    assert stats["closed"] == 1
    with sqlite() as s:
        supplier = supplier_registry.list_suppliers(s)[0]
        full = supplier_registry.get_supplier(s, supplier["id"])
    assert full["capabilities"][0]["platform_vetting_status"] == "suspended"


def test_fresh_supplier_skipped(sqlite, monkeypatch):
    # a supplier verified just now is not re-checked
    with sqlite() as s:
        _seed_discovery_supplier(s)
    monkeypatch.setattr(job, "refresh_vendor_by_place_id",
                        lambda pid: {"place_id": pid, "rating": 4.0, "user_ratings_total": 50, "business_status": "OPERATIONAL"})
    job.refresh_stale_vendors()  # first run stamps last_verified_at = now
    stats2 = job.refresh_stale_vendors()  # second run: still fresh → skipped
    assert stats2["checked"] == 0

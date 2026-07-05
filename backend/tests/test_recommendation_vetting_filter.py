"""
Tests for GAP 3 — unapproved supplier capabilities must never reach employees.

Two employee-facing paths read supplier_service_capabilities:
  1. the recommendation engine, via supplier_registry.search_by_service_destination
  2. the marketplace router, via a direct Supabase query in _fetch_suppliers

Both must hard-filter platform_vetting_status == 'approved'.
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
from backend.app.services import supplier_registry  # noqa: E402
from backend.app.routers import marketplace as marketplace_router  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402


# ---------------------------------------------------------------------------
# Path 1 — recommendation engine (search_by_service_destination)
# ---------------------------------------------------------------------------

@pytest.fixture
def SessionMaker(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(supplier_registry, "SessionLocal", maker, raising=False)
    return maker


def _make_supplier(session, name, country_code, *, approve):
    supplier = supplier_registry.create_supplier(
        session,
        {
            "name": name,
            "status": "active",
            "capabilities": [
                {
                    "service_category": "movers",
                    "coverage_scope_type": "country",
                    "country_code": country_code,
                }
            ],
        },
    )
    cap_id = supplier["capabilities"][0]["id"]
    if approve:
        supplier_registry.approve_capability(session, cap_id, "admin-1", notes="ok")
    return supplier["id"]


def test_search_excludes_pending_includes_approved(SessionMaker):
    with SessionMaker() as session:
        approved_id = _make_supplier(session, "Approved Movers", "NO", approve=True)
        _make_supplier(session, "Pending Movers", "NO", approve=False)

        results = supplier_registry.search_by_service_destination(
            session, "movers", destination_country="NO"
        )
        ids = {r["item_id"] for r in results}
        assert approved_id in ids
        assert len(ids) == 1  # the pending supplier is filtered out


# ---------------------------------------------------------------------------
# Path 2 — marketplace router (direct Supabase query)
# ---------------------------------------------------------------------------

def _cap(status):
    return {
        "service_category": "movers",
        "country_code": "NO",
        "min_budget": None,
        "max_budget": None,
        "platform_vetting_status": status,
    }


def _supplier_row(sid, name, cap_status):
    return {
        "id": sid,
        "name": name,
        "description": None,
        "website": None,
        "verified": True,
        "supplier_scoring_metadata": {"average_rating": 4.5, "review_count": 10,
                                       "response_sla_hours": 24, "preferred_partner": False},
        "supplier_service_capabilities": [_cap(cap_status)],
    }


def test_marketplace_hides_unapproved(monkeypatch):
    monkeypatch.setattr(
        marketplace_router.main_db, "get_assignment_by_id",
        lambda aid: {"company_id": "c1", "destination_country": "NO", "origin_country": "FR"},
    )
    monkeypatch.setattr(marketplace_router, "_get_covered_benefit_keys", lambda aid: set())
    monkeypatch.setattr(marketplace_router, "_get_preferred_supplier_ids", lambda cid: set())
    monkeypatch.setattr(
        marketplace_router, "_fetch_suppliers",
        lambda dest: [
            _supplier_row("sup-approved", "Approved Co", "approved"),
            _supplier_row("sup-pending", "Pending Co", "pending"),
        ],
    )

    app = FastAPI()
    app.include_router(marketplace_router.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "emp-1", "role": "EMPLOYEE"}
    client = TestClient(app)

    resp = client.get("/api/employee/assignments/a1/marketplace")
    assert resp.status_code == 200
    ids = {v["id"] for v in resp.json()["vendors"]}
    assert "sup-approved" in ids
    assert "sup-pending" not in ids

"""
Tests for GAP 2 — cross-supplier pending-capability vetting queue.

Covers the service function list_pending_capabilities and the admin endpoint
GET /api/suppliers/capabilities/pending.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app.routers import suppliers as suppliers_router  # noqa: E402
from backend.app.services import supplier_registry  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402

_PENDING_KEYS = {
    "supplier_id", "supplier_name", "capability_id", "service_category",
    "country_code", "city_name", "source", "source_url", "created_at",
    # [AIQ-1788] Registry-harvested suppliers carry accreditation evidence, and the vetting
    # queue renders it — approving one without seeing WHICH register vouched for it is a
    # rubber stamp. None here: this lane is SQLite and has no supplier_accreditations table,
    # which is exactly the case list_pending_capabilities has to tolerate.
    "accreditation",
}


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
    monkeypatch.setattr(suppliers_router, "SessionLocal", maker, raising=False)
    return maker


def _seed(session):
    """Two suppliers: one pending cap, one approved cap. Returns pending cap id."""
    a = supplier_registry.create_supplier(session, {
        "name": "Pending Co", "status": "active",
        "source": "scraper_discovery", "source_url": "https://maps.example/p1",
        "capabilities": [{"service_category": "movers", "coverage_scope_type": "country",
                          "country_code": "NO"}],
    })
    b = supplier_registry.create_supplier(session, {
        "name": "Approved Co", "status": "active",
        "capabilities": [{"service_category": "banks", "coverage_scope_type": "country",
                          "country_code": "DE"}],
    })
    supplier_registry.approve_capability(session, b["capabilities"][0]["id"], "admin-1", notes="ok")
    return a["capabilities"][0]["id"]


def test_list_pending_capabilities_service(SessionMaker):
    with SessionMaker() as session:
        pending_cap_id = _seed(session)
        rows = supplier_registry.list_pending_capabilities(session)
        assert len(rows) == 1
        row = rows[0]
        assert row["capability_id"] == pending_cap_id
        assert row["supplier_name"] == "Pending Co"
        assert row["source"] == "scraper_discovery"
        assert set(row.keys()) == _PENDING_KEYS


def _admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(suppliers_router.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "is_admin": True}
    return app


def test_pending_endpoint_returns_only_pending(SessionMaker):
    with SessionMaker() as session:
        _seed(session)
    resp = TestClient(_admin_app()).get("/api/suppliers/capabilities/pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["capabilities"][0]["supplier_name"] == "Pending Co"


def test_pending_endpoint_requires_admin(SessionMaker):
    def _forbidden():
        raise HTTPException(status_code=403, detail="admin only")
    app = FastAPI()
    app.include_router(suppliers_router.router)
    app.dependency_overrides[require_admin] = _forbidden
    resp = TestClient(app).get("/api/suppliers/capabilities/pending")
    assert resp.status_code == 403

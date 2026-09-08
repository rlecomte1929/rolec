"""
Tests for GAP 1 — supplier capability vetting lifecycle + source provenance.

Service-level tests exercise supplier_registry directly; router-level tests mount
the real suppliers router with require_admin overridden and SessionLocal patched to
an in-memory SQLite engine built from the ORM models (so the new vetting/source
columns exist).
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


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def SessionMaker(engine, monkeypatch):
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(supplier_registry, "SessionLocal", maker, raising=False)
    monkeypatch.setattr(suppliers_router, "SessionLocal", maker, raising=False)
    return maker


def _make_supplier_with_capability(session, *, source="admin_manual", source_url=None):
    """Create an active supplier with one capability; return (supplier_id, capability_id)."""
    supplier = supplier_registry.create_supplier(
        session,
        {
            "name": "Norse Relocations",
            "status": "active",
            "source": source,
            "source_url": source_url,
            "capabilities": [
                {
                    "service_category": "movers",
                    "coverage_scope_type": "country",
                    "country_code": "NO",
                }
            ],
        },
    )
    cap = supplier["capabilities"][0]
    return supplier["id"], cap["id"]


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

def test_new_capability_defaults_pending(SessionMaker):
    with SessionMaker() as session:
        supplier_id, _ = _make_supplier_with_capability(session)
        supplier = supplier_registry.create_supplier(
            session,
            {"name": "Second Co", "status": "draft"},
        )
        added = supplier_registry.add_capability(
            session,
            supplier["id"],
            {"service_category": "banks", "coverage_scope_type": "country", "country_code": "NO"},
        )
        assert added["capabilities"][0]["platform_vetting_status"] == "pending"


def test_approve_sets_fields(SessionMaker):
    with SessionMaker() as session:
        _, cap_id = _make_supplier_with_capability(session)
        result = supplier_registry.approve_capability(
            session, cap_id, vetted_by_user_id="admin-1", notes="looks good"
        )
        cap = result["capabilities"][0]
        assert cap["platform_vetting_status"] == "approved"
        assert cap["vetted_by"] == "admin-1"
        assert cap["vetted_at"] is not None
        assert cap["vetting_notes"] == "looks good"


def test_reject_without_notes_raises(SessionMaker):
    with SessionMaker() as session:
        _, cap_id = _make_supplier_with_capability(session)
        with pytest.raises(ValueError):
            supplier_registry.reject_capability(session, cap_id, "admin-1", notes="")


def test_reject_with_notes_sets_rejected(SessionMaker):
    with SessionMaker() as session:
        _, cap_id = _make_supplier_with_capability(session)
        result = supplier_registry.reject_capability(
            session, cap_id, "admin-1", notes="unverifiable business"
        )
        cap = result["capabilities"][0]
        assert cap["platform_vetting_status"] == "rejected"
        assert cap["vetting_notes"] == "unverifiable business"


def test_create_supplier_persists_source(SessionMaker):
    with SessionMaker() as session:
        supplier = supplier_registry.create_supplier(
            session,
            {
                "name": "Directory Import Co",
                "source": "directory_import",
                "source_url": "https://eura.example/member/123",
            },
        )
        assert supplier["source"] == "directory_import"
        assert supplier["source_url"] == "https://eura.example/member/123"


# ---------------------------------------------------------------------------
# Router layer
# ---------------------------------------------------------------------------

def _admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(suppliers_router.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "is_admin": True}
    return app


def test_router_approve_returns_updated_supplier(SessionMaker):
    with SessionMaker() as session:
        supplier_id, cap_id = _make_supplier_with_capability(session)
    client = TestClient(_admin_app())
    resp = client.post(
        f"/api/suppliers/{supplier_id}/capabilities/{cap_id}/approve",
        json={"notes": "verified"},
    )
    assert resp.status_code == 200
    cap = resp.json()["capabilities"][0]
    assert cap["platform_vetting_status"] == "approved"


def test_router_reject_without_notes_returns_400(SessionMaker):
    with SessionMaker() as session:
        supplier_id, cap_id = _make_supplier_with_capability(session)
    client = TestClient(_admin_app())
    resp = client.post(
        f"/api/suppliers/{supplier_id}/capabilities/{cap_id}/reject",
        json={"notes": ""},
    )
    assert resp.status_code == 400

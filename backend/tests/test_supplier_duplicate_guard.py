"""[AIQ-1511] Duplicate-supplier guard.

Live incident: public.suppliers held 100 rows but only 90 distinct names — ten movers
existed twice, once with a UUID id and once with the recommendation-dataset id
'm-1'..'m-10', because the registry was seeded twice and nothing stopped it:
create_supplier() accepts an explicit id and there was neither a UNIQUE constraint on
name nor a duplicate-name check. Migration 20260913000000 removes the duplicates and
adds the constraint; these tests cover the application-side guard, so an admin gets a
clean 409 instead of a raw constraint violation (500).

Note SQLite (used here) does not carry the production functional UNIQUE index, so
these tests pin the *application* guard specifically — which is the layer that turns a
duplicate into a 409.
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
from backend.app.routers import suppliers as suppliers_router  # noqa: E402
from backend.app.services import supplier_registry  # noqa: E402
from backend.app.services.supplier_registry import DuplicateSupplierError  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def SessionMaker(engine, monkeypatch):
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(supplier_registry, "SessionLocal", maker, raising=False)
    monkeypatch.setattr(suppliers_router, "SessionLocal", maker, raising=False)
    return maker


@pytest.fixture
def client(SessionMaker):
    app = FastAPI()
    app.include_router(suppliers_router.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "role": "admin"}
    return TestClient(app)


# ── service layer ────────────────────────────────────────────────────────────

def test_create_supplier_rejects_exact_duplicate_name(SessionMaker):
    with SessionMaker() as s:
        supplier_registry.create_supplier(s, {"name": "Crown Relocations"})
        s.commit()
    with SessionMaker() as s:
        with pytest.raises(DuplicateSupplierError):
            supplier_registry.create_supplier(s, {"name": "Crown Relocations"})


def test_create_supplier_rejects_case_and_whitespace_variant(SessionMaker):
    """The real duplicates differed only by id — but a registry must also refuse
    'crown relocations' / '  CROWN RELOCATIONS  ' as the same company. Mirrors the
    migration's UNIQUE INDEX on lower(trim(name))."""
    with SessionMaker() as s:
        supplier_registry.create_supplier(s, {"name": "Crown Relocations"})
        s.commit()
    for variant in ("crown relocations", "  CROWN RELOCATIONS  ", "Crown  Relocations".replace("  ", " ")):
        with SessionMaker() as s:
            with pytest.raises(DuplicateSupplierError):
                supplier_registry.create_supplier(s, {"name": variant})


def test_explicit_id_does_not_bypass_the_guard(SessionMaker):
    """This is exactly how the incident happened: the second seed pass supplied an
    explicit id ('m-2') for a name that already existed under a UUID id."""
    with SessionMaker() as s:
        supplier_registry.create_supplier(s, {"name": "Crown Relocations"})  # uuid4 id
        s.commit()
    with SessionMaker() as s:
        with pytest.raises(DuplicateSupplierError):
            supplier_registry.create_supplier(s, {"id": "m-2", "name": "Crown Relocations"})


def test_distinct_names_still_create_fine(SessionMaker):
    with SessionMaker() as s:
        a = supplier_registry.create_supplier(s, {"name": "Crown Relocations"})
        b = supplier_registry.create_supplier(s, {"name": "Asian Tigers"})
        s.commit()
    assert a["id"] != b["id"]
    assert {a["name"], b["name"]} == {"Crown Relocations", "Asian Tigers"}


# ── router ───────────────────────────────────────────────────────────────────

def test_post_duplicate_name_returns_409(client):
    assert client.post("/api/suppliers", json={"name": "Crown Relocations"}).status_code == 200
    r = client.post("/api/suppliers", json={"name": "  crown relocations "})
    assert r.status_code == 409, r.text
    assert "already exists" in r.json()["detail"].lower()


def test_post_new_name_returns_200(client):
    r = client.post("/api/suppliers", json={"name": "Santa Fe Relocation"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Santa Fe Relocation"


def test_validation_error_is_still_400_not_409(client):
    """The 409 must not swallow ordinary validation failures."""
    r = client.post("/api/suppliers", json={"name": ""})
    assert r.status_code == 400, r.text


def test_non_admin_cannot_create_supplier(SessionMaker):
    """AIQ-1511 validation criterion 6: an employee hitting the admin create route is
    rejected. require_admin is the enforcement point — assert it is actually wired."""
    from fastapi import HTTPException

    def _deny():
        raise HTTPException(status_code=403, detail="Admin access required")

    app = FastAPI()
    app.include_router(suppliers_router.router)
    app.dependency_overrides[require_admin] = _deny
    c = TestClient(app)
    assert c.post("/api/suppliers", json={"name": "Sneaky Movers"}).status_code == 403

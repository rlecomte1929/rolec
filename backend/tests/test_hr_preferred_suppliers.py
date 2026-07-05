"""
GAP 4 — HR preferred-suppliers DB helpers: supplier vetting-state lookup + the
duplicate-add / remove-return bug fixes in backend/db/companies.py.
"""
from __future__ import annotations

import os
import sys

import uuid as _uuid

import pytest
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# conftest installs a MagicMock for backend.database, so exercise the real
# CompaniesMixin methods directly against a SQLite engine instead of the mock.
from backend.db.companies import CompaniesMixin  # noqa: E402


class _TestDB(CompaniesMixin):
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _rows_to_list(rows):
        return [
            {k: str(v) if isinstance(v, _uuid.UUID) else v for k, v in r._mapping.items()}
            for r in rows
        ]

_SCHEMA = """
CREATE TABLE suppliers (id TEXT PRIMARY KEY, name TEXT, status TEXT);
CREATE TABLE supplier_service_capabilities (
    id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL,
    service_category TEXT,
    platform_vetting_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE company_preferred_suppliers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL,
    service_category TEXT,
    priority_rank INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE UNIQUE INDEX idx_cps_unique
    ON company_preferred_suppliers(company_id, supplier_id, coalesce(service_category, ''));
"""


@pytest.fixture
def tdb():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        for stmt in _SCHEMA.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        conn.execute(text("INSERT INTO suppliers (id, name, status) VALUES ('S1','Approved Co','active')"))
        conn.execute(text("INSERT INTO suppliers (id, name, status) VALUES ('S2','Pending Co','active')"))
        conn.execute(text(
            "INSERT INTO supplier_service_capabilities (id, supplier_id, service_category, platform_vetting_status) "
            "VALUES ('c1','S1','movers','approved')"))
        conn.execute(text(
            "INSERT INTO supplier_service_capabilities (id, supplier_id, service_category, platform_vetting_status) "
            "VALUES ('c2','S2','movers','pending')"))
    return _TestDB(engine)


def test_vetting_state_approved(tdb):
    assert tdb.get_supplier_vetting_state("S1", "movers") == {"exists": True, "has_approved": True}


def test_vetting_state_only_pending(tdb):
    st = tdb.get_supplier_vetting_state("S2", "movers")
    assert st["exists"] is True
    assert st["has_approved"] is False


def test_vetting_state_unknown_supplier(tdb):
    st = tdb.get_supplier_vetting_state("nope", None)
    assert st["exists"] is False
    assert st["has_approved"] is False


def test_duplicate_add_does_not_raise(tdb):
    tdb.add_company_preferred_supplier("c1", "S1", service_category="movers")
    # Second add of the same (company, supplier, category) must not raise.
    tdb.add_company_preferred_supplier("c1", "S1", service_category="movers", notes="updated")
    rows = tdb.list_company_preferred_suppliers("c1", "movers")
    assert len(rows) == 1


def test_remove_with_service_category_returns_count(tdb):
    tdb.add_company_preferred_supplier("c1", "S1", service_category="movers")
    removed = tdb.remove_company_preferred_supplier("c1", "S1", "movers")
    assert removed == 1
    assert tdb.list_company_preferred_suppliers("c1", "movers") == []

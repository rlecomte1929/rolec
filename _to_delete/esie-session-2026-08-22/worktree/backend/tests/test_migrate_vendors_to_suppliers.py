"""
GAP 6 — migrate_vendors_to_suppliers: copies active vendors into System A as
pending suppliers, idempotently, with category-label → slug mapping.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app.services import supplier_registry  # noqa: E402
from backend.scripts import migrate_vendors_to_suppliers as mig  # noqa: E402

_VENDORS_DDL = """
CREATE TABLE vendors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    website_url TEXT,
    email TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);
"""


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)  # suppliers, supplier_service_capabilities, scoring
    with engine.begin() as conn:
        conn.execute(text(_VENDORS_DDL))
        conn.execute(text("INSERT INTO vendors (id,name,category,website_url,email,is_active) VALUES "
                          "('v1','BerlinReloc GmbH','Housing Search','https://berlinreloc.de',NULL,1)"))
        conn.execute(text("INSERT INTO vendors (id,name,category,website_url,email,is_active) VALUES "
                          "('v2','SIRVA Worldwide','Moving & Freight',NULL,NULL,1)"))
        conn.execute(text("INSERT INTO vendors (id,name,category,website_url,email,is_active) VALUES "
                          "('v3','Inactive Co','Tax Advisory',NULL,NULL,0)"))
    return sessionmaker(bind=engine)()


def test_migrate_creates_pending_suppliers(session):
    result = mig.migrate(session)
    assert result == {"created": 2, "skipped": 0}  # inactive vendor excluded
    pending = supplier_registry.list_pending_capabilities(session)
    by_name = {r["supplier_name"]: r for r in pending}
    assert by_name["BerlinReloc GmbH"]["service_category"] == "living_areas"
    assert by_name["BerlinReloc GmbH"]["source"] == "directory_import"
    assert by_name["SIRVA Worldwide"]["service_category"] == "movers"


def test_migrate_is_idempotent(session):
    mig.migrate(session)
    result2 = mig.migrate(session)
    assert result2 == {"created": 0, "skipped": 2}
    # still exactly 2 suppliers
    assert len(supplier_registry.list_suppliers(session)) == 2


def test_unknown_category_falls_back_to_general(session):
    session.execute(text("INSERT INTO vendors (id,name,category,is_active) VALUES ('v4','Mystery Co','Concierge Weird',1)"))
    session.commit()
    mig.migrate(session)
    pending = supplier_registry.list_pending_capabilities(session)
    mystery = next(r for r in pending if r["supplier_name"] == "Mystery Co")
    assert mystery["service_category"] == "general"

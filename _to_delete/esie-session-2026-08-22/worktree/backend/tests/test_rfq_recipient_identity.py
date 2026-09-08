"""[AIQ-1520] An employee-led RFQ must actually reach the suppliers HR approved.

Before this, POST /api/rfqs resolved a recipient to `suppliers.vendor_id` and validated it
against the `vendors` table. Measured in prod: only 8 of 90 suppliers had a vendor_id, the
`vendors` table held 8 rows against 90 suppliers, and **ZERO of the 11 HR-approved movers
resolved** — every employee-led RFQ would have 400'd.

The recipient is a supplier now. The employee shortlists a recommendation item_id
(= service_catalog_items.external_id), which is a different id space from suppliers.id — the
two only ever overlapped by string coincidence, and the AIQ-1511 dedupe removed the overlap.
Migration 20260918000000 adds the explicit service_catalog_items.supplier_id link.

These tests pin the resolution, and the two failure modes that used to be silent.
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
from backend.app.services import rfq_recipient_mapping as rrm  # noqa: E402
from backend.app.services import supplier_registry  # noqa: E402

# service_catalog_items has no ORM model — create the slice we need.
_CATALOG_DDL = """
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY,
    category TEXT,
    name TEXT,
    external_id TEXT,
    supplier_id TEXT,
    active INTEGER DEFAULT 1
);
"""


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with eng.begin() as conn:
        conn.execute(text(_CATALOG_DDL))
    return eng


@pytest.fixture
def SessionMaker(engine, monkeypatch):
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr(rrm, "SessionLocal", maker, raising=False)
    monkeypatch.setattr(supplier_registry, "SessionLocal", maker, raising=False)
    return maker


@pytest.fixture
def seeded(SessionMaker, engine):
    """One supplier ('Crown Relocations'), reachable via a catalog item whose external_id is
    the OLD dataset id 'm-2' — precisely the shape that broke: the catalog still points at
    'm-2', but no supplier has that id any more."""
    with SessionMaker() as s:
        crown = supplier_registry.create_supplier(s, {"name": "Crown Relocations"})
        s.commit()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO service_catalog_items (id, category, name, external_id, supplier_id) "
            "VALUES ('cat-1', 'movers', 'Crown Relocations', 'm-2', :sid)"
        ), {"sid": crown["id"]})
        # A catalog item with NO supplier on record — must fail honestly, not silently.
        conn.execute(text(
            "INSERT INTO service_catalog_items (id, category, name, external_id, supplier_id) "
            "VALUES ('cat-2', 'movers', 'Nameless Movers', 'm-99', NULL)"
        ))
    return crown


def test_catalog_item_id_resolves_to_its_supplier(seeded):
    """THE regression: the employee shortlists 'm-2' (a catalog external_id). It must resolve
    to the supplier, even though no supplier has the id 'm-2' any more."""
    ids, errors = rrm.resolve_recipient_ids(["m-2"])
    assert errors == []
    assert ids == [seeded["id"]], "the HR-approved mover did not resolve to a supplier"


def test_a_supplier_id_still_resolves_directly(seeded):
    ids, errors = rrm.resolve_recipient_ids([seeded["id"]])
    assert errors == []
    assert ids == [seeded["id"]]


def test_catalog_item_with_no_supplier_fails_honestly(seeded):
    """It must name the vendor and say why — never guess a supplier, never drop it silently."""
    ids, errors = rrm.resolve_recipient_ids(["m-99"])
    assert ids == []
    assert len(errors) == 1
    assert "Nameless Movers" in errors[0]
    assert "no supplier on record" in errors[0].lower()


def test_one_unreachable_vendor_does_not_poison_the_others(seeded):
    """Previously ANY unresolvable id 400'd the whole RFQ. The reachable ones must survive,
    and the unreachable one must still be reported."""
    ids, errors = rrm.resolve_recipient_ids(["m-2", "m-99"])
    assert ids == [seeded["id"]], "a reachable supplier was dropped because a sibling failed"
    assert len(errors) == 1
    assert "Nameless Movers" in errors[0]


def test_unknown_id_is_reported(seeded):
    ids, errors = rrm.resolve_recipient_ids(["hr-custom-abc123"])
    assert ids == []
    assert len(errors) == 1
    assert "hr-custom-abc123" in errors[0]


def test_duplicate_ids_are_deduped(seeded):
    """The same supplier reachable by both id spaces must be invited exactly once."""
    ids, errors = rrm.resolve_recipient_ids(["m-2", seeded["id"], "m-2"])
    assert errors == []
    assert ids == [seeded["id"]]


def test_no_longer_requires_suppliers_vendor_id(seeded, SessionMaker):
    """The old gate demanded suppliers.vendor_id, which only 8 of 90 suppliers had. Our
    supplier has none, and it must still resolve."""
    with SessionMaker() as s:
        row = supplier_registry.get_supplier(s, seeded["id"])
    assert not row.get("vendor_id"), "fixture should have no vendor_id — that is the point"
    ids, errors = rrm.resolve_recipient_ids(["m-2"])
    assert ids == [seeded["id"]] and errors == []

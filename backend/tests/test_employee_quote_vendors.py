"""[AIQ-1514] The employee's shortlisted vendors must survive the quote request.

The bug: ServicesRfqNew.tsx let the employee shortlist specific vendors, then sent only
`service_categories` plus a free-text `notes` blob. `quote_requests` had no vendor column,
so the choice was discarded at the API boundary and HR never learned who was picked.

These tests pin the contract: the vendors go in, they come back out, and the pre-existing
empty-selection 422 does not regress.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import employee_quotes  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

EMPLOYEE = {"id": "emp-1", "role": "EMPLOYEE", "company": "co-1"}

# Mirrors the production DDL, with jsonb -> TEXT for SQLite (see _is_postgres()).
_DDL = """
CREATE TABLE quote_requests (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    service_categories TEXT,
    notes TEXT,
    budget_range TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT,
    vendors TEXT NOT NULL DEFAULT '[]'
);
"""


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.execute(text(_DDL))
    return eng


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setattr(employee_quotes.db, "engine", engine, raising=False)
    monkeypatch.setattr(employee_quotes.db, "get_profile_record",
                        lambda uid: {"company_id": "co-1"}, raising=False)
    monkeypatch.setattr(employee_quotes, "insert_audit_log", lambda *a, **k: None, raising=False)
    # The roadmap side-effect is best-effort in prod; neutralise it here.
    monkeypatch.setattr(employee_quotes, "advance_quote_step", lambda *a, **k: None, raising=False)

    app = FastAPI()
    app.include_router(employee_quotes.router)
    app.dependency_overrides[get_current_user] = lambda: EMPLOYEE
    return TestClient(app)


TWO_VENDORS = [
    {"service_category": "movers", "item_id": "ext-crown-1", "name": "Crown Relocations"},
    # An HR-added vendor has no master row — its id is synthesised. Must round-trip too.
    {"service_category": "housing", "item_id": "hr-custom-abc123", "name": "Local Agent"},
]


def test_shortlisted_vendors_are_persisted_and_returned(client):
    """THE regression: the employee picks 2 vendors -> both survive the round trip."""
    r = client.post("/api/employee/quote-requests", json={
        "case_id": "case-1",
        "service_categories": ["movers", "housing"],
        "vendors": TWO_VENDORS,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["vendors"] == TWO_VENDORS, "the employee's vendor choice was dropped"

    # And it is readable back, not just echoed from the request.
    listed = client.get("/api/employee/quote-requests")
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["vendors"] == TWO_VENDORS


def test_hr_custom_vendor_id_survives(client):
    """'hr-custom-<id>' vendors have no service_catalog_items row — the id must not be
    mangled or dropped in favour of a lookup that would fail."""
    client.post("/api/employee/quote-requests", json={
        "case_id": "case-1",
        "service_categories": ["housing"],
        "vendors": [TWO_VENDORS[1]],
    })
    got = client.get("/api/employee/quote-requests").json()[0]["vendors"]
    assert got[0]["item_id"] == "hr-custom-abc123"


def test_empty_service_categories_still_422(client):
    """Pre-existing behaviour — an empty selection is blocked. Must not regress."""
    r = client.post("/api/employee/quote-requests", json={
        "case_id": "case-1", "service_categories": [], "vendors": [],
    })
    assert r.status_code == 422


def test_legacy_client_without_vendors_still_succeeds(client):
    """A client that sends no `vendors` key (i.e. the old frontend) must keep working,
    and read back as an honest empty list — not a fabricated one."""
    r = client.post("/api/employee/quote-requests", json={
        "case_id": "case-1", "service_categories": ["movers"],
    })
    assert r.status_code == 201, r.text
    assert r.json()["vendors"] == []


def test_vendors_no_longer_smuggled_through_notes(client):
    """The choice must live in a structured column, not inside the free-text notes."""
    r = client.post("/api/employee/quote-requests", json={
        "case_id": "case-1",
        "service_categories": ["movers"],
        "notes": "Crown Relocations: need it by June",
        "vendors": [TWO_VENDORS[0]],
    })
    body = r.json()
    assert body["vendors"][0]["item_id"] == "ext-crown-1"
    # notes stays the employee's own words — it is simply no longer the ONLY record.
    assert body["notes"] == "Crown Relocations: need it by June"

"""[AIQ-1525] The employee `quote_requests` WRITE path is retired.

The employee-led request model is consolidated onto the canonical RFQ system: employees
now submit a vendor shortlist via POST /api/rfqs (writes rfqs + rfq_recipients). The old
POST /api/employee/quote-requests write path — including the AIQ-1514 vendor round-trip it
used to carry — is retired to a 410 tombstone. The table and its historical rows stay
readable so nothing is orphaned.

These tests pin that contract: the write path returns 410, and the read path still returns
existing rows.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker  # noqa: F401 — parity with sibling fixtures
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
    app = FastAPI()
    app.include_router(employee_quotes.router)
    app.dependency_overrides[get_current_user] = lambda: EMPLOYEE
    return TestClient(app)


def _seed_row(engine, *, row_id="qr-legacy-1", employee_id="emp-1"):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO quote_requests "
                "(id, case_id, employee_id, company_id, service_categories, notes, "
                " budget_range, status, created_at, updated_at, vendors) "
                "VALUES (:id, 'case-1', :emp, 'co-1', 'movers,housing', 'legacy note', "
                " NULL, 'pending', '2026-06-01T00:00:00', '2026-06-01T00:00:00', '[]')"
            ),
            {"id": row_id, "emp": employee_id},
        )


def test_write_path_is_retired_410(client):
    """The employee quote-request write path is retired — submit via POST /api/rfqs."""
    r = client.post("/api/employee/quote-requests", json={
        "case_id": "case-1",
        "service_categories": ["movers", "housing"],
        "vendors": [{"service_category": "movers", "item_id": "ext-crown-1", "name": "Crown"}],
    })
    assert r.status_code == 410, r.text
    assert "/api/rfqs" in r.json()["detail"]


def test_existing_rows_remain_readable(client, engine):
    """Retiring the write must not orphan the 51 legacy rows — the reader still returns them."""
    _seed_row(engine)
    listed = client.get("/api/employee/quote-requests")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == "qr-legacy-1"
    assert body[0]["service_categories"] == ["movers", "housing"]

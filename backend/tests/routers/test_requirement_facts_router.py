"""AIQ-1091 (P4-02) — POST /api/admin/requirement-facts/extract.

App-mounted against the PROD app (backend.main) so it also asserts the route is served there
(dual registration). The extractor is monkeypatched (no LLM/network); the persist runs against
the conftest-mocked engine (defensive). Deliberately does NOT set DATABASE_URL at import (the
AIQ-1090 test-pollution lesson).
"""
from __future__ import annotations

import os

os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
import backend.app.auth_deps as auth_deps  # noqa: E402
import backend.app.routers.requirement_facts as rf  # noqa: E402
from backend.app.services.requirement_fact_extractor import RequirementFact  # noqa: E402


def _admin():
    return {"id": "admin-1", "role": "ADMIN", "is_admin": True, "email": "admin@relopass.com"}


def _employee():
    return {"id": "emp-1", "role": "EMPLOYEE", "is_admin": False}


def _two_facts():
    return [
        RequirementFact(
            text="A valid passport is required.", requirement_type="document", corridor="IN-DE",
            confidence_score=0.9, source_quote="You must hold a valid passport.",
            source_url="https://gov.example", extraction_method="llm",
        ),
        RequirementFact(
            text="Pay the EUR 75 application fee.", requirement_type="fee", corridor="IN-DE",
            confidence_score=0.8, source_quote="The fee is EUR 75.",
            source_url="https://gov.example", extraction_method="llm",
        ),
    ]


@pytest.fixture
def client(monkeypatch):
    async def _fake_extract(url, *, corridor="", content=None):
        return _two_facts()

    monkeypatch.setattr(rf, "extract_requirement_facts", _fake_extract)
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def test_admin_extract_returns_facts_and_pending(client):
    app.dependency_overrides[auth_deps.get_current_user] = _admin
    r = client.post(
        "/api/admin/requirement-facts/extract",
        json={"source_url": "https://gov.example", "corridor": "IN-DE"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["extracted"] == 2
    assert body["pending"] == 2  # one persisted row per fact
    assert len(body["facts"]) == 2
    assert body["facts"][0]["requirement_type"] == "document"
    assert 0.0 < body["facts"][0]["confidence_score"] <= 1.0


def test_non_admin_forbidden(client):
    app.dependency_overrides[auth_deps.get_current_user] = _employee
    r = client.post("/api/admin/requirement-facts/extract", json={"source_url": "https://gov.example"})
    assert r.status_code == 403


def test_requirement_type_hint_filters(client):
    app.dependency_overrides[auth_deps.get_current_user] = _admin
    r = client.post(
        "/api/admin/requirement-facts/extract",
        json={"source_url": "https://gov.example", "requirement_type_hint": "fee"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extracted"] == 1
    assert body["facts"][0]["requirement_type"] == "fee"


def test_route_registered_on_prod_app():
    paths = [route.path for route in app.routes if "requirement-facts" in route.path]
    assert "/api/admin/requirement-facts/extract" in paths

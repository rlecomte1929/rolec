"""
Tests for backend/app/routers/resources_activities.py — AIQ-1581.

City-level activity suggestions. The LLM call is mocked; we assert the endpoint
shape, that require_hr_or_employee gates access, and that a generation failure
degrades to a 200 with an empty list (fail-soft) rather than a 500.
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import resources_activities  # noqa: E402
from backend.app.services import city_activities_service  # noqa: E402
from backend.app.auth_deps import require_hr_or_employee  # noqa: E402


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(resources_activities.router)
    app.dependency_overrides[require_hr_or_employee] = lambda: {"id": "u-1"}
    return app


def test_requires_auth():
    app = FastAPI()
    app.include_router(resources_activities.router)
    client = TestClient(app)
    r = client.get("/api/resources/city-activities", params={"city": "Oslo", "country": "Norway"})
    assert r.status_code == 401


def test_returns_activities(monkeypatch):
    async def fake_complete(*, system, user, schema, **kwargs):
        assert "Oslo" in user  # city reaches the prompt
        return {
            "activities": [
                {"title": "Vigeland Park", "description": "Sculpture park.", "category": "outdoor"},
                {"title": "", "description": "dropped — no title", "category": "x"},
            ]
        }

    monkeypatch.setattr(city_activities_service, "complete", fake_complete)
    client = TestClient(_app())
    r = client.get("/api/resources/city-activities", params={"city": "Oslo", "country": "Norway"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["city"] == "Oslo"
    assert len(body["activities"]) == 1  # blank-title item filtered out
    assert body["activities"][0]["title"] == "Vigeland Park"


def test_llm_failure_degrades_to_empty(monkeypatch):
    async def boom(*, system, user, schema, **kwargs):
        raise RuntimeError("OPENAI_API_KEY not set")

    monkeypatch.setattr(city_activities_service, "complete", boom)
    client = TestClient(_app())
    r = client.get("/api/resources/city-activities", params={"city": "Oslo", "country": "Norway"})
    assert r.status_code == 200, r.text
    assert r.json()["activities"] == []


def test_empty_inputs_return_empty_without_calling_llm(monkeypatch):
    async def boom(*, system, user, schema, **kwargs):
        raise AssertionError("LLM should not be called with no city/country")

    monkeypatch.setattr(city_activities_service, "complete", boom)
    client = TestClient(_app())
    r = client.get("/api/resources/city-activities", params={"city": "", "country": ""})
    assert r.status_code == 200, r.text
    assert r.json()["activities"] == []

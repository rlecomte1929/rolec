"""P2-04 integration bridge — estimate_for_case() + the /processing-time endpoint.

Pure/stdlib for the service helper (a fake session), and the real router over a
minimal FastAPI app (auth via dependency_overrides, no DB) for the endpoint.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.app.routers import predictions  # noqa: E402
from backend.app.services import processing_time_estimate as pte  # noqa: E402
from backend.app.services.processing_time_estimate import (  # noqa: E402
    estimate_for_case,
    processing_time_estimate,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fake session: case lookup -> .first(); duration query -> .all()
# ──────────────────────────────────────────────────────────────────────────────


class _Result:
    def __init__(self, first_row, all_rows):
        self._first = first_row
        self._all = all_rows

    def mappings(self):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all


class _FakeSession:
    def __init__(self, *, case_row, duration_rows=None):
        self._case_row = case_row
        self._duration_rows = duration_rows or []

    def execute(self, *_args, **_kwargs):
        return _Result(self._case_row, self._duration_rows)


# ──────────────────────────────────────────────────────────────────────────────
# estimate_for_case()
# ──────────────────────────────────────────────────────────────────────────────


def test_estimate_for_case_resolves_corridor_and_falls_back_to_official():
    # Case on IN->DE, no completed platform cases -> official Blue Card range.
    session = _FakeSession(case_row={"origin_country": "IN", "dest_country": "DE"})
    est = estimate_for_case(session, "case-1")
    assert est is not None
    assert est["source"] == "official_only"
    assert (est["p50_days"], est["p90_days"]) == (28, 84)


def test_estimate_for_case_returns_none_when_case_missing():
    assert estimate_for_case(_FakeSession(case_row=None), "nope") is None


def test_estimate_for_case_returns_none_when_corridor_incomplete():
    session = _FakeSession(case_row={"origin_country": None, "dest_country": "DE"})
    assert estimate_for_case(session, "case-2") is None


def test_official_match_works_without_a_pathway():
    # Corridor-only match: a None pathway still resolves the single seeded entry.
    est = processing_time_estimate(pathway_type=None, corridor=("FR", "NO"))
    assert est is not None
    assert est["source"] == "official_only"
    assert (est["p50_days"], est["p90_days"]) == (1, 90)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/cases/{case_id}/processing-time
# ──────────────────────────────────────────────────────────────────────────────


class _NullSession:
    def __enter__(self):
        return None

    def __exit__(self, *_a):
        return False


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("PROCESSING_TIME_ENABLED", "true")
    # No real DB: the session is unused because estimate_for_case is stubbed.
    monkeypatch.setattr(predictions, "SessionLocal", lambda: _NullSession())
    monkeypatch.setattr(predictions, "require_case_access", lambda *a, **k: None)

    app = FastAPI()
    app.include_router(predictions.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "role": "HR"}
    return TestClient(app)


_ESTIMATE = {
    "p50_days": 28,
    "p90_days": 84,
    "source": "official_only",
    "sample_size": 0,
    "last_updated": "2026-05-30",
    "source_url": "https://example.test/eu-blue-card",
}


def test_endpoint_returns_estimate(client, monkeypatch):
    monkeypatch.setattr(pte, "estimate_for_case", lambda _s, _cid: dict(_ESTIMATE))
    resp = client.get("/api/cases/case-1/processing-time")
    assert resp.status_code == 200
    assert resp.json() == _ESTIMATE


def test_endpoint_404_when_no_estimate(client, monkeypatch):
    monkeypatch.setattr(pte, "estimate_for_case", lambda _s, _cid: None)
    resp = client.get("/api/cases/case-1/processing-time")
    assert resp.status_code == 404


def test_endpoint_404_when_flag_disabled(monkeypatch):
    monkeypatch.setenv("PROCESSING_TIME_ENABLED", "false")
    app = FastAPI()
    app.include_router(predictions.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "role": "HR"}
    resp = TestClient(app).get("/api/cases/case-1/processing-time")
    assert resp.status_code == 404


def test_endpoint_requires_authentication(monkeypatch):
    monkeypatch.setenv("PROCESSING_TIME_ENABLED", "true")
    app = FastAPI()
    app.include_router(predictions.router)  # no auth override -> real dependency
    resp = TestClient(app).get("/api/cases/case-1/processing-time")
    assert resp.status_code == 401

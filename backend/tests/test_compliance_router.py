"""BL-Compliance.4 — API tests for the compliance router (AIQ-746).

Mounts the production app (`backend.main`) and overrides the auth/company
dependencies imported from `backend.app.auth_deps` (the deployed app's deps).
The empty-company paths short-circuit before any DB access, so these run with no
Postgres; the full happy-path (alerts render) is a live/manual check since the
compliance tables are Postgres-only.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_org_id_for_hr_user, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_routes_registered():
    paths = {r.path for r in app.routes}
    assert "/api/compliance/alerts" in paths
    assert "/api/compliance/evaluate" in paths
    assert "/api/compliance/alerts/{alert_id}" in paths


def test_list_alerts_empty_company_returns_empty(client: TestClient):
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: ""
    resp = client.get("/api/compliance/alerts")
    assert resp.status_code == 200
    assert resp.json() == {"alerts": [], "counts_by_severity": {}}


def test_evaluate_requires_a_company(client: TestClient):
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: ""
    resp = client.post("/api/compliance/evaluate")
    assert resp.status_code == 400


def test_alerts_rejects_non_hr_user(client: TestClient):
    # A logged-in employee must be rejected by require_admin_or_hr (nested in
    # get_org_id_for_hr_user).
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "role": "employee",
        "email": "e@example.com",
    }
    resp = client.get("/api/compliance/alerts")
    assert resp.status_code == 403


def test_update_alert_rejects_bad_status(client: TestClient):
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: "co-1"
    resp = client.patch(
        "/api/compliance/alerts/some-id", json={"status": "bogus"}
    )
    assert resp.status_code == 422  # pydantic Literal rejects it before any DB work

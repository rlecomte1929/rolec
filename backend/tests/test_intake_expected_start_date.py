"""Phase B1 — HR can set relocation_cases.expected_start_date.

Mounts the production app (`backend.main`) and overrides the auth/company
dependencies from `backend.app.auth_deps`. The route smoke-test does not hit
the DB; tenant-isolation + 404 paths short-circuit via the UPDATE returning
zero rows (which we exercise via dependency injection in a separate test that
runs only when a live DB is configured).
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import (
    get_current_user,
    get_org_id_for_hr_user,
    require_admin_or_hr,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _hr_overrides():
    def _hr_user():
        return {"id": "hr-1", "role": "hr", "email": "hr@example.com",
                "company_id": "company-1"}

    app.dependency_overrides[get_current_user] = _hr_user
    app.dependency_overrides[require_admin_or_hr] = _hr_user
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: "company-1"
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin_or_hr, None)
    app.dependency_overrides.pop(get_org_id_for_hr_user, None)


def test_route_is_registered():
    paths = {r.path for r in app.routes}
    assert "/api/hr/cases/{case_id}/expected-start-date" in paths, (
        "Phase B1 route not registered — check immigration_intake_profile.py "
        "and both backend/main.py + backend/app/main.py registrations."
    )


def test_rejects_invalid_payload(client: TestClient):
    resp = client.patch(
        "/api/hr/cases/00000000-0000-0000-0000-000000000000/expected-start-date",
        json={},
    )
    assert resp.status_code == 422, resp.text


def test_rejects_non_iso_date(client: TestClient):
    resp = client.patch(
        "/api/hr/cases/00000000-0000-0000-0000-000000000000/expected-start-date",
        json={"expected_start_date": "not-a-date"},
    )
    assert resp.status_code == 422, resp.text

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
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user, require_admin


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_org_id_for_hr_user, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin, None)


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


# ── Phase C2: admin fleet-wide evaluate-all endpoint ─────────────────────────


def test_evaluate_all_route_registered():
    paths = {r.path for r in app.routes}
    assert "/api/compliance/evaluate-all" in paths


def test_evaluate_all_rejects_non_admin(client: TestClient):
    # An HR user (no is_admin) must be rejected by require_admin.
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "hr-1", "role": "hr", "is_admin": False,
    }
    resp = client.post("/api/compliance/evaluate-all?dry_run=true")
    assert resp.status_code == 403, resp.text


def test_evaluate_all_default_is_dry_run(client: TestClient, monkeypatch):
    """When admin POSTs without ?dry_run=..., endpoint must default to dry-run
    so the scheduled cron is safe-by-default."""
    app.dependency_overrides[require_admin] = lambda: {
        "id": "admin-1", "role": "admin", "is_admin": True,
    }
    captured: dict = {}

    def fake_run(db, today=None, company_id=None, dry_run=False):
        from backend.app.services.compliance_evaluator import EvaluationResult
        captured["dry_run"] = dry_run
        captured["company_id"] = company_id
        return EvaluationResult(
            cases_evaluated=0, alerts_created=0, alerts_skipped_existing=0
        )

    monkeypatch.setattr(
        "backend.app.routers.compliance.run_compliance_evaluation", fake_run
    )
    resp = client.post("/api/compliance/evaluate-all")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert captured["dry_run"] is True
    assert captured["company_id"] is None  # fleet-wide, not company-scoped


def test_evaluate_all_dry_run_false_persists(client: TestClient, monkeypatch):
    app.dependency_overrides[require_admin] = lambda: {
        "id": "admin-1", "role": "admin", "is_admin": True,
    }
    captured: dict = {}

    def fake_run(db, today=None, company_id=None, dry_run=False):
        from backend.app.services.compliance_evaluator import EvaluationResult
        captured["dry_run"] = dry_run
        return EvaluationResult(
            cases_evaluated=3, alerts_created=2, alerts_skipped_existing=1
        )

    monkeypatch.setattr(
        "backend.app.routers.compliance.run_compliance_evaluation", fake_run
    )
    resp = client.post("/api/compliance/evaluate-all?dry_run=false")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "cases_evaluated": 3,
        "alerts_created": 2,
        "alerts_skipped_existing": 1,
        "dry_run": False,
    }
    assert captured["dry_run"] is False

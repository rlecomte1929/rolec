"""Route tests for POST /api/hr/{company_id}/optimize-benefit-mix (Parker-B).

A minimal FastAPI app mounts only the optimizer router so the suite needn't boot
the whole backend (DB/seed). Auth dependencies are overridden to exercise the
company-scoping gate without a real token/DB. Skipped cleanly without PuLP.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

pytest.importorskip("pulp")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.auth_deps import (  # noqa: E402
    get_current_user,
    get_org_id_for_hr_user,
)
from backend.app.routers import benefit_optimizer as router_mod  # noqa: E402

_HR_USER: Dict[str, Any] = {"id": "u-hr-1", "role": "HR", "is_admin": False}
_EMPLOYEE: Dict[str, Any] = {"id": "u-emp-1", "role": "EMPLOYEE", "is_admin": False}

_CANDIDATES = [
    {"id": "a", "category": "housing", "cost_per_employee": 3000, "expected_satisfaction": 10, "variance": 4},
    {"id": "b", "category": "transport", "cost_per_employee": 4000, "expected_satisfaction": 12, "variance": 9},
    {"id": "c", "category": "education", "cost_per_employee": 5000, "expected_satisfaction": 8, "variance": 1},
]


def _make_client(user: Dict[str, Any], caller_company: str) -> TestClient:
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: caller_company
    return TestClient(app)


def _body(**overrides) -> Dict[str, Any]:
    body = {"budget": 8000, "candidates": _CANDIDATES, "lambda_risk": 0.1}
    body.update(overrides)
    return body


def test_optimize_happy_path_200():
    client = _make_client(_HR_USER, caller_company="comp-1")
    resp = client.post("/api/hr/comp-1/optimize-benefit-mix", json=_body())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["feasible"] is True
    assert data["selected"] == ["a", "b"]
    assert data["achieved_utility"] == pytest.approx(20.7)
    assert "budget_per_1000" in data["shadow_prices"]


def test_non_hr_admin_caller_403():
    # Employee role is rejected by require_admin_or_hr before reaching the handler.
    client = _make_client(_EMPLOYEE, caller_company="comp-1")
    resp = client.post("/api/hr/comp-1/optimize-benefit-mix", json=_body())
    assert resp.status_code == 403, resp.text


def test_wrong_company_403():
    # HR admin of comp-2 cannot optimize for comp-1.
    client = _make_client(_HR_USER, caller_company="comp-2")
    resp = client.post("/api/hr/comp-1/optimize-benefit-mix", json=_body())
    assert resp.status_code == 403, resp.text


def test_malformed_body_422():
    client = _make_client(_HR_USER, caller_company="comp-1")
    resp = client.post(
        "/api/hr/comp-1/optimize-benefit-mix",
        json={"candidates": _CANDIDATES},  # missing required 'budget'
    )
    assert resp.status_code == 422, resp.text

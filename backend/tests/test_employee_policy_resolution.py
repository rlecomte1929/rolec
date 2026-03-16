"""
Lightweight regression tests for employee published policy retrieval.
Verifies: policy and policy-budget return 200 with has_policy; no 500 for missing policy.
"""
import os
import sys
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from main import app

client = TestClient(app)


def _login(identifier: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200
    return res.json()["token"]


def test_employee_policy_returns_200_with_has_policy_key():
    """Employee policy endpoint returns 200 and has_policy key (no 500 for missing policy)."""
    token = _login("demo@relopass.com", "Passw0rd!")
    res = client.get("/api/employee/assignments/current", headers={"Authorization": f"Bearer {token}"})
    if res.status_code != 200 or not res.json().get("assignment", {}).get("id"):
        # No current assignment: call policy with a placeholder id to assert 404 (not 500)
        res_policy = client.get(
            "/api/employee/assignments/00000000-0000-0000-0000-000000000000/policy",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_policy.status_code in (404, 403)
        return
    assignment_id = res.json()["assignment"]["id"]
    res_policy = client.get(
        f"/api/employee/assignments/{assignment_id}/policy",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_policy.status_code == 200
    data = res_policy.json()
    assert "has_policy" in data
    assert "policy" in data
    assert "benefits" in data
    assert "exclusions" in data


def test_employee_policy_budget_returns_200_empty_when_no_published_policy():
    """Policy-budget endpoint returns 200 with has_policy and caps (no 500 when no policy)."""
    token = _login("demo@relopass.com", "Passw0rd!")
    res = client.get("/api/employee/assignments/current", headers={"Authorization": f"Bearer {token}"})
    if res.status_code != 200 or not res.json().get("assignment", {}).get("id"):
        res_budget = client.get(
            "/api/employee/assignments/00000000-0000-0000-0000-000000000000/policy-budget",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_budget.status_code in (404, 403)
        return
    assignment_id = res.json()["assignment"]["id"]
    res_budget = client.get(
        f"/api/employee/assignments/{assignment_id}/policy-budget",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_budget.status_code == 200
    data = res_budget.json()
    assert "has_policy" in data
    assert "currency" in data
    assert "caps" in data
    if not data.get("has_policy"):
        assert isinstance(data["caps"], dict)

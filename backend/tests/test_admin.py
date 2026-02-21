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


def test_admin_access_denied_for_employee():
    token = _login("demo@relopass.com", "Passw0rd!")
    res = client.get("/api/admin/companies", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_admin_action_requires_reason():
    token = _login("admin@relopass.com", "Passw0rd!")
    res = client.post(
        "/api/admin/actions/unlock-case",
        headers={"Authorization": f"Bearer {token}"},
        json={"payload": {"case_id": "demo-case-demo-emp"}},
    )
    assert res.status_code == 400


def test_admin_context_available():
    token = _login("admin@relopass.com", "Passw0rd!")
    res = client.get("/api/admin/context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json().get("isAdmin") is True

"""AIQ-23: GET /api/admin/assignments/{id} must return 200, not 500."""
from __future__ import annotations

import os
import sys
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi.testclient import TestClient

from backend.main import app
import backend.database as dbmod

_PASSWORD = "Passw0rd!"


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def test_admin_assignment_detail_returns_200():
    """
    Regression: GET /api/admin/assignments/{id} was returning HTTP 500 due to
    an invalid column reference.  Fix replaced the broken query with a standard
    JOIN across case_assignments, relocation_cases, profiles, hr_users, employees.
    Verifies:
      1. 200 + expected keys for a valid assignment id.
      2. 404 (not 500) for an unknown id.
    """
    with TestClient(app) as client:
        # ── create admin user directly (no seed in in-memory DB) ──────────────
        # Use the same CryptContext instance the auth router uses so hashes are compatible.
        from backend.app.routers.auth import _pwd_context as _auth_pwd_ctx

        admin_id = str(uuid.uuid4())
        admin_email = f"admin-aiq23-{_suffix()}@example.test"
        dbmod.db.ensure_initialized()
        dbmod.db.create_user(
            admin_id, None, admin_email,
            _auth_pwd_ctx.hash(_PASSWORD),
            "ADMIN", "Admin AIQ23",
        )

        # ── admin login ───────────────────────────────────────────────────────
        admin_login = client.post(
            "/api/auth/login",
            json={"identifier": admin_email, "password": _PASSWORD},
        )
        assert admin_login.status_code == 200, admin_login.text
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}

        # ── create company ────────────────────────────────────────────────────
        co_res = client.post(
            "/api/admin/companies",
            headers=admin_headers,
            json={"name": f"AIQ-23 Corp {_suffix()}"},
        )
        assert co_res.status_code == 201, co_res.text
        company_id = co_res.json()["company"]["id"]

        # ── register HR user and link to company ──────────────────────────────
        hr_email = f"hr-aiq23-{_suffix()}@example.test"
        hr_reg = client.post(
            "/api/auth/register",
            json={"email": hr_email, "password": _PASSWORD, "role": "HR", "name": "HR AIQ23"},
        )
        assert hr_reg.status_code == 200, hr_reg.text
        hr_user_id = hr_reg.json()["user"]["id"]
        hr_token = hr_reg.json()["token"]

        link = client.post(
            f"/api/admin/people/{hr_user_id}/assign-company",
            headers=admin_headers,
            json={"company_id": company_id},
        )
        assert link.status_code == 200, link.text

        # ── register employee ─────────────────────────────────────────────────
        emp_email = f"emp-aiq23-{_suffix()}@example.test"
        emp_reg = client.post(
            "/api/auth/register",
            json={"email": emp_email, "password": _PASSWORD, "role": "EMPLOYEE", "name": "Emp AIQ23"},
        )
        assert emp_reg.status_code == 200, emp_reg.text

        # ── HR creates a case ─────────────────────────────────────────────────
        case_res = client.post(
            "/api/hr/cases",
            headers={"Authorization": f"Bearer {hr_token}"},
            json={"profile": {"home_country": "FR", "host_country": "DE"}},
        )
        assert case_res.status_code == 200, case_res.text
        case_body = case_res.json()
        case_id = case_body.get("id") or case_body.get("caseId")
        assert case_id, f"No id/caseId in case response: {case_body}"

        # ── HR assigns employee ───────────────────────────────────────────────
        assign_res = client.post(
            f"/api/hr/cases/{case_id}/assign",
            headers={"Authorization": f"Bearer {hr_token}"},
            json={"employeeIdentifier": emp_email},
        )
        assert assign_res.status_code == 200, assign_res.text
        asgn_body = assign_res.json()
        assignment_id = (
            asgn_body.get("assignment_id")
            or asgn_body.get("assignmentId")
            or asgn_body.get("id")
        )
        assert assignment_id, f"No assignment_id/assignmentId in response: {asgn_body}"

        # ── happy path: valid id → 200 + expected keys ────────────────────────
        res = client.get(f"/api/admin/assignments/{assignment_id}", headers=admin_headers)
        assert res.status_code == 200, (
            f"Expected 200, got {res.status_code}.\nBody: {res.text}"
        )
        body = res.json()
        assert "assignment" in body, f"Missing 'assignment' key in: {body}"
        detail = body["assignment"]
        assert detail.get("id") == assignment_id, f"Wrong id in detail: {detail}"
        assert "status" in detail, f"Missing 'status' in detail: {detail}"

        # ── sad path: unknown id → 404, never 500 ────────────────────────────
        not_found = client.get(
            f"/api/admin/assignments/{uuid.uuid4()}", headers=admin_headers
        )
        assert not_found.status_code == 404, (
            f"Expected 404 for unknown id, got {not_found.status_code}.\nBody: {not_found.text}"
        )

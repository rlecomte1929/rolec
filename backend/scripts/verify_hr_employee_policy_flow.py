#!/usr/bin/env python3
"""
Verify HR-side and employee-side policy visibility for Test company.

Usage (from repo root):
  PYTHONPATH=. DISABLE_DEMO_RESEED=true DATABASE_URL=sqlite:///./backend/relopass.db \\
    python backend/scripts/verify_hr_employee_policy_flow.py
"""
import os
import sys

# Run from repo root so "backend" package is available
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
os.chdir(repo_root)

os.environ.setdefault("DISABLE_DEMO_RESEED", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/relopass.db")

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402


TEST_COMPANY_ID = "110854ad-3c85-4291-a484-0b43effb680e"
HR_EMAIL = "hr.demo@relopass.local"
EMP_EMAIL = "demo@relopass.com"  # demo-emp-003
PASSWORD = "Passw0rd!"

client = TestClient(app)


def login(email: str) -> str:
    r = client.post("/api/auth/login", json={"identifier": email, "password": PASSWORD})
    if r.status_code != 200:
        raise SystemExit(f"Login failed for {email}: {r.status_code} {r.text}")
    return r.json()["token"]


def verify_hr_flow() -> None:
    print("\n=== HR-SIDE VERIFICATION ===")
    token = login(HR_EMAIL)
    headers = {"Authorization": f"Bearer {token}"}

    # HR company info
    r = client.get("/api/company", headers=headers)
    print("HR /api/company status:", r.status_code)
    print("HR company payload:", r.json())

    # Company employees/people from HR perspective (via admin people API requires admin; instead use /api/company and assignments)
    # For quick check, hit admin people with admin token separately in employee/overall section.

    # Company policy list (HR-scoped)
    r = client.get("/api/company-policies", headers=headers)
    print("\nHR /api/company-policies status:", r.status_code)
    data = r.json() if r.status_code == 200 else {}
    policies = data.get("policies") or []
    print("HR company policies count:", len(policies))
    for p in policies:
        print("  HR policy:", p.get("id"), "| title:", p.get("title"), "| company_id:", p.get("company_id"))

    # Latest company policy (HR / employee)
    r = client.get("/api/company-policies/latest", headers=headers)
    print("\nHR /api/company-policies/latest status:", r.status_code)
    data = r.json() if r.status_code == 200 else {}
    print("HR latest policy company_name:", data.get("company_name"))
    if data.get("policy"):
        print("HR latest policy id:", data["policy"].get("id"))
        print("HR latest policy title:", data["policy"].get("title"))
        print("HR benefits count:", len(data.get("benefits") or []))


def verify_employee_flow() -> None:
    print("\n=== EMPLOYEE-SIDE VERIFICATION ===")
    token = login(EMP_EMAIL)
    headers = {"Authorization": f"Bearer {token}"}

    # Employee company info
    r = client.get("/api/company", headers=headers)
    print("EMP /api/company status:", r.status_code)
    print("EMP company payload:", r.json())

    # Latest company policy for employee
    r = client.get("/api/company-policies/latest", headers=headers)
    print("\nEMP /api/company-policies/latest status:", r.status_code)
    data = r.json() if r.status_code == 200 else {}
    print("EMP latest policy company_name:", data.get("company_name"))
    if data.get("policy"):
        print("EMP latest policy id:", data["policy"].get("id"))
        print("EMP latest policy title:", data["policy"].get("title"))
        print("EMP benefits count:", len(data.get("benefits") or []))


def verify_admin_view() -> None:
    print("\n=== ADMIN VIEW VERIFICATION ===")
    token = login("admin@relopass.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Companies row for Test company
    r = client.get("/api/admin/companies", headers=headers)
    data = r.json() if r.status_code == 200 else {}
    companies = data.get("companies") or []
    row = next((c for c in companies if c.get("id") == TEST_COMPANY_ID), None)
    print("Admin companies status:", r.status_code)
    print("Admin Test company row:", row)

    # Admin policies for Test company
    r = client.get("/api/admin/policies", headers=headers, params={"company_id": TEST_COMPANY_ID})
    print("Admin /api/admin/policies status:", r.status_code)
    if r.status_code == 200:
        print("Admin policies payload keys:", list(r.json().keys()))


def main() -> None:
    verify_hr_flow()
    verify_employee_flow()
    verify_admin_view()


if __name__ == "__main__":
    main()


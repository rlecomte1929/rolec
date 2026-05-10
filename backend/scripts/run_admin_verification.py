#!/usr/bin/env python3
"""
Run admin verification against local backend (TestClient).
Usage: from repo root: PYTHONPATH=. python backend/scripts/run_admin_verification.py
"""
import os
import sys

# Run from repo root so "backend" package is available
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
os.chdir(repo_root)

# Ensure we don't reseed demo-company-001 while running verification
os.environ.setdefault("DISABLE_DEMO_RESEED", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/relopass.db")

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
TEST_COMPANY_ID = "110854ad-3c85-4291-a484-0b43effb680e"


def auth():
    r = client.post("/api/auth/login", json={"identifier": "admin@relopass.com", "password": "Passw0rd!"})
    if r.status_code != 200:
        raise SystemExit(f"Login failed: {r.status_code} {r.text}")
    return r.json()["token"]


def main():
    print("=== Admin verification (TestClient) ===\n")
    token = auth()

    # A. Backfill
    print("1. BACKFILL EXECUTION")
    r = client.post(
        "/api/admin/reconciliation/backfill-test-company",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        print(f"   FAILED: {r.status_code} {r.text}\n")
    else:
        data = r.json()
        summary = (data.get("summary") or {}) if data.get("ok") else {}
        print("   test_company_id:", summary.get("test_company_id"))
        print("   profiles_linked:", summary.get("profiles_linked"))
        print("   hr_users_linked:", summary.get("hr_users_linked"))
        print("   relocation_cases_linked:", summary.get("relocation_cases_linked"))
    print()

    # B. Companies list
    print("2. COMPANIES PAGE (Test company row)")
    r = client.get("/api/admin/companies", headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        print(f"   FAILED: {r.status_code} {r.text}\n")
    else:
        companies = r.json().get("companies") or []
        test_row = next((c for c in companies if c.get("id") == TEST_COMPANY_ID), None)
        if not test_row:
            print("   Test company row NOT FOUND")
        else:
            print("   id:", test_row.get("id"))
            print("   name:", test_row.get("name"))
            print("   hr_users_count:", test_row.get("hr_users_count"))
            print("   employee_count:", test_row.get("employee_count"))
            print("   assignments_count:", test_row.get("assignments_count"))
    print()

    # C. Company detail
    print("3. COMPANY DETAIL")
    r = client.get(
        f"/api/admin/companies/{TEST_COMPANY_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        print(f"   FAILED: {r.status_code} {r.text[:500]}\n")
    else:
        data = r.json()
        company = data.get("company") or {}
        summary = data.get("summary") or data.get("counts_summary") or {}
        print("   working: yes")
        print("   company.name:", company.get("name"))
        print("   summary hr_users_count:", summary.get("hr_users_count"))
        print("   summary employee_count:", summary.get("employee_count"), "| employees_count:", summary.get("employees_count"))
        print("   summary assignments_count:", summary.get("assignments_count"))
        print("   len(hr_users):", len(data.get("hr_users") or []))
        print("   len(employees):", len(data.get("employees") or []))
        print("   len(assignments):", len(data.get("assignments") or []))
        print("   len(policies):", len(data.get("policies") or []))
    print()

    # D. People
    print("4. PEOPLE PAGE")
    r_all = client.get("/api/admin/people", headers={"Authorization": f"Bearer {token}"})
    r_test = client.get("/api/admin/people", headers={"Authorization": f"Bearer {token}"}, params={"company_id": TEST_COMPANY_ID})
    if r_all.status_code != 200:
        print("   All companies FAILED:", r_all.status_code)
    else:
        people_all = r_all.json().get("people") or []
        print("   All companies total:", len(people_all))
    if r_test.status_code != 200:
        print("   Test company filter FAILED:", r_test.status_code)
    else:
        people_test = r_test.json().get("people") or []
        hr = sum(1 for p in people_test if p.get("role") == "HR" or (p.get("hr_link_count") or 0) > 0)
        emp = sum(1 for p in people_test if (p.get("role") or "") in ("EMPLOYEE", "EMPLOYEE_USER") or (p.get("employee_link_count") or 0) > 0)
        print("   Test company total:", len(people_test), "| HR:", hr, "| Employee:", emp)
    print()

    # E. Assignments
    print("5. ASSIGNMENTS PAGE (Test company)")
    r = client.get("/api/admin/assignments", headers={"Authorization": f"Bearer {token}"}, params={"company_id": TEST_COMPANY_ID})
    if r.status_code != 200:
        print(f"   FAILED: {r.status_code} {r.text[:200]}\n")
    else:
        assignments = r.json().get("assignments") or []
        print("   count:", len(assignments))
    print()

    # F. Policies
    print("6. POLICIES (Test company)")
    r = client.get("/api/admin/policies", headers={"Authorization": f"Bearer {token}"}, params={"company_id": TEST_COMPANY_ID})
    if r.status_code != 200:
        print(f"   FAILED: {r.status_code} {r.text[:300]}\n")
    else:
        data = r.json()
        policies = data.get("policies") if isinstance(data.get("policies"), list) else []
        if not policies and isinstance(data.get("policies"), dict):
            policies = []
        print("   visible policies:", len(policies))
        for p in (policies or [])[:3]:
            print("     -", p.get("title") or p.get("policy_id"))
    print()

    # G. Supplier detail
    print("7. SUPPLIER DETAIL")
    r_list = client.get("/api/suppliers", headers={"Authorization": f"Bearer {token}"}, params={"limit": 1})
    if r_list.status_code != 200:
        print("   list FAILED:", r_list.status_code)
    else:
        suppliers = r_list.json().get("suppliers") or []
        if not suppliers:
            print("   no suppliers, skip")
        else:
            sid = suppliers[0].get("id")
            r = client.get(f"/api/suppliers/{sid}", headers={"Authorization": f"Bearer {token}"})
            print("   working: yes" if r.status_code == 200 else f"   failed: {r.status_code} {r.text[:200]}")
    print()

    # H. Messages
    print("8. MESSAGES (Test company)")
    r = client.get(
        "/api/admin/messages/threads",
        headers={"Authorization": f"Bearer {token}"},
        params={"company_id": TEST_COMPANY_ID, "limit": 10},
    )
    if r.status_code != 200:
        print(f"   FAILED: {r.status_code} {r.text[:300]}\n")
    else:
        threads = (r.json().get("threads") or [])
        print("   working: yes | threads count:", len(threads))
    print("\n=== Done ===")


if __name__ == "__main__":
    main()

"""
Execution + verification pass for admin console.
Run: cd backend && pytest tests/test_admin_verification.py -v -s 2>&1
Uses TestClient; DB state depends on DATABASE_URL (default sqlite).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
TEST_COMPANY_ID = "110854ad-3c85-4291-a484-0b43effb680e"


def _auth():
    r = client.post("/api/auth/login", json={"identifier": "admin@relopass.com", "password": "Passw0rd!"})
    if r.status_code != 200:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
    return r.json()["token"]


def test_a_backfill_execution():
    """A. Run backfill and capture exact summary."""
    token = _auth()
    r = client.post(
        "/api/admin/reconciliation/backfill-test-company",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Backfill failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("ok") is True, data
    summary = data.get("summary") or {}
    print("\n1. BACKFILL RESULT")
    print("   test_company_id:", summary.get("test_company_id"))
    print("   profiles_linked:", summary.get("profiles_linked"))
    print("   hr_users_linked:", summary.get("hr_users_linked"))
    print("   relocation_cases_linked:", summary.get("relocation_cases_linked"))


def test_b_companies_page_counts():
    """B. Companies list: Test company row counts."""
    token = _auth()
    r = client.get("/api/admin/companies", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    companies = r.json().get("companies") or []
    test_row = next((c for c in companies if c.get("id") == TEST_COMPANY_ID), None)
    print("\n2. COMPANIES PAGE (Test company row)")
    if not test_row:
        print("   Test company row NOT FOUND in list (id may not exist yet)")
        return
    print("   id:", test_row.get("id"))
    print("   name:", test_row.get("name"))
    print("   hr_users_count:", test_row.get("hr_users_count"))
    print("   employee_count:", test_row.get("employee_count"))
    print("   assignments_count:", test_row.get("assignments_count"))
    print("   primary_contact_name:", test_row.get("primary_contact_name"))


def test_c_company_detail_route():
    """C. Company detail GET for Test company."""
    token = _auth()
    r = client.get(
        f"/api/admin/companies/{TEST_COMPANY_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    print("\n3. COMPANY DETAIL")
    if r.status_code != 200:
        print("   FAILED status:", r.status_code)
        print("   body:", r.text[:500])
        raise AssertionError(f"Company detail failed: {r.status_code}")
    data = r.json()
    company = data.get("company") or {}
    summary = data.get("summary") or data.get("counts_summary") or {}
    print("   working: yes")
    print("   company.name:", company.get("name"))
    print("   summary.hr_users_count:", summary.get("hr_users_count"))
    print("   summary.employee_count:", summary.get("employee_count"), "(or employees_count:", summary.get("employees_count"), ")")
    print("   summary.assignments_count:", summary.get("assignments_count"))
    print("   summary.policies_count:", summary.get("policies_count"))
    print("   len(hr_users):", len(data.get("hr_users") or []))
    print("   len(employees):", len(data.get("employees") or []))
    print("   len(assignments):", len(data.get("assignments") or []))
    print("   len(policies):", len(data.get("policies") or []))


def test_d_people_page():
    """D. People: All companies and Test company filter."""
    token = _auth()
    # All companies
    r_all = client.get(
        "/api/admin/people",
        headers={"Authorization": f"Bearer {token}"},
        params={},
    )
    assert r_all.status_code == 200, r_all.text
    people_all = (r_all.json().get("people") or [])
    # Test company only
    r_test = client.get(
        "/api/admin/people",
        headers={"Authorization": f"Bearer {token}"},
        params={"company_id": TEST_COMPANY_ID},
    )
    assert r_test.status_code == 200, r_test.text
    people_test = (r_test.json().get("people") or [])
    hr_count = sum(1 for p in people_test if p.get("role") == "HR" or (p.get("hr_link_count") or 0) > 0)
    emp_count = sum(1 for p in people_test if (p.get("role") or "") in ("EMPLOYEE", "EMPLOYEE_USER") or (p.get("employee_link_count") or 0) > 0)
    print("\n4. PEOPLE PAGE")
    print("   All companies total:", len(people_all))
    print("   Test company filter total:", len(people_test))
    print("   Test company HR count:", hr_count)
    print("   Test company Employee count:", emp_count)


def test_e_assignments_page():
    """E. Assignments with Test company filter."""
    token = _auth()
    r = client.get(
        "/api/admin/assignments",
        headers={"Authorization": f"Bearer {token}"},
        params={"company_id": TEST_COMPANY_ID},
    )
    assert r.status_code == 200, r.text
    assignments = r.json().get("assignments") or []
    print("\n5. ASSIGNMENTS PAGE (Test company)")
    print("   count:", len(assignments))


def test_f_policies_for_test_company():
    """F. Policies for Test company."""
    token = _auth()
    r = client.get(
        "/api/admin/policies",
        headers={"Authorization": f"Bearer {token}"},
        params={"company_id": TEST_COMPANY_ID},
    )
    print("\n6. POLICIES (Test company)")
    if r.status_code != 200:
        print("   status:", r.status_code, r.text[:300])
        return
    data = r.json()
    policies = data.get("policies") if isinstance(data.get("policies"), list) else (data.get("policies_by_company") or {}).get("policies", [])
    if not isinstance(policies, list):
        policies = []
    print("   visible policies:", len(policies))
    for p in policies[:3]:
        print("     -", p.get("title") or p.get("policy_id"), "default_template:", p.get("template_source") == "default_platform_template" or p.get("is_default_template"))


def test_g_supplier_detail():
    """G. Supplier detail - first supplier from list."""
    token = _auth()
    r_list = client.get(
        "/api/suppliers",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 1},
    )
    print("\n7. SUPPLIER DETAIL")
    if r_list.status_code != 200:
        print("   list failed:", r_list.status_code)
        return
    suppliers = r_list.json().get("suppliers") or []
    if not suppliers:
        print("   no suppliers in DB, skip detail")
        return
    sid = suppliers[0].get("id")
    r = client.get(f"/api/suppliers/{sid}", headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 200:
        print("   working: yes (supplier_id=%s)" % sid)
    else:
        print("   failed:", r.status_code, r.text[:200])


def test_h_messages():
    """H. Messages threads for Test company."""
    token = _auth()
    r = client.get(
        "/api/admin/messages/threads",
        headers={"Authorization": f"Bearer {token}"},
        params={"company_id": TEST_COMPANY_ID, "limit": 10},
    )
    print("\n8. MESSAGES (Test company)")
    if r.status_code != 200:
        print("   failed:", r.status_code, r.text[:300])
        return
    data = r.json()
    threads = data.get("threads") or []
    print("   working: yes (empty-success or data)")
    print("   threads count:", len(threads))

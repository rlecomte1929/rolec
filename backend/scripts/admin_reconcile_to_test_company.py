#!/usr/bin/env python3
"""
Admin data-model reconciliation for Test company.

Assumptions:
- All demo/test users, assignments, and policies should belong to the Test company:
  id = 110854ad-3c85-4291-a484-0b43effb680e

Usage (from repo root):
  PYTHONPATH=. DATABASE_URL=sqlite:///./backend/relopass.db python backend/scripts/admin_reconcile_to_test_company.py
"""
import os
import sys
from datetime import datetime

from typing import Any, Dict

# Run from repo root so "backend" package is available
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
os.chdir(repo_root)

# Ensure we don't reseed demo-company-001 while running reconciliation
os.environ.setdefault("DISABLE_DEMO_RESEED", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/relopass.db")

from sqlalchemy import text  # noqa: E402
from backend.database import Database  # noqa: E402


TEST_COMPANY_ID = "110854ad-3c85-4291-a484-0b43effb680e"


def _print_heading(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def snapshot_state(db: Database) -> Dict[str, Any]:
    """Capture a mapping report of current records relevant to admin console."""
    out: Dict[str, Any] = {}
    with db.engine.connect() as conn:
        out["companies"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, name, country, created_at FROM companies ORDER BY id"
                )
            ).fetchall()
        ]
        out["profiles"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, role, email, full_name, company_id FROM profiles ORDER BY id"
                )
            ).fetchall()
        ]
        out["hr_users"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, company_id, profile_id, created_at FROM hr_users ORDER BY id"
                )
            ).fetchall()
        ]
        out["employees"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, company_id, profile_id, relocation_case_id, status, created_at "
                    "FROM employees ORDER BY id"
                )
            ).fetchall()
        ]
        out["relocation_cases"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, company_id, employee_id, hr_user_id, status, stage "
                    "FROM relocation_cases ORDER BY id"
                )
            ).fetchall()
        ]
        out["case_assignments"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, case_id, canonical_case_id, hr_user_id, employee_user_id, "
                    "employee_identifier, status, created_at "
                    "FROM case_assignments ORDER BY id"
                )
            ).fetchall()
        ]
        out["company_policies"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, company_id, title, extraction_status, template_source, is_default_template, created_at "
                    "FROM company_policies ORDER BY created_at"
                )
            ).fetchall()
        ]
        out["policy_versions"] = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT id, policy_id, version_number, status, created_at, updated_at "
                    "FROM policy_versions ORDER BY created_at"
                )
            ).fetchall()
        ]
    return out


def reconcile_to_test_company(db: Database) -> Dict[str, Any]:
    """Perform reconciliation updates to move demo data under Test company."""
    actions: Dict[str, Any] = {
        "profiles_updated_to_test_company": 0,
        "hr_users_repointed": 0,
        "hr_users_created": 0,
        "employees_repointed": 0,
        "employees_created": 0,
        "relocation_cases_repointed": 0,
        "policies_linked_to_test_company": False,
        "backfill_policy_result": None,
    }

    now = datetime.utcnow().isoformat()

    # 1) Ensure Test company exists (id is fixed)
    db.create_company(
        company_id=TEST_COMPANY_ID,
        name="Test company",
        country=None,
        status="active",
        plan_tier="low",
    )

    # 2) Profiles: point all non-admin profiles to Test company
    with db.engine.begin() as conn:
        r = conn.execute(
            text(
                "UPDATE profiles "
                "SET company_id = :cid "
                "WHERE COALESCE(role,'') <> 'ADMIN' AND company_id <> :cid"
            ),
            {"cid": TEST_COMPANY_ID},
        )
        actions["profiles_updated_to_test_company"] = r.rowcount

    # 3) HR users: repoint existing rows; create for HR profiles without hr_users
    with db.engine.begin() as conn:
        # Repoint any existing hr_users to Test company
        r = conn.execute(
            text("UPDATE hr_users SET company_id = :cid WHERE company_id <> :cid"),
            {"cid": TEST_COMPANY_ID},
        )
        actions["hr_users_repointed"] = r.rowcount

        # Create missing hr_users for HR profiles
        existing_hr_links = {
            row._mapping["profile_id"]
            for row in conn.execute(
                text("SELECT DISTINCT profile_id FROM hr_users"), {}
            ).fetchall()
        }
        hr_profiles = conn.execute(
            text("SELECT id FROM profiles WHERE role = 'HR'"), {}
        ).fetchall()
        for row in hr_profiles:
            pid = row._mapping["id"]
            if pid in existing_hr_links:
                continue
            uid = f"hr-{pid}"
            conn.execute(
                text(
                    "INSERT INTO hr_users (id, company_id, profile_id, permissions_json, created_at) "
                    "VALUES (:id, :cid, :pid, :perms, :ca)"
                ),
                {
                    "id": uid,
                    "cid": TEST_COMPANY_ID,
                    "pid": pid,
                    "perms": '{"can_manage_policy": true}',
                    "ca": now,
                },
            )
            actions["hr_users_created"] += 1

    # 4) Employees: repoint existing rows; create for employee profiles without employees
    with db.engine.begin() as conn:
        r = conn.execute(
            text(
                "UPDATE employees SET company_id = :cid WHERE company_id <> :cid"
            ),
            {"cid": TEST_COMPANY_ID},
        )
        actions["employees_repointed"] = r.rowcount

        existing_emp_links = {
            row._mapping["profile_id"]
            for row in conn.execute(
                text("SELECT DISTINCT profile_id FROM employees"), {}
            ).fetchall()
        }
        emp_profiles = conn.execute(
            text("SELECT id FROM profiles WHERE role IN ('EMPLOYEE','EMPLOYEE_USER')"), {}
        ).fetchall()
        for row in emp_profiles:
            pid = row._mapping["id"]
            if pid in existing_emp_links:
                continue
            eid = f"emp-{pid}"
            conn.execute(
                text(
                    "INSERT INTO employees (id, company_id, profile_id, band, assignment_type, "
                    "relocation_case_id, status, created_at) "
                    "VALUES (:id, :cid, :pid, NULL, NULL, NULL, 'active', :ca)"
                ),
                {"id": eid, "cid": TEST_COMPANY_ID, "pid": pid, "ca": now},
            )
            actions["employees_created"] += 1

    # 5) Relocation cases: repoint to Test company
    with db.engine.begin() as conn:
        r = conn.execute(
            text(
                "UPDATE relocation_cases SET company_id = :cid, updated_at = :now "
                "WHERE company_id <> :cid"
            ),
            {"cid": TEST_COMPANY_ID, "now": now},
        )
        actions["relocation_cases_repointed"] = r.rowcount

    # 6) Policies: ensure Test company has at least one policy based on default template
    try:
        existing_policies = db.list_company_policies(TEST_COMPANY_ID)
        if existing_policies:
            actions["backfill_policy_result"] = {
                "ok": True,
                "company_id": TEST_COMPANY_ID,
                "policy_id": existing_policies[0].get("id"),
                "linked": True,
                "reason": "company_already_has_policy",
            }
            actions["policies_linked_to_test_company"] = True
        else:
            templates = db.list_default_policy_templates()
            default_one = next(
                (t for t in templates if t.get("is_default_template")),
                templates[0] if templates else None,
            )
            if not default_one:
                actions["backfill_policy_result"] = {
                    "ok": False,
                    "error": "No default template found",
                    "policy_id": None,
                }
                actions["policies_linked_to_test_company"] = False
            else:
                tpl_id = default_one["id"]
                result = db.apply_default_template_to_company(
                    company_id=TEST_COMPANY_ID,
                    template_id=tpl_id,
                    overwrite_existing=False,
                    created_by=None,
                )
                actions["backfill_policy_result"] = result
                actions["policies_linked_to_test_company"] = bool(result.get("ok"))
    except Exception as exc:  # pragma: no cover - defensive
        actions["backfill_policy_result"] = {"ok": False, "error": str(exc)}
        actions["policies_linked_to_test_company"] = False

    return actions


def main() -> None:
    db = Database()

    _print_heading("1. Canonical data model summary")
    print("profiles: admin-facing people records, keyed by id == auth user id; link to company via profiles.company_id")
    print("hr_users: HR seats for a company, keyed by id; link to company via hr_users.company_id and to person via hr_users.profile_id")
    print("employees: employee seats for a company, keyed by id; link to company via employees.company_id and to person via employees.profile_id")
    print("relocation_cases: relocation cases, linked to company via relocation_cases.company_id and to employee via relocation_cases.employee_id")
    print("case_assignments: assignments tying hr_user_id, employee_user_id, and (canonical_)case_id together")
    print("company_policies: company-scoped policies; link to company via company_policies.company_id")
    print("policy_versions: structured versions of a policy; link to policy via policy_versions.policy_id\n")

    before = snapshot_state(db)

    _print_heading("2. Records found BEFORE reconciliation")
    print(f"companies: {len(before['companies'])}")
    print(f"profiles: {len(before['profiles'])}")
    print(f"hr_users: {len(before['hr_users'])}")
    print(f"employees: {len(before['employees'])}")
    print(f"relocation_cases: {len(before['relocation_cases'])}")
    print(f"case_assignments: {len(before['case_assignments'])}")
    print(f"company_policies: {len(before['company_policies'])}")
    print(f"policy_versions: {len(before['policy_versions'])}")

    print("\nProfiles and company_id:")
    for p in before["profiles"]:
        print(f"  profile {p['id']}: role={p['role']} email={p['email']} company_id={p.get('company_id')}")

    print("\nHR users:")
    for h in before["hr_users"]:
        print(f"  hr_user {h['id']}: company_id={h['company_id']} profile_id={h['profile_id']}")

    print("\nEmployees:")
    for e in before["employees"]:
        print(
            f"  employee {e['id']}: company_id={e['company_id']} profile_id={e['profile_id']} "
            f"relocation_case_id={e.get('relocation_case_id')}"
        )

    print("\nRelocation cases:")
    for rc in before["relocation_cases"]:
        print(
            f"  case {rc['id']}: company_id={rc['company_id']} employee_id={rc['employee_id']} "
            f"hr_user_id={rc.get('hr_user_id')} status={rc.get('status')} stage={rc.get('stage')}"
        )

    print("\nCase assignments:")
    for a in before["case_assignments"]:
        print(
            f"  assignment {a['id']}: case_id={a['case_id']} canonical_case_id={a['canonical_case_id']} "
            f"hr_user_id={a['hr_user_id']} employee_user_id={a['employee_user_id']} "
            f"employee_identifier={a['employee_identifier']} status={a['status']}"
        )

    print("\nCompany policies:")
    for cp in before["company_policies"]:
        print(
            f"  policy {cp['id']}: company_id={cp['company_id']} title={cp['title']} "
            f"status={cp['extraction_status']} template_source={cp.get('template_source')} "
            f"is_default_template={cp.get('is_default_template')}"
        )

    print("\nPolicy versions:")
    for pv in before["policy_versions"]:
        print(
            f"  version {pv['id']}: policy_id={pv['policy_id']} v={pv['version_number']} status={pv['status']}"
        )

    _print_heading("3. Reconciliation actions")
    actions = reconcile_to_test_company(db)
    for k, v in actions.items():
        print(f"{k}: {v}")

    after = snapshot_state(db)

    _print_heading("4. Counts AFTER reconciliation for Test company")
    # Simple per-table counts for Test company
    hr_users_tc = [h for h in after["hr_users"] if h["company_id"] == TEST_COMPANY_ID]
    employees_tc = [e for e in after["employees"] if e["company_id"] == TEST_COMPANY_ID]
    cases_tc = [c for c in after["relocation_cases"] if c["company_id"] == TEST_COMPANY_ID]
    policies_tc = [p for p in after["company_policies"] if p["company_id"] == TEST_COMPANY_ID]

    print(f"HR users (Test company): {len(hr_users_tc)}")
    print(f"Employees (Test company): {len(employees_tc)}")
    print(f"Relocation cases (Test company): {len(cases_tc)}")
    print(f"Company policies (Test company): {len(policies_tc)}")


if __name__ == "__main__":
    main()


"""Admin reconciliation — repair missing company/person/assignment/policy links.

Extracted from ``backend/main.py`` (WS1 Task 1.5). Bodies are verbatim;
auth uses ``backend.app.auth_deps``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ...database import db
from ..auth_deps import get_current_user, require_admin  # noqa: F401 — get_current_user is the override target

router = APIRouter(prefix="/api/admin/reconciliation", tags=["admin-reconciliation"])


def _require_reason(reason: Optional[str]) -> None:
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for admin actions")


class ReconciliationLinkPersonCompanyRequest(BaseModel):
    profile_id: str
    company_id: str


class ReconciliationLinkAssignmentCompanyRequest(BaseModel):
    assignment_id: str
    company_id: str
    reason: str


class ReconciliationLinkAssignmentPersonRequest(BaseModel):
    assignment_id: str
    profile_id: str


class ReconciliationLinkPolicyCompanyRequest(BaseModel):
    policy_id: str
    company_id: str


@router.get("/report")
def get_reconciliation_report(user: Dict[str, Any] = Depends(require_admin)):
    """Admin: full reconciliation report (companies, people, assignments, policies, missing links)."""
    data = db.get_reconciliation_report()
    db.log_audit(user["id"], "READ", "reconciliation_report", None, None, {})
    return data


@router.post("/backfill-test-company")
def admin_backfill_test_company(
    user: Dict[str, Any] = Depends(require_admin),
):
    """
    One-time non-destructive backfill: link orphan profiles, hr_users, and relocation_cases
    to the company named exactly 'Test company'. Does not overwrite existing linkage.
    """
    result = db.run_admin_reconciliation_backfill_test_company("Test company")
    db.log_audit(
        user["id"],
        "RECONCILIATION_BACKFILL",
        "reconciliation",
        None,
        None,
        result.get("summary") or {},
    )
    return result


@router.post("/link-person-company")
def reconciliation_link_person_company(
    body: ReconciliationLinkPersonCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: attach a profile (person) to a company. Updates profiles.company_id and employees if present."""
    if not db.get_profile_record(body.profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.admin_reassign_employee_company(body.profile_id, body.company_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_PERSON_COMPANY", "profile", body.profile_id, None, {"company_id": body.company_id})
    return {"ok": True}


@router.post("/link-assignment-company")
def reconciliation_link_assignment_company(
    body: ReconciliationLinkAssignmentCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: set assignment's case company (relocation_cases.company_id)."""
    _require_reason(body.reason)
    if not db.get_assignment_by_id(body.assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.admin_fix_assignment_company_linkage(body.assignment_id, body.company_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_ASSIGNMENT_COMPANY", "assignment", body.assignment_id, body.reason, {"company_id": body.company_id})
    return {"ok": True}


@router.post("/link-assignment-person")
def reconciliation_link_assignment_person(
    body: ReconciliationLinkAssignmentPersonRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: attach a profile (person) as employee to an assignment."""
    if not db.get_assignment_by_id(body.assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not db.get_profile_record(body.profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    db.attach_employee_to_assignment(body.assignment_id, body.profile_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_ASSIGNMENT_PERSON", "assignment", body.assignment_id, None, {"profile_id": body.profile_id})
    return {"ok": True}


@router.post("/link-policy-company")
def reconciliation_link_policy_company(
    body: ReconciliationLinkPolicyCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: reassign a company_policy to a company."""
    if not db.get_company_policy(body.policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.admin_link_policy_company(body.policy_id, body.company_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_POLICY_COMPANY", "company_policy", body.policy_id, None, {"company_id": body.company_id})
    return {"ok": True}


@router.post("/rebuild-test-company-graph")
def rebuild_test_company_graph(user: Dict[str, Any] = Depends(require_admin)):
    """
    Admin: full, idempotent rebuild of Test company graph in the current runtime DB.
    - Reassigns non-admin demo/test users and related seats/cases to the fixed Test company.
    - Repairs HR/employee seats and case/assignment linkage when recoverable.
    """
    TEST_COMPANY_ID = db.TEST_COMPANY_FIXED_ID

    # Simple before snapshot: counts per table for Test company
    with db.engine.connect() as conn:
        before_profiles = conn.execute(
            text("SELECT COUNT(*) AS n FROM profiles WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_hr = conn.execute(
            text("SELECT COUNT(*) AS n FROM hr_users WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_emp = conn.execute(
            text("SELECT COUNT(*) AS n FROM employees WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_cases = conn.execute(
            text("SELECT COUNT(*) AS n FROM relocation_cases WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_policies = conn.execute(
            text("SELECT COUNT(*) AS n FROM company_policies WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]

    summary = db.rebuild_test_company_graph()

    with db.engine.connect() as conn:
        after_profiles = conn.execute(
            text("SELECT COUNT(*) AS n FROM profiles WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_hr = conn.execute(
            text("SELECT COUNT(*) AS n FROM hr_users WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_emp = conn.execute(
            text("SELECT COUNT(*) AS n FROM employees WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_cases = conn.execute(
            text("SELECT COUNT(*) AS n FROM relocation_cases WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_policies = conn.execute(
            text("SELECT COUNT(*) AS n FROM company_policies WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]

    db.log_audit(
        user["id"],
        "RECONCILIATION_REBUILD_TEST_COMPANY",
        "reconciliation",
        None,
        None,
        summary,
    )

    return {
        "ok": True,
        "summary": {
            "test_company_id": db.TEST_COMPANY_FIXED_ID,
            **summary,
        },
        "before": {
            "profiles": before_profiles,
            "hr_users": before_hr,
            "employees": before_emp,
            "relocation_cases": before_cases,
            "policies": before_policies,
        },
        "after": {
            "profiles": after_profiles,
            "hr_users": after_hr,
            "employees": after_emp,
            "relocation_cases": after_cases,
            "policies": after_policies,
        },
    }

"""
W2-3 (HR-MVP): HR case escalation endpoints.

Gives HR a first-class "send this case to a specialist / legal" action — the
buyer-value audit's lever for reducing external legal spend. Tenant-scoped by the
HR user's resolved company (get_org_id_for_hr_user) + the case_escalations RLS.

Registered in BOTH backend/app/main.py and backend/main.py (prod boots
backend.main:app).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..services import case_escalation_service
from ...database import db

router = APIRouter(prefix="/api/hr", tags=["hr-escalation"])


class EscalateBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)
    kind: str = "specialist"  # specialist | legal | other
    assignee: Optional[str] = None
    sla_due_at: Optional[str] = None


class ResolveBody(BaseModel):
    resolution_note: str = Field(..., min_length=1, max_length=1000)


@router.post("/cases/{case_id}/escalate")
def escalate_case(
    case_id: str,
    body: EscalateBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Create an open escalation for a case (HR/admin only, scoped to their company)."""
    if not org_id:
        raise HTTPException(status_code=400, detail="No company associated with this HR user")
    return case_escalation_service.create_escalation(
        case_id=case_id,
        company_id=org_id,
        reason=body.reason,
        kind=body.kind,
        assignee=body.assignee,
        sla_due_at=body.sla_due_at,
        created_by=user.get("auth_uuid") or user.get("id"),
    )


@router.get("/cases/{case_id}/escalations")
def list_case_escalations(
    case_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """List a case's escalations within the caller's company."""
    if not org_id:
        return {"escalations": []}
    return {"escalations": case_escalation_service.list_escalations(case_id, org_id)}


@router.post("/escalations/{escalation_id}/resolve")
def resolve_case_escalation(
    escalation_id: str,
    body: ResolveBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Resolve an escalation (tenant-scoped; 404 if not in the caller's company)."""
    if not org_id:
        raise HTTPException(status_code=404, detail="Escalation not found")
    esc = case_escalation_service.resolve_escalation(
        escalation_id, org_id,
        resolution_note=body.resolution_note,
        resolved_by=user.get("auth_uuid") or user.get("id"),
    )
    if esc is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return esc


# ---------------------------------------------------------------------------
# [AIQ-1136 / NAV-HR-2-FU slice 2] HR-scoped case reassignment.
# HR (not just admin) may reassign a case's HR owner to another HR in their own
# company. Tenant-gated both ways: the case must be in the caller's company, and
# the target HR must be in the same company.
# ---------------------------------------------------------------------------


class HrReassignBody(BaseModel):
    hr_user_id: str = Field(..., min_length=1)  # the target HR's profile id
    reason: str = Field(..., min_length=1, max_length=1000)


def _assignment_company_id(assignment_id: str) -> Optional[str]:
    with db.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT rc.company_id AS company_id "
                "FROM case_assignments a "
                "LEFT JOIN relocation_cases rc ON CAST(rc.id AS TEXT) = CAST(a.case_id AS TEXT) "
                "WHERE a.id = :aid"
            ),
            {"aid": assignment_id},
        ).mappings().first()
    return row["company_id"] if row and row.get("company_id") else None


@router.get("/team")
def list_company_hr(
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """HR users in the caller's company — the reassignment target list."""
    if not org_id:
        raise HTTPException(status_code=400, detail="No company associated with this HR user")
    members = db.list_hr_users_with_profiles(org_id)
    return {
        "members": [
            {"profile_id": m.get("profile_id"), "name": m.get("name"), "email": m.get("email")}
            for m in members
        ]
    }


@router.patch("/cases/{case_id}/reassign-hr-owner")
def hr_reassign_case_owner(
    case_id: str,
    body: HrReassignBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Reassign a case's HR owner to another HR in the same company. HR-scoped."""
    if not org_id:
        raise HTTPException(status_code=400, detail="No company associated with this HR user")

    # Tenant gate 1: the case must belong to the caller's company (404, not 403).
    case_company = _assignment_company_id(case_id)
    if case_company is not None and case_company != org_id:
        raise HTTPException(status_code=404, detail="Case not found")

    # Tenant gate 2: the target HR must be in the same company.
    members = db.list_hr_users_with_profiles(org_id)
    if not any(str(m.get("profile_id")) == str(body.hr_user_id) for m in members):
        raise HTTPException(status_code=400, detail="Target HR user is not in your company")

    db.admin_reassign_hr_owner(case_id, body.hr_user_id)

    # Best-effort audit into the canonical audit_logs.
    try:
        from ..services.audit_log_service import insert_audit_log, ACTION_UPDATE, ACTOR_HUMAN
        import re

        _uuid_re = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        actor = user.get("auth_uuid") or user.get("id")
        actor_id = str(actor) if actor and re.match(_uuid_re, str(actor), re.I) else None
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="assignment",
                entity_id=case_id,
                action_type=ACTION_UPDATE,
                new_value={"event": "REASSIGN_HR_OWNER", "hr_user_id": body.hr_user_id, "reason": body.reason},
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        pass

    return {"ok": True}

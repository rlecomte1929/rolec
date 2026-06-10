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

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..services import case_escalation_service

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

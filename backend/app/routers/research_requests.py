"""AIQ-1349 P2 — research request intake + admin resolution.

POST /api/research-requests           (HR/employee) — request research for an uncovered corridor
GET  /api/admin/research-requests     (admin)       — list requests
PATCH /api/admin/research-requests/{id} (admin)     — approve (→ in_progress) / reject
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth_deps import require_admin, require_hr_or_employee
from ..services import research_request_service as svc

router = APIRouter(tags=["research-requests"])


class CreateResearchRequestBody(BaseModel):
    company_id: str
    dest_country: str
    origin_country: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None


class ResolveResearchBody(BaseModel):
    status: str  # "approved" | "rejected"
    notes: Optional[str] = None


@router.post("/api/research-requests")
def create_research_request(
    body: CreateResearchRequestBody,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    if not body.dest_country.strip():
        raise HTTPException(status_code=400, detail="dest_country is required")
    # NOTE: company_id is taken from the case context the requester is viewing;
    # server-side company validation is a P2 hardening follow-up.
    return svc.open_research_request(
        company_id=body.company_id,
        requester_user_id=str(user.get("id")),
        dest_country=body.dest_country,
        origin_country=body.origin_country,
        purpose=body.purpose,
        scope=body.scope,
    )


@router.get("/api/admin/research-requests")
def list_research_requests(
    status: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    return svc.list_research_requests(status=status)


@router.patch("/api/admin/research-requests/{request_id}")
def resolve_research_request(
    request_id: str,
    body: ResolveResearchBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")
    return svc.resolve_research_request(
        request_id=request_id,
        new_status=body.status,
        actor_user_id=str(user.get("id")),
        notes=body.notes,
    )

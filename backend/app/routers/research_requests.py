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
from ...database import db as main_db

router = APIRouter(tags=["research-requests"])


def _caller_company_id(user: Dict[str, Any]) -> str:
    """Resolve the caller's company SERVER-SIDE — never trust a client-supplied
    company_id (the service uses the admin client, so a body value would be an
    IDOR). Mirrors hr_catalog._caller_company_id."""
    uid = user.get("id")
    company_id = (
        (main_db.get_hr_company_id(uid) if uid else None)
        or (main_db.get_profile_record(uid) or {}).get("company_id")
        or user.get("company")
    )
    if not company_id:
        raise HTTPException(status_code=403, detail="No company associated with this user")
    return str(company_id)


class CreateResearchRequestBody(BaseModel):
    dest_country: str
    origin_country: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None


class ResolveResearchBody(BaseModel):
    status: str  # "approved" | "rejected"
    notes: Optional[str] = None


class CompleteResearchBody(BaseModel):
    result_summary: str
    actual_cost: Optional[float] = None


@router.post("/api/research-requests")
def create_research_request(
    body: CreateResearchRequestBody,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    if not body.dest_country.strip():
        raise HTTPException(status_code=400, detail="dest_country is required")
    return svc.open_research_request(
        company_id=_caller_company_id(user),  # server-resolved (anti-IDOR)
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


@router.post("/api/admin/research-requests/{request_id}/complete")
def complete_research_request(
    request_id: str,
    body: CompleteResearchBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Publish a researched corridor: requires the curation review to be resolved
    (strict human gate), records cost/summary, notifies the requester."""
    try:
        return svc.complete_research_request(
            request_id=request_id,
            actor_user_id=str(user.get("id")),
            result_summary=body.result_summary,
            actual_cost=body.actual_cost,
        )
    except svc.ReviewNotResolvedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

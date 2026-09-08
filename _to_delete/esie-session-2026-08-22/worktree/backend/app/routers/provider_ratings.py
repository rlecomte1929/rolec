"""
CATALOG-3 / AIQ-1067 — Employee provider rating endpoint.

POST /api/employee/providers/{supplier_id}/rating
  Body: { case_id, score (1-5), comment? }

An employee rates a provider for one of THEIR cases. The rating is idempotent
per (employee, supplier, case) and feeds supplier_scoring_metadata, which the
recommendation engine scores. See provider_ratings_service.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_current_user
from ..db import SessionLocal
from ..services import provider_ratings_service

router = APIRouter(prefix="/api/employee/providers", tags=["provider-ratings"])


class ProviderRatingBody(BaseModel):
    case_id: str = Field(..., description="The case this rating is for")
    score: int = Field(..., ge=1, le=5, description="1-5 star rating")
    comment: Optional[str] = Field(None, max_length=2000)


@router.post("/{supplier_id}/rating")
def rate_provider(
    body: ProviderRatingBody,
    supplier_id: str = Path(..., description="Registry supplier id (recs item_id)"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    # Use the canonical Supabase auth uuid (AUTH-ID-1): case_assignments.employee_user_id
    # and profiles.id are uuid-keyed, while user["id"] is the legacy users.id. Comparing
    # the legacy id against employee_user_id 403'd every real employee.
    employee_id = user.get("auth_uuid") or user.get("id")
    if not employee_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Ownership is validated against case_assignments — the employee-facing case
    # id space (public.cases is a separate space under the case-identity schism).
    # company_id is resolved best-effort from the employee profile for HR scoping.
    with SessionLocal() as session:
        asg = session.execute(
            text("SELECT employee_user_id FROM case_assignments WHERE id = :cid"),
            {"cid": body.case_id},
        ).first()
        if not asg:
            raise HTTPException(status_code=404, detail="Assignment not found")

        is_admin = bool(user.get("is_admin")) or (user.get("role") or "").upper() == "ADMIN"
        if str(asg.employee_user_id) != str(employee_id) and not is_admin:
            raise HTTPException(status_code=403, detail="Not your case")

        prof = session.execute(
            text("SELECT company_id FROM profiles WHERE id = :eid"),
            {"eid": employee_id},
        ).first()
    company_id = str(prof.company_id) if prof and prof.company_id else None

    aggregate = provider_ratings_service.record_rating(
        employee_id=str(employee_id),
        company_id=company_id,
        supplier_id=supplier_id,
        case_id=body.case_id,
        score=body.score,
        comment=body.comment,
    )
    return {"ok": True, "supplier_id": supplier_id, **aggregate}

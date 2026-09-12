"""Admin Lead CRM router — inbound person-level leads.
Modeled on admin_prospects.py (ORM via SessionLocal). Admin-only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import Lead, ProspectCandidate
from ._leads_schemas import VALID_STATUSES, LeadOut, LeadPatchIn, LeadStatsOut

router = APIRouter(prefix="/leads", tags=["admin-leads"])


def _to_out(lead: Lead, matched_domains: set) -> LeadOut:
    out = LeadOut.model_validate(lead)
    out.matched_prospect = bool(lead.company_domain and lead.company_domain in matched_domains)
    return out


@router.get("", response_model=Dict[str, Any])
def list_leads(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    include_test: bool = Query(False, description="AIQ-2327: include synthetic is_test leads"),
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    s = SessionLocal()
    try:
        q = s.query(Lead)
        total_q = s.query(func.count(Lead.id))
        if not include_test:
            q = q.filter(Lead.is_test.is_(False))
            total_q = total_q.filter(Lead.is_test.is_(False))
        if status:
            q = q.filter(Lead.status == status)
        if search:
            like = f"%{search.lower()}%"
            q = q.filter(func.lower(Lead.email).like(like))
        rows = q.order_by(desc(Lead.created_at)).limit(limit).all()
        total = total_q.scalar() or 0
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain.isnot(None)).all()}
        return {"total": total, "leads": [_to_out(r, domains).model_dump() for r in rows]}
    finally:
        s.close()


@router.get("/stats", response_model=LeadStatsOut)
def lead_stats(_admin: dict = Depends(require_admin)) -> LeadStatsOut:
    s = SessionLocal()
    try:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        total = s.query(func.count(Lead.id)).scalar() or 0
        new_this_week = s.query(func.count(Lead.id)).filter(Lead.created_at >= week_ago).scalar() or 0
        by_status = dict(s.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all())
        return LeadStatsOut(total=total, new_this_week=new_this_week, by_status=by_status)
    finally:
        s.close()


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, _admin: dict = Depends(require_admin)) -> LeadOut:
    s = SessionLocal()
    try:
        lead = s.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain == lead.company_domain).all()}
        return _to_out(lead, domains)
    finally:
        s.close()


@router.patch("/{lead_id}", response_model=LeadOut)
def patch_lead(lead_id: str, body: LeadPatchIn, _admin: dict = Depends(require_admin)) -> LeadOut:
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    s = SessionLocal()
    try:
        lead = s.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if body.status is not None:
            lead.status = body.status
        if body.tags is not None:
            lead.tags = body.tags
        s.commit()
        s.refresh(lead)
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain == lead.company_domain).all()}
        return _to_out(lead, domains)
    finally:
        s.close()

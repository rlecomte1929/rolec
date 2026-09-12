"""Admin Lead CRM router — inbound person-level leads.
Modeled on admin_prospects.py (ORM via SessionLocal). Admin-only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, text
from sqlalchemy.orm import defer

from ...db.test_data_filter import exclude_test_people, looks_like_test_email, table_has_is_test
from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import Lead, ProspectCandidate
from ._leads_schemas import VALID_STATUSES, LeadOut, LeadPatchIn, LeadStatsOut

router = APIRouter(prefix="/leads", tags=["admin-leads"])


def _to_out(lead: Lead, matched_domains: set, *, has_is_test: bool) -> LeadOut:
    return LeadOut(
        id=lead.id,
        email=lead.email,
        first_name=lead.first_name,
        last_name=lead.last_name,
        company_domain=lead.company_domain,
        source=lead.source,
        status=lead.status,
        tags=list(lead.tags or []),
        message=lead.message,
        utm_source=lead.utm_source,
        utm_campaign=lead.utm_campaign,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        matched_prospect=bool(lead.company_domain and lead.company_domain in matched_domains),
        is_test=bool(lead.is_test) if has_is_test else looks_like_test_email(lead.email),
    )


def _leads_query(s):
    """Entity query that never SELECTs is_test when the column is absent."""
    has = table_has_is_test(s, "leads")
    q = s.query(Lead)
    if not has:
        q = q.options(defer(Lead.is_test))
    return q, has


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
        q, has_is_test = _leads_query(s)
        total_q = s.query(func.count(Lead.id))
        if not include_test:
            if has_is_test:
                q = q.filter(Lead.is_test.is_(False))
                total_q = total_q.filter(Lead.is_test.is_(False))
            else:
                pattern = text(exclude_test_people("email"))
                q = q.filter(pattern)
                total_q = total_q.filter(pattern)
        if status:
            q = q.filter(Lead.status == status)
        if search:
            like = f"%{search.lower()}%"
            q = q.filter(func.lower(Lead.email).like(like))
        rows = q.order_by(desc(Lead.created_at)).limit(limit).all()
        total = total_q.scalar() or 0
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain.isnot(None)).all()}
        return {"total": total, "leads": [_to_out(r, domains, has_is_test=has_is_test).model_dump() for r in rows]}
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
        q, has_is_test = _leads_query(s)
        lead = q.filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain == lead.company_domain).all()}
        return _to_out(lead, domains, has_is_test=has_is_test)
    finally:
        s.close()


@router.patch("/{lead_id}", response_model=LeadOut)
def patch_lead(lead_id: str, body: LeadPatchIn, _admin: dict = Depends(require_admin)) -> LeadOut:
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    s = SessionLocal()
    try:
        q, has_is_test = _leads_query(s)
        lead = q.filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if body.status is not None:
            lead.status = body.status
        if body.tags is not None:
            lead.tags = body.tags
        s.commit()
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain == lead.company_domain).all()}
        return _to_out(lead, domains, has_is_test=has_is_test)
    finally:
        s.close()

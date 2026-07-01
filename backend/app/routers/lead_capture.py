"""Public, unauthenticated, rate-limited lead capture.
Fed by the marketing-site demo forms. Writes a person-level lead and
emits a `lead_captured` analytics event (bottom of the marketing funnel).

PII: `message` is stored raw for GTM. If a future ticket routes it to an
LLM for enrichment, it MUST pass mask_pii() first (repo data-minimisation rule)."""
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...rate_limit import limiter
from ..db import SessionLocal
from ..models import Lead, ProspectCandidate
from ..services.analytics_service import emit_event
from ._leads_schemas import LeadCaptureIn

log = logging.getLogger(__name__)
router = APIRouter(tags=["public-lead-capture"])


def _domain_from_email(email: str) -> str | None:
    return email.split("@", 1)[1].lower() if "@" in email else None


@router.post("/api/public/lead-capture", status_code=201)
@limiter.limit("10/hour;50/day")
def capture_lead(body: LeadCaptureIn, request: Request) -> JSONResponse:
    domain = body.company_domain or _domain_from_email(str(body.email))
    lead_id = str(uuid.uuid4())
    matched = False
    s = SessionLocal()
    try:
        lead = Lead(
            id=lead_id, email=str(body.email), first_name=body.first_name,
            last_name=body.last_name, company_domain=domain, source=body.source,
            status="new", tags=[], message=body.message,
            utm_source=body.utm_source, utm_campaign=body.utm_campaign,
        )
        s.add(lead)
        s.commit()
        if domain:
            matched = s.query(ProspectCandidate.id).filter(
                ProspectCandidate.company_domain == domain).first() is not None
    finally:
        s.close()
    # Bottom-of-funnel event → analytics_events (consumed by marketing dashboard)
    emit_event("lead_captured", extra={
        "source": body.source, "utm_source": body.utm_source,
        "utm_campaign": body.utm_campaign, "matched_prospect": matched,
    })
    return JSONResponse(status_code=201, content={"id": lead_id, "matched_prospect": matched})

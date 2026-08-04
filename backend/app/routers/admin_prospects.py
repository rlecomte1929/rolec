"""
Admin HR Prospect Pipeline router.

Batch-import a seed list of companies, kick off LLM enrichment as
BackgroundTasks, triage the results (approve / maybe / reject), and
export the approved list as CSV.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, text

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import ProspectCandidate
from ..services.prospect_enrichment_service import (
    EnrichmentRequest,
    enrich_prospect,
)
from ..services.prospect_icp_config import ICP_CONFIG
from ..services.prospect_web_search import (
    TAVILY_COST_PER_QUERY_USD,
    estimate_batch_cost_usd,
)


log = logging.getLogger(__name__)

router = APIRouter(prefix="/prospects", tags=["admin-prospects"])


VALID_STATUSES = {
    "pending_enrichment",
    "enriched",
    "enrichment_failed",
    "approved",
    "maybe",
    "rejected",
    "promoted",
}
TRIAGE_DECISIONS = {"approved", "maybe", "rejected"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProspectSeedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(..., min_length=1, max_length=300)
    company_domain: Optional[str] = Field(None, max_length=300)
    company_linkedin_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)


class BatchIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospects: List[ProspectSeedItem]
    enable_web_search: bool = False


class BatchIngestResponse(BaseModel):
    batch_id: str
    queued: int
    skipped_duplicates: int
    duplicate_domains: List[str]
    enable_web_search: bool
    estimated_web_search_cost_usd: float


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str  # approved | maybe | rejected


class ReenrichRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_web_search: bool = False


class ReenrichFailedResponse(BaseModel):
    reenriched: int
    enable_web_search: bool
    estimated_web_search_cost_usd: float


class ProspectRowOut(BaseModel):
    id: str
    company_name: str
    company_domain: Optional[str]
    company_linkedin_url: Optional[str]
    icp_score: Optional[int]
    qualification_band: Optional[str]
    suggested_contact_title: Optional[str]
    suggested_hook: Optional[str]
    status: str
    web_search_used: bool
    batch_id: Optional[str]
    enrichment_error: Optional[str]
    enriched: Optional[Dict[str, Any]] = None
    raw_input: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    enriched_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]


def _row_to_out(row: ProspectCandidate, *, include_payloads: bool) -> ProspectRowOut:
    enriched: Optional[Dict[str, Any]] = None
    raw_input: Optional[Dict[str, Any]] = None
    if include_payloads:
        try:
            enriched = json.loads(row.enriched_json or "{}") or {}
        except (TypeError, ValueError):
            enriched = {}
        try:
            raw_input = json.loads(row.raw_input_json or "{}") or {}
        except (TypeError, ValueError):
            raw_input = {}
    return ProspectRowOut(
        id=row.id,
        company_name=row.company_name,
        company_domain=row.company_domain,
        company_linkedin_url=row.company_linkedin_url,
        icp_score=row.icp_score,
        qualification_band=row.qualification_band,
        suggested_contact_title=row.suggested_contact_title,
        suggested_hook=row.suggested_hook,
        status=row.status,
        web_search_used=bool(row.web_search_used),
        batch_id=row.batch_id,
        enrichment_error=row.enrichment_error,
        enriched=enriched,
        raw_input=raw_input,
        created_at=row.created_at,
        updated_at=row.updated_at,
        enriched_at=row.enriched_at,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/icp-config")
def get_icp_config(_: dict = Depends(require_admin)) -> Dict[str, Any]:
    """Return the currently configured ICP as-is (read-only in v1)."""
    cfg = ICP_CONFIG
    return {
        "mission_summary": cfg.mission_summary,
        "target_size_bands": cfg.target_size_bands,
        "target_sectors": cfg.target_sectors,
        "target_regions": cfg.target_regions,
        "strong_signals": cfg.strong_signals,
        "weak_signals": cfg.weak_signals,
        "disqualifiers": cfg.disqualifiers,
        "contact_titles": cfg.contact_titles,
        "band_thresholds": cfg.band_thresholds,
    }


@router.get("/cost-estimate")
def cost_estimate(
    prospect_count: int = Query(..., ge=0, le=10_000),
    _: dict = Depends(require_admin),
) -> Dict[str, Any]:
    """Estimate the marginal cost of enabling web search for a batch."""
    return {
        "prospect_count": prospect_count,
        "tavily_cost_per_query_usd": TAVILY_COST_PER_QUERY_USD,
        "estimated_web_search_cost_usd": estimate_batch_cost_usd(prospect_count),
        "notes": (
            "Tavily basic search ~$0.005 per query. LLM synthesis cost is "
            "separate (~$0.004-0.010 per prospect on gpt-4.1-mini). "
            "Disabling web search removes the Tavily cost entirely."
        ),
    }


@router.post("/batch", response_model=BatchIngestResponse)
def ingest_batch(
    payload: BatchIngestRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_admin),
) -> BatchIngestResponse:
    if not payload.prospects:
        raise HTTPException(status_code=400, detail="prospects list is empty")
    if len(payload.prospects) > 500:
        raise HTTPException(
            status_code=400,
            detail="batch limit is 500 prospects per request",
        )
    batch_id = str(uuid.uuid4())
    queued_ids: List[str] = []
    duplicate_domains: List[str] = []
    with SessionLocal() as db:
        # Collect existing domains once so the dedupe check is O(batch) rather
        # than one query per row. Lower-cased to match the input normalisation
        # below — domain comparison is case-insensitive.
        existing_domains = {
            (d or "").strip().lower()
            for (d,) in db.query(ProspectCandidate.company_domain)
            .filter(ProspectCandidate.company_domain.isnot(None))
            .all()
        }
        seen_in_batch: set[str] = set()
        for item in payload.prospects:
            normalized_domain = (item.company_domain or "").strip().lower() or None
            if normalized_domain:
                if normalized_domain in existing_domains or normalized_domain in seen_in_batch:
                    duplicate_domains.append(normalized_domain)
                    continue
                seen_in_batch.add(normalized_domain)
            row = ProspectCandidate(
                id=str(uuid.uuid4()),
                company_name=item.company_name.strip(),
                company_domain=(item.company_domain or "").strip() or None,
                company_linkedin_url=(item.company_linkedin_url or "").strip() or None,
                raw_input_json=json.dumps(
                    {
                        "notes": item.notes or "",
                        "submitted_by": user.get("email") or user.get("id"),
                    },
                    ensure_ascii=False,
                ),
                status="pending_enrichment",
                batch_id=batch_id,
                web_search_used=False,
            )
            db.add(row)
            queued_ids.append(row.id)
        db.commit()
    for prospect_id in queued_ids:
        background_tasks.add_task(
            enrich_prospect,
            EnrichmentRequest(
                prospect_id=prospect_id,
                enable_web_search=payload.enable_web_search,
            ),
        )
    return BatchIngestResponse(
        batch_id=batch_id,
        queued=len(queued_ids),
        skipped_duplicates=len(duplicate_domains),
        duplicate_domains=duplicate_domains,
        enable_web_search=payload.enable_web_search,
        estimated_web_search_cost_usd=(
            estimate_batch_cost_usd(len(queued_ids))
            if payload.enable_web_search
            else 0.0
        ),
    )


@router.post("/reenrich-failed", response_model=ReenrichFailedResponse)
def reenrich_failed(
    body: ReenrichRequest,
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_admin),
) -> ReenrichFailedResponse:
    """Re-queue every `enrichment_failed` row for enrichment in one call.

    Caps at 500 rows per call to match the batch-ingest limit — if you
    somehow have more failures than that, run the action a second time.
    The original `batch_id` on each row is preserved so the prospects
    stay grouped with their import batch.
    """
    queued_ids: List[str] = []
    with SessionLocal() as db:
        rows = (
            db.query(ProspectCandidate)
            .filter(ProspectCandidate.status == "enrichment_failed")
            .limit(500)
            .all()
        )
        for row in rows:
            row.status = "pending_enrichment"
            row.enrichment_error = None
            queued_ids.append(row.id)
        db.commit()
    for prospect_id in queued_ids:
        background_tasks.add_task(
            enrich_prospect,
            EnrichmentRequest(
                prospect_id=prospect_id,
                enable_web_search=body.enable_web_search,
            ),
        )
    return ReenrichFailedResponse(
        reenriched=len(queued_ids),
        enable_web_search=body.enable_web_search,
        estimated_web_search_cost_usd=(
            estimate_batch_cost_usd(len(queued_ids))
            if body.enable_web_search
            else 0.0
        ),
    )


@router.get("")
def list_prospects(
    status: Optional[str] = Query(None),
    band: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: dict = Depends(require_admin),
) -> Dict[str, Any]:
    with SessionLocal() as db:
        q = db.query(ProspectCandidate)
        if status:
            if status not in VALID_STATUSES:
                raise HTTPException(status_code=400, detail="invalid status filter")
            q = q.filter(ProspectCandidate.status == status)
        if band:
            q = q.filter(ProspectCandidate.qualification_band == band)
        if batch_id:
            q = q.filter(ProspectCandidate.batch_id == batch_id)
        if min_score is not None:
            q = q.filter(ProspectCandidate.icp_score >= min_score)
        total = q.count()
        rows = (
            q.order_by(
                desc(ProspectCandidate.icp_score.is_(None)),
                desc(ProspectCandidate.icp_score),
                desc(ProspectCandidate.created_at),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "prospects": [
                _row_to_out(r, include_payloads=False).model_dump(mode="json")
                for r in rows
            ],
        }


@router.get("/{prospect_id}", response_model=ProspectRowOut)
def get_prospect(prospect_id: str, _: dict = Depends(require_admin)) -> ProspectRowOut:
    with SessionLocal() as db:
        row = db.get(ProspectCandidate, prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect not found")
        return _row_to_out(row, include_payloads=True)


@router.post("/{prospect_id}/triage", response_model=ProspectRowOut)
def triage_prospect(
    prospect_id: str,
    body: TriageRequest,
    user: dict = Depends(require_admin),
) -> ProspectRowOut:
    if body.decision not in TRIAGE_DECISIONS:
        raise HTTPException(status_code=400, detail="decision must be approved, maybe, or rejected")
    with SessionLocal() as db:
        row = db.get(ProspectCandidate, prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect not found")
        if row.status in {"pending_enrichment"}:
            raise HTTPException(
                status_code=409,
                detail="prospect is still enriching — triage after enrichment completes",
            )
        row.status = body.decision
        row.reviewed_at = datetime.utcnow()
        row.reviewed_by = user.get("email") or user.get("id")
        db.commit()
        db.refresh(row)
        return _row_to_out(row, include_payloads=True)


@router.post("/{prospect_id}/reenrich", response_model=ProspectRowOut)
def reenrich_prospect(
    prospect_id: str,
    body: ReenrichRequest,
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_admin),
) -> ProspectRowOut:
    with SessionLocal() as db:
        row = db.get(ProspectCandidate, prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect not found")
        row.status = "pending_enrichment"
        row.enrichment_error = None
        db.commit()
        db.refresh(row)
        out = _row_to_out(row, include_payloads=True)
    background_tasks.add_task(
        enrich_prospect,
        EnrichmentRequest(
            prospect_id=prospect_id,
            enable_web_search=body.enable_web_search,
        ),
    )
    return out


@router.delete("/{prospect_id}")
def delete_prospect(prospect_id: str, _: dict = Depends(require_admin)) -> Dict[str, Any]:
    """Hard-delete a prospect row. Use for duplicates or rows you don't
    want cluttering the list — a rejection keeps the row visible under
    the `rejected` filter, whereas this removes it entirely."""
    with SessionLocal() as db:
        row = db.get(ProspectCandidate, prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect not found")
        db.delete(row)
        db.commit()
    return {"deleted": prospect_id}


@router.get("/export.csv")
def export_approved_csv(
    status: str = Query("approved"),
    _: dict = Depends(require_admin),
) -> StreamingResponse:
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status filter")
    with SessionLocal() as db:
        rows = (
            db.query(ProspectCandidate)
            .filter(ProspectCandidate.status == status)
            .order_by(
                desc(ProspectCandidate.icp_score.is_(None)),
                desc(ProspectCandidate.icp_score),
            )
            .all()
        )
        payloads = [json.loads(r.enriched_json or "{}") for r in rows]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "company_name",
            "company_domain",
            "company_linkedin_url",
            "icp_score",
            "qualification_band",
            "suggested_contact_title",
            "suggested_hook",
            "size_band",
            "sector",
            "hq_country",
            "mobility_signals",
            "icp_rationale",
        ]
    )
    for row, enriched in zip(rows, payloads):
        profile = (enriched or {}).get("company_profile") or {}
        signals = (enriched or {}).get("mobility_signals") or []
        signal_str = "; ".join(
            f"{s.get('type', '')}: {s.get('evidence', '')}" for s in signals if isinstance(s, dict)
        )
        writer.writerow(
            [
                row.company_name,
                row.company_domain or "",
                row.company_linkedin_url or "",
                row.icp_score if row.icp_score is not None else "",
                row.qualification_band or "",
                row.suggested_contact_title or "",
                row.suggested_hook or "",
                profile.get("size_band", ""),
                profile.get("sector", ""),
                profile.get("hq_country", ""),
                signal_str,
                (enriched or {}).get("icp_rationale", ""),
            ]
        )
    buffer.seek(0)
    filename = f"prospects_{status}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{prospect_id}/promote")
def promote_prospect(
    prospect_id: str,
    user: dict = Depends(require_admin),
) -> Dict[str, Any]:
    """Promote an approved prospect into the LinkedIn Outreach CRM.

    Bridges the two halves of the funnel that were previously joined only by a
    CSV export + manual re-entry: creates a ``linkedin_prospects`` row seeded
    with the company, the suggested contact title, and — as the initial draft —
    the enrichment hook, so nothing the pipeline produced is thrown away.

    The contact is a shell: the admin still fills in the real person's name and
    LinkedIn URL. Because ``linkedin_prospects.linkedin_url`` is UNIQUE NOT NULL
    and a company-level candidate has no person yet, we seed the URL with a
    LinkedIn people-search for the suggested title at the company (a useful
    starting point for finding the human) made unique per candidate.

    The candidate moves to ``promoted`` so it leaves the approved queue and
    can't be double-promoted. ``linkedin_prospects`` is written via the
    service-role session (same pattern as admin_outreach), so RLS is bypassed
    intentionally for this admin-gated action.
    """
    with SessionLocal() as db:
        row = db.get(ProspectCandidate, prospect_id)
        if row is None:
            raise HTTPException(status_code=404, detail="prospect not found")
        if row.status == "promoted":
            raise HTTPException(
                status_code=409, detail="prospect already promoted to outreach"
            )
        if row.status != "approved":
            raise HTTPException(
                status_code=409,
                detail="approve the prospect before promoting it to outreach",
            )

        try:
            enriched = json.loads(row.enriched_json or "{}") or {}
        except (TypeError, ValueError):
            enriched = {}
        profile = enriched.get("company_profile") or {}

        title = (row.suggested_contact_title or "HR / Mobility lead").strip()
        company = row.company_name
        hook = (row.suggested_hook or "").strip()

        search = quote(f"{title} {company}".strip())
        linkedin_url = (
            "https://www.linkedin.com/search/results/people/"
            f"?keywords={search}#rp-{row.id[:8]}"
        )

        note_bits = [f"Promoted from HR Prospect Pipeline (candidate {row.id})."]
        if row.icp_score is not None:
            note_bits.append(
                f"ICP score {row.icp_score}, band {row.qualification_band or '—'}."
            )
        if row.company_domain:
            note_bits.append(f"Domain: {row.company_domain}.")
        rationale = (enriched.get("icp_rationale") or "").strip()
        if rationale:
            note_bits.append(f"Rationale: {rationale}")
        note_bits.append(
            "Replace the placeholder name + LinkedIn URL with the real contact."
        )
        notes = " ".join(note_bits)

        seed_status = "message_drafted" if hook else "flagged"
        new_row = (
            db.execute(
                text(
                    """
                    INSERT INTO public.linkedin_prospects
                        (full_name, linkedin_url, company_name, company_size,
                         job_title, corridor_relevance, notes, source, status)
                    VALUES
                        (:full_name, :linkedin_url, :company_name, :company_size,
                         :job_title, :corridor_relevance, :notes, :source, :status)
                    RETURNING id
                    """
                ),
                {
                    "full_name": f"[Contact — {title}]",
                    "linkedin_url": linkedin_url,
                    "company_name": company,
                    "company_size": profile.get("size_band"),
                    "job_title": title,
                    "corridor_relevance": None,
                    "notes": notes,
                    "source": "prospect_pipeline",
                    "status": seed_status,
                },
            )
            .mappings()
            .first()
        )
        new_prospect_id = str(new_row["id"])

        if hook:
            db.execute(
                text(
                    """
                    INSERT INTO public.outreach_messages
                        (prospect_id, message_type, body, status, personalisation_notes)
                    VALUES
                        (:prospect_id, 'initial', :body, 'draft', :notes)
                    """
                ),
                {
                    "prospect_id": new_prospect_id,
                    "body": hook,
                    "notes": "Seeded from HR Prospect Pipeline enrichment.",
                },
            )

        row.status = "promoted"
        row.reviewed_at = datetime.utcnow()
        row.reviewed_by = user.get("email") or user.get("id")
        db.commit()

    return {
        "promoted_prospect_id": new_prospect_id,
        "outreach_status": seed_status,
        "created_initial_draft": bool(hook),
    }

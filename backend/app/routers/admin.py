from __future__ import annotations

import logging
from typing import Any, List, Optional
from datetime import datetime, timedelta
import os
import uuid

from fastapi import APIRouter, Header, HTTPException, Depends

from ..db import SessionLocal
from ...database import db, Database
from .. import crud, schemas, models
from ..services.research import run_country_research
from ..services.official_ingest_service import ingest_url_to_knowledge_doc
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def _audit_postgres(
    *,
    entity_type: str,
    entity_id: str,
    action_type: str,
    new_value: Optional[dict] = None,
    old_value: Optional[dict] = None,
    actor_id: Optional[str] = None,
) -> None:
    """Write one audit_logs row on the Postgres tier; never raise."""
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action_type,
                old_value=old_value,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        logger.exception(
            "audit_log write failed entity_type=%s entity_id=%s",
            entity_type,
            entity_id,
        )


def _is_admin_user(user: dict) -> bool:
    role = (user.get("role") or "").upper()
    if role == "ADMIN":
        return True
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() == "ADMIN":
        return True
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return True
    return False


def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user or not _is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/countries", response_model=schemas.CountryListDTO)
def list_countries(user: dict = Depends(require_admin)):
    with SessionLocal() as db:
        profiles = crud.list_country_profiles(db)
        items = []
        for profile in profiles:
            sources = crud.list_sources(db, profile.country_code)
            requirements = crud.list_requirements(db, profile.country_code)
            top_domains = list({source.publisher_domain for source in sources})[:3]
            items.append(
                schemas.CountryListItemDTO(
                    countryCode=profile.country_code,
                    lastUpdatedAt=profile.last_updated_at,
                    requirementsCount=len(requirements),
                    confidenceScore=profile.confidence_score,
                    topDomains=top_domains,
                )
            )
        return schemas.CountryListDTO(countries=items)


@router.get("/countries/{country_code}", response_model=schemas.CountryProfileDTO)
def get_country(country_code: str, user: dict = Depends(require_admin)):
    with SessionLocal() as db:
        profile = crud.get_country_profile(db, country_code.upper())
        if not profile:
            raise HTTPException(status_code=404, detail="Country not found")
        sources = crud.list_sources(db, profile.country_code)
        requirements = crud.list_requirements(db, profile.country_code)
        groups = {}
        for item in requirements:
            groups.setdefault(item.pillar, []).append(
                schemas.RequirementItemDTO(
                    id=item.id,
                    pillar=item.pillar,
                    title=item.title,
                    description=item.description,
                    severity=item.severity,
                    owner=item.owner,
                    requiredFields=json.loads(item.required_fields_json),
                    statusForCase="NEEDS_REVIEW",
                    citations=[],
                )
            )

        return schemas.CountryProfileDTO(
            countryCode=profile.country_code,
            lastUpdatedAt=profile.last_updated_at,
            confidenceScore=profile.confidence_score,
            sources=[schemas.SourceRecordDTO(
                id=source.id,
                url=source.url,
                title=source.title,
                publisherDomain=source.publisher_domain,
                retrievedAt=source.retrieved_at,
                snippet=source.snippet,
            ) for source in sources],
            requirementGroups=[{"pillar": pillar, "items": items} for pillar, items in groups.items()],
        )


_REVIEW_STATUSES = {"approved", "rejected"}


def _review_dto(item: Any) -> schemas.AdminRequirementReviewDTO:
    def _arr(raw: Optional[str]) -> Optional[List[str]]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    return schemas.AdminRequirementReviewDTO(
        id=item.id,
        purpose=item.purpose,
        pillar=item.pillar,
        title=item.title,
        description=item.description,
        severity=item.severity,
        owner=item.owner,
        verificationStatus=getattr(item, "verification_status", None),
        attestationStatus=getattr(item, "attestation_status", None),
        attestedBy=getattr(item, "attested_by", None),
        attestedAt=getattr(item, "attested_at", None),
        reviewStatus=getattr(item, "review_status", "approved"),
        reviewedBy=getattr(item, "reviewed_by", None),
        reviewedAt=getattr(item, "reviewed_at", None),
        appliesToNationalityClasses=_arr(getattr(item, "applies_to_nationality_classes_json", None)),
        appliesToAssignmentTypes=_arr(getattr(item, "applies_to_assignment_types_json", None)),
        citations=_arr(getattr(item, "citations_json", None)) or [],
        lastVerifiedAt=getattr(item, "last_verified_at", None),
    )


@router.get("/countries/{country_code}/requirements", response_model=schemas.AdminRequirementListDTO)
def list_country_requirements(country_code: str, user: dict = Depends(require_admin)):
    """Every requirement for a country, INCLUDING the unapproved ones.

    The only read path that passes `include_unapproved=True` — an admin cannot approve content
    the serving filter has already hidden from him. Pending rows sort first: they are the work.
    """
    code = country_code.strip().upper()
    with SessionLocal() as db:
        items = crud.list_requirements(db, code, include_unapproved=True)
        dtos = [_review_dto(i) for i in items]
    order = {"pending": 0, "rejected": 1, "approved": 2}
    dtos.sort(key=lambda d: (order.get(d.reviewStatus, 9), d.purpose, d.title))
    return schemas.AdminRequirementListDTO(
        countryCode=code,
        pendingCount=sum(1 for d in dtos if d.reviewStatus == "pending"),
        items=dtos,
    )


@router.post(
    "/countries/{country_code}/requirements/{requirement_id}/review",
    response_model=schemas.AdminRequirementReviewDTO,
)
def review_country_requirement(
    country_code: str,
    requirement_id: str,
    body: schemas.AdminRequirementReviewRequest,
    user: dict = Depends(require_admin),
):
    """Publish or withhold one requirement. This is the decision the gate exists for.

    Approving is what makes content readable by employees and by the public corridor endpoint;
    until then `crud.list_requirements` filters it out. Stamped and audited, because "who
    published this immigration fact, and when" is the question that matters after the fact.
    """
    status = (body.status or "").strip().lower()
    if status not in _REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_REVIEW_STATUSES)}")

    actor = user.get("id") or user.get("sub") or user.get("email")
    with SessionLocal() as db:
        item = db.get(models.RequirementItem, requirement_id)
        if item is None or (item.country_code or "").upper() != country_code.strip().upper():
            raise HTTPException(status_code=404, detail="Requirement not found for this country")
        before = item.review_status
        item.review_status = status
        item.reviewed_by = str(actor) if actor else None
        item.reviewed_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        dto = _review_dto(item)

    _audit_postgres(
        entity_type="requirement_item",
        entity_id=requirement_id,
        action_type=ACTION_UPDATE,
        actor_id=actor,
        old_value={"review_status": before},
        new_value={"review_status": status, "title": dto.title, "country": dto.id},
    )
    return dto


@router.post("/countries/{country_code}/research/rerun")
def rerun_country(country_code: str, user: dict = Depends(require_admin), opts: Optional[dict] = None):
    run_country_research(country_code, (opts or {}).get("purpose", "employment"), {})
    _audit_postgres(
        entity_type="country_research",
        entity_id=country_code,
        action_type=ACTION_UPDATE,
        actor_id=user.get("id") or user.get("sub"),
        new_value={"event": "research_rerun"},
    )
    return {"jobId": country_code.lower() + "-job"}


def _require_ingest_enabled():
    if os.getenv("ADMIN_INGEST_ENABLED", "true").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Ingest pipeline disabled")


@router.get("/research/candidates")
def list_research_candidates(
    destination_country: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    _require_ingest_enabled()
    with SessionLocal() as db:
        candidates = crud.list_research_candidates(db, destination_country, status)
        return {
            "candidates": [
                {
                    "id": c.id,
                    "destination_country": c.destination_country or c.country_code,
                    "purpose": c.purpose,
                    "url": c.url,
                    "title": c.title,
                    "snippet": c.snippet,
                    "publisher_domain": c.publisher_domain,
                    "status": c.status,
                    "created_at": c.created_at,
                }
                for c in candidates
            ]
        }


@router.post("/research/candidates/{candidate_id}/approve")
def approve_research_candidate(
    candidate_id: str,
    payload: dict,
    user: dict = Depends(require_admin),
):
    _require_ingest_enabled()
    domain_area = (payload or {}).get("domain_area") or "other"
    actor_id = user.get("id")
    with SessionLocal() as session:
        candidate = crud.update_research_candidate_status(session, candidate_id, "approved")
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        job = crud.create_ingest_job(
            session,
            {
                "id": str(uuid.uuid4()),
                "candidate_id": candidate.id,
                "doc_id": None,
                "url": candidate.url,
                "destination_country": candidate.destination_country or candidate.country_code,
                "status": "running",
                "started_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
            },
        )
        results = []
        try:
            result = ingest_url_to_knowledge_doc(candidate.url, candidate.destination_country or candidate.country_code, domain_area)
            crud.update_ingest_job(session, job.id, "done", doc_id=result.get("doc_id"))
            results.append({
                "url": candidate.url,
                "status": result.get("fetch_status"),
                "doc_id": result.get("doc_id"),
                "facts_created": result.get("facts_created"),
                "error": result.get("error"),
            })
        except Exception as exc:
            crud.update_ingest_job(session, job.id, "failed", error=str(exc))
            results.append({
                "url": candidate.url,
                "status": "fetch_failed",
                "error": str(exc),
            })
        succeeded = len([r for r in results if r.get("status") == "fetched"])
        failed = len(results) - succeeded
        _audit_postgres(
            entity_type="research_candidates",
            entity_id=candidate.id,
            action_type=ACTION_UPDATE,
            new_value={
                "status": "approved",
                "domain_area": domain_area,
                "ingest_job_id": job.id,
                "doc_id": (results[0] or {}).get("doc_id"),
                "fetch_status": (results[0] or {}).get("status"),
            },
            actor_id=actor_id,
        )
        return {"attempted": 1, "succeeded": succeeded, "failed": failed, "results": results}


@router.post("/ingest/url")
def ingest_url(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    url = (payload or {}).get("url")
    destination_country = (payload or {}).get("destination_country")
    domain_area = (payload or {}).get("domain_area") or "other"
    if not url or not destination_country:
        raise HTTPException(status_code=400, detail="Missing url or destination_country")
    actor_id = user.get("id")
    with SessionLocal() as session:
        job = crud.create_ingest_job(
            session,
            {
                "id": str(uuid.uuid4()),
                "candidate_id": None,
                "doc_id": None,
                "url": url,
                "destination_country": destination_country,
                "status": "running",
                "started_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
            },
        )
        results = []
        try:
            result = ingest_url_to_knowledge_doc(url, destination_country, domain_area)
            crud.update_ingest_job(session, job.id, "done", doc_id=result.get("doc_id"))
            results.append({
                "url": url,
                "status": result.get("fetch_status"),
                "doc_id": result.get("doc_id"),
                "facts_created": result.get("facts_created"),
                "error": result.get("error"),
            })
        except Exception as exc:
            crud.update_ingest_job(session, job.id, "failed", error=str(exc))
            results.append({
                "url": url,
                "status": "fetch_failed",
                "error": str(exc),
            })
        succeeded = len([r for r in results if r.get("status") == "fetched"])
        failed = len(results) - succeeded
        _audit_postgres(
            entity_type="ingest_jobs",
            entity_id=job.id,
            action_type=ACTION_INSERT,
            new_value={
                "url": url,
                "destination_country": destination_country,
                "domain_area": domain_area,
                "doc_id": (results[0] or {}).get("doc_id"),
                "fetch_status": (results[0] or {}).get("status"),
                "source": "ingest_url",
            },
            actor_id=actor_id,
        )
        return {"attempted": 1, "succeeded": succeeded, "failed": failed, "results": results}


@router.post("/ingest/batch")
def ingest_batch(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    urls = (payload or {}).get("urls") or []
    destination_country = (payload or {}).get("destination_country")
    default_area = (payload or {}).get("domain_area") or "other"
    if not urls or not destination_country:
        raise HTTPException(status_code=400, detail="Missing urls or destination_country")
    actor_id = user.get("id")
    results = []
    for item in urls:
        if isinstance(item, dict):
            url = item.get("url")
            domain_area = item.get("domain_area") or default_area
        else:
            url = item
            domain_area = default_area
        with SessionLocal() as session:
            job = crud.create_ingest_job(
                session,
                {
                    "id": str(uuid.uuid4()),
                    "candidate_id": None,
                    "doc_id": None,
                    "url": url,
                    "destination_country": destination_country,
                    "status": "running",
                    "started_at": datetime.utcnow(),
                    "created_at": datetime.utcnow(),
                },
            )
            item_result: dict
            try:
                result = ingest_url_to_knowledge_doc(url, destination_country, domain_area)
                crud.update_ingest_job(session, job.id, "done", doc_id=result.get("doc_id"))
                item_result = {
                    "url": url,
                    "status": result.get("fetch_status"),
                    "doc_id": result.get("doc_id"),
                    "facts_created": result.get("facts_created"),
                    "error": result.get("error"),
                }
                results.append(item_result)
            except Exception as exc:
                item_result = {"url": url, "status": "fetch_failed", "error": str(exc)}
                crud.update_ingest_job(session, job.id, "failed", error=str(exc))
                results.append(item_result)
            _audit_postgres(
                entity_type="ingest_jobs",
                entity_id=job.id,
                action_type=ACTION_INSERT,
                new_value={
                    "url": url,
                    "destination_country": destination_country,
                    "domain_area": domain_area,
                    "doc_id": item_result.get("doc_id"),
                    "fetch_status": item_result.get("status"),
                    "source": "ingest_batch",
                },
                actor_id=actor_id,
            )
    succeeded = len([r for r in results if r.get("status") == "fetched"])
    failed = len(results) - succeeded
    return {"attempted": len(results), "succeeded": succeeded, "failed": failed, "results": results}


@router.get("/ingest/jobs")
def list_ingest_jobs(status: Optional[str] = None, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    with SessionLocal() as session:
        jobs = crud.list_ingest_jobs(session, status)
        return {
            "jobs": [
                {
                    "id": j.id,
                    "candidate_id": j.candidate_id,
                    "doc_id": j.doc_id,
                    "url": j.url,
                    "destination_country": j.destination_country,
                    "status": j.status,
                    "error": j.error,
                    "started_at": j.started_at,
                    "finished_at": j.finished_at,
                    "created_at": j.created_at,
                }
                for j in jobs
            ]
        }


@router.get("/knowledge/docs")
def list_knowledge_docs(destination_country: Optional[str] = None, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    if not destination_country:
        raise HTTPException(status_code=400, detail="destination_country required")
    docs = db.list_knowledge_docs_by_destination(destination_country)
    fallback = False
    if not docs:
        docs = db.list_all_knowledge_docs()
        fallback = True
    return {
        "fallback": fallback,
        "docs": [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "publisher": d.get("publisher"),
                "source_url": d.get("source_url"),
                "fetch_status": d.get("fetch_status"),
                "last_verified_at": d.get("last_verified_at"),
                "fetched_at": d.get("fetched_at"),
                "content_length": len((d.get("content_excerpt") or d.get("text_content") or "")),
                "excerpt_preview": (d.get("content_excerpt") or d.get("text_content") or "")[:300],
                "content_excerpt": d.get("content_excerpt") or d.get("text_content"),
                "pack_id": d.get("pack_id"),
            }
            for d in docs
        ]
    }


@router.get("/research/health")
def research_health(destination: str, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    info = Database.get_db_info()
    docs_count = db.count_knowledge_docs_by_destination(destination)
    rules_count = db.count_knowledge_rules_by_destination(destination)
    packs_count = db.count_knowledge_packs_by_destination(destination)
    with SessionLocal() as session:
        since = datetime.utcnow() - timedelta(days=1)
        recent_jobs = session.query(models.KnowledgeDocIngestJob).filter(models.KnowledgeDocIngestJob.created_at >= since).all()
        last_job = session.query(models.KnowledgeDocIngestJob).order_by(models.KnowledgeDocIngestJob.created_at.desc()).first()
    return {
        "db_provider": info.get("db_url_scheme"),
        "knowledge_docs": docs_count,
        "knowledge_rules": rules_count,
        "knowledge_packs": packs_count,
        "ingest_jobs_24h": len(recent_jobs),
        "last_job": {
            "status": getattr(last_job, "status", None),
            "error": getattr(last_job, "error", None),
            "url": getattr(last_job, "url", None),
            "created_at": getattr(last_job, "created_at", None),
        } if last_job else None,
    }


@router.get("/requirements/entities")
def list_requirement_entities(
    destination: str,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    _require_ingest_enabled()
    items = db.list_requirement_entities(destination, status)
    return {"entities": items}


@router.get("/requirements/entities/{entity_id}/facts")
def list_requirement_facts(
    entity_id: str,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    _require_ingest_enabled()
    facts = db.list_requirement_facts(entity_id, status)
    return {"facts": facts}


@router.get("/requirements/criteria")
def list_requirement_criteria(
    destination: str,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    _require_ingest_enabled()
    facts = db.list_requirement_facts_by_destination(destination, status)
    return {"facts": facts}


@router.post("/requirements/facts/approve")
def approve_requirement_facts(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    fact_ids = (payload or {}).get("fact_ids") or []
    if not fact_ids:
        raise HTTPException(status_code=400, detail="fact_ids required")
    actor_id = user.get("id") or "admin"
    db.update_requirement_fact_status(fact_ids, "approved", actor_id)
    for fid in fact_ids:
        _audit_postgres(
            entity_type="requirement_facts",
            entity_id=fid,
            action_type=ACTION_UPDATE,
            new_value={"status": "approved"},
            actor_id=actor_id if actor_id != "admin" else None,
        )
    return {"ok": True, "count": len(fact_ids)}


@router.post("/requirements/facts/reject")
def reject_requirement_facts(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    fact_ids = (payload or {}).get("fact_ids") or []
    if not fact_ids:
        raise HTTPException(status_code=400, detail="fact_ids required")
    actor_id = user.get("id") or "admin"
    db.update_requirement_fact_status(fact_ids, "rejected", actor_id)
    for fid in fact_ids:
        _audit_postgres(
            entity_type="requirement_facts",
            entity_id=fid,
            action_type=ACTION_UPDATE,
            new_value={"status": "rejected"},
            actor_id=actor_id if actor_id != "admin" else None,
        )
    return {"ok": True, "count": len(fact_ids)}


# ---------------------------------------------------------------------------
# Policy ingest reconciler — manual orphan cleanup.
# Startup already runs this once; this endpoint lets ops trigger it on demand
# without a restart (useful when LLM extraction hangs and a user is stuck).
# ---------------------------------------------------------------------------
@router.get("/policy-ingest/orphans")
def list_policy_ingest_orphans(
    max_age_seconds: int = 900,
    user: dict = Depends(require_admin),
):
    """Read-only: list policy_documents stuck mid-extraction for > max_age_seconds."""
    from ..services.policy_ingest_reconciler import find_orphaned_policy_documents
    rows = find_orphaned_policy_documents(db, max_age_seconds=max_age_seconds)
    return {"max_age_seconds": max_age_seconds, "count": len(rows), "orphans": rows}


@router.post("/policy-ingest/reconcile")
def reconcile_policy_ingest(
    payload: Optional[dict] = None,
    user: dict = Depends(require_admin),
):
    """
    Mark orphaned policy_documents as failed so affected users can retry by
    re-uploading. Accepts {"max_age_seconds": int}; defaults to 15 minutes.
    """
    from ..services.policy_ingest_reconciler import reconcile_orphaned_policy_ingest_jobs
    max_age = int((payload or {}).get("max_age_seconds") or 900)
    if max_age < 60:
        raise HTTPException(status_code=400, detail="max_age_seconds must be >= 60")
    actor_id = user.get("id")
    summary = reconcile_orphaned_policy_ingest_jobs(
        db,
        max_age_seconds=max_age,
        actor_id=actor_id,
        actor_label="admin_manual",
    )
    for orphan in summary.get("orphans") or []:
        doc_id = orphan.get("id")
        if not doc_id:
            continue
        _audit_postgres(
            entity_type="policy_documents",
            entity_id=doc_id,
            action_type=ACTION_UPDATE,
            old_value={
                "processing_status": orphan.get("previous_processing_status"),
                "assistant_import_status": orphan.get("previous_assistant_import_status"),
            },
            new_value={
                "processing_status": "failed",
                "assistant_import_status": "failed",
                "reason": "admin_manual_reconcile",
                "max_age_seconds": max_age,
            },
            actor_id=actor_id,
        )
    return summary

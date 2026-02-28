from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta
import os
import uuid

from fastapi import APIRouter, Header, HTTPException, Depends

from ..db import SessionLocal
from ...database import db, Database
from .. import crud, schemas, models
from ..services.research import run_country_research
from ..services.official_ingest_service import ingest_url_to_knowledge_doc
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.post("/countries/{country_code}/research/rerun")
def rerun_country(country_code: str, user: dict = Depends(require_admin), opts: Optional[dict] = None):
    run_country_research(country_code, (opts or {}).get("purpose", "employment"), {})
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
        return {"attempted": 1, "succeeded": succeeded, "failed": failed, "results": results}


@router.post("/ingest/url")
def ingest_url(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    url = (payload or {}).get("url")
    destination_country = (payload or {}).get("destination_country")
    domain_area = (payload or {}).get("domain_area") or "other"
    if not url or not destination_country:
        raise HTTPException(status_code=400, detail="Missing url or destination_country")
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
        return {"attempted": 1, "succeeded": succeeded, "failed": failed, "results": results}


@router.post("/ingest/batch")
def ingest_batch(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    urls = (payload or {}).get("urls") or []
    destination_country = (payload or {}).get("destination_country")
    default_area = (payload or {}).get("domain_area") or "other"
    if not urls or not destination_country:
        raise HTTPException(status_code=400, detail="Missing urls or destination_country")
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
                results.append({"url": url, "status": "fetch_failed", "error": str(exc)})
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
    db.update_requirement_fact_status(fact_ids, "approved", user.get("id") or "admin")
    return {"ok": True, "count": len(fact_ids)}


@router.post("/requirements/facts/reject")
def reject_requirement_facts(payload: dict, user: dict = Depends(require_admin)):
    _require_ingest_enabled()
    fact_ids = (payload or {}).get("fact_ids") or []
    if not fact_ids:
        raise HTTPException(status_code=400, detail="fact_ids required")
    db.update_requirement_fact_status(fact_ids, "rejected", user.get("id") or "admin")
    return {"ok": True, "count": len(fact_ids)}

import json
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from . import models


def get_case(db: Session, case_id: str) -> Optional[models.Case]:
    return db.query(models.Case).filter(models.Case.id == case_id).first()


def create_case(db: Session, case_id: str, draft: Dict[str, Any]) -> models.Case:
    case = models.Case(
        id=case_id,
        draft_json=json.dumps(draft),
        status="created",
        flags_json=json.dumps({}),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case(db: Session, case: models.Case, draft: Dict[str, Any], derived: Dict[str, Any], flags: Dict[str, Any]) -> models.Case:
    case.draft_json = json.dumps(draft)
    case.origin_country = derived.get("origin_country")
    case.origin_city = derived.get("origin_city")
    case.dest_country = derived.get("dest_country")
    case.dest_city = derived.get("dest_city")
    case.purpose = derived.get("purpose")
    case.target_move_date = _parse_date(derived.get("target_move_date"))
    case.flags_json = json.dumps(flags)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    return case


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
        # Fallbacks for common UI formats: DD.MM.YYYY or DD/MM/YYYY
        try:
            if len(raw) == 10 and raw[2] in (".", "/") and raw[5] in (".", "/"):
                d1, d2, y = raw[:2], raw[3:5], raw[6:]
                day = int(d1)
                month = int(d2)
                year = int(y)
                # If month looks invalid, swap
                if month > 12 and day <= 12:
                    day, month = month, day
                return date(year, month, day)
        except Exception:
            return None
        return None
    return None


def list_country_profiles(db: Session) -> List[models.CountryProfile]:
    return db.query(models.CountryProfile).all()


def get_country_profile(db: Session, country_code: str) -> Optional[models.CountryProfile]:
    return db.query(models.CountryProfile).filter(models.CountryProfile.country_code == country_code).first()


def upsert_country_profile(db: Session, payload: Dict[str, Any]) -> models.CountryProfile:
    existing = get_country_profile(db, payload["country_code"])
    if existing:
        existing.last_updated_at = payload.get("last_updated_at")
        existing.confidence_score = payload.get("confidence_score")
        existing.notes = payload.get("notes")
        db.commit()
        db.refresh(existing)
        return existing
    record = models.CountryProfile(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_source_record(db: Session, payload: Dict[str, Any]) -> models.SourceRecord:
    existing = db.query(models.SourceRecord).filter(models.SourceRecord.content_hash == payload["content_hash"]).first()
    if existing:
        return existing
    record = models.SourceRecord(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_sources(db: Session, country_code: str) -> List[models.SourceRecord]:
    return db.query(models.SourceRecord).filter(models.SourceRecord.country_code == country_code).all()


def create_requirement_item(db: Session, payload: Dict[str, Any]) -> models.RequirementItem:
    existing = (
        db.query(models.RequirementItem)
        .filter(models.RequirementItem.country_code == payload["country_code"])
        .filter(models.RequirementItem.purpose == payload["purpose"])
        .filter(models.RequirementItem.title == payload["title"])
        .first()
    )
    if existing:
        existing.description = payload["description"]
        existing.severity = payload["severity"]
        existing.owner = payload["owner"]
        existing.required_fields_json = payload["required_fields_json"]
        existing.citations_json = payload["citations_json"]
        existing.last_verified_at = payload["last_verified_at"]
        db.commit()
        db.refresh(existing)
        return existing
    item = models.RequirementItem(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_research_candidate(db: Session, payload: Dict[str, Any]) -> models.ResearchSourceCandidate:
    existing = (
        db.query(models.ResearchSourceCandidate)
        .filter(models.ResearchSourceCandidate.content_hash == payload["content_hash"])
        .first()
    )
    if existing:
        return existing
    record = models.ResearchSourceCandidate(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_research_candidates(
    db: Session,
    destination_country: Optional[str] = None,
    status: Optional[str] = None,
) -> List[models.ResearchSourceCandidate]:
    query = db.query(models.ResearchSourceCandidate)
    if destination_country:
        query = query.filter(
            (models.ResearchSourceCandidate.destination_country == destination_country)
            | (models.ResearchSourceCandidate.country_code == destination_country)
        )
    if status:
        query = query.filter(models.ResearchSourceCandidate.status == status)
    return query.order_by(models.ResearchSourceCandidate.created_at.desc()).all()


def update_research_candidate_status(db: Session, candidate_id: str, status: str) -> Optional[models.ResearchSourceCandidate]:
    candidate = db.query(models.ResearchSourceCandidate).filter(models.ResearchSourceCandidate.id == candidate_id).first()
    if not candidate:
        return None
    candidate.status = status
    db.commit()
    db.refresh(candidate)
    return candidate


def create_ingest_job(db: Session, payload: Dict[str, Any]) -> models.KnowledgeDocIngestJob:
    job = models.KnowledgeDocIngestJob(**payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_ingest_job(
    db: Session,
    job_id: str,
    status: str,
    doc_id: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[models.KnowledgeDocIngestJob]:
    job = db.query(models.KnowledgeDocIngestJob).filter(models.KnowledgeDocIngestJob.id == job_id).first()
    if not job:
        return None
    job.status = status
    if doc_id:
        job.doc_id = doc_id
    job.error = error
    if status in ("running", "done", "failed"):
        job.started_at = job.started_at or datetime.utcnow()
    if status in ("done", "failed"):
        job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def list_ingest_jobs(db: Session, status: Optional[str] = None) -> List[models.KnowledgeDocIngestJob]:
    query = db.query(models.KnowledgeDocIngestJob)
    if status:
        query = query.filter(models.KnowledgeDocIngestJob.status == status)
    return query.order_by(models.KnowledgeDocIngestJob.created_at.desc()).all()


def list_requirements(db: Session, country_code: str, purpose: Optional[str] = None) -> List[models.RequirementItem]:
    query = db.query(models.RequirementItem).filter(models.RequirementItem.country_code == country_code)
    if purpose:
        query = query.filter(models.RequirementItem.purpose == purpose)
    return query.all()


def create_snapshot(db: Session, payload: Dict[str, Any]) -> models.CaseRequirementsSnapshot:
    snapshot = models.CaseRequirementsSnapshot(**payload)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot

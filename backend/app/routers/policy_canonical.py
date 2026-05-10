"""
Canonical policy admin + company-scoped read/query routes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ...database import db
from ...services.policy_canonical_access import (
    ensure_company_scope_for_read,
    ensure_company_scope_for_write,
    resolve_target_company_id,
    resolve_user_company_id,
)
from ...services.policy_canonical_chunking import chunk_canonical_policy_document
from ...services.policy_canonical_extraction import extract_canonical_policy_facts
from ...services.policy_canonical_ingestion import ingest_canonical_policy_document
from ...services.policy_query_answering import answer_company_scoped_policy_query
from ...services.policy_rendering import render_canonical_policy_markdown


def _authenticated_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def _require_hr_or_admin(user: Dict[str, Any] = Depends(_authenticated_user)) -> Dict[str, Any]:
    role = str(user.get("role") or "").upper()
    if role in {"HR", "ADMIN"}:
        return user
    profile = db.get_profile_record(str(user.get("id") or ""))
    if profile and str(profile.get("role") or "").upper() in {"HR", "ADMIN"}:
        return user
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return {**user, "role": "ADMIN"}
    raise HTTPException(status_code=403, detail="HR or admin only")


def _require_policy_reader(user: Dict[str, Any] = Depends(_authenticated_user)) -> Dict[str, Any]:
    role = str(user.get("role") or "").upper()
    if role in {"EMPLOYEE", "HR", "ADMIN"}:
        return user
    profile = db.get_profile_record(str(user.get("id") or ""))
    if profile and str(profile.get("role") or "").upper() in {"EMPLOYEE", "HR", "ADMIN"}:
        return user
    raise HTTPException(status_code=403, detail="Employee, HR, or Admin required")


def _document_or_404(canonical_document_id: str) -> Dict[str, Any]:
    document = db.get_canonical_policy_document(canonical_document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Canonical policy document not found")
    return document


class CanonicalPolicyIngestRequest(BaseModel):
    company_id: Optional[str] = None
    file_path: Optional[str] = None
    source_policy_document_id: Optional[str] = None
    source_uri: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    default_currency: Optional[str] = None
    assignment_types: List[str] = Field(default_factory=list)


class CanonicalPolicyUpdateRequest(BaseModel):
    title: Optional[str] = None
    version_label: Optional[str] = None
    default_currency: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CanonicalPolicyQueryRequest(BaseModel):
    message: str
    canonical_policy_document_id: Optional[str] = None


admin_router = APIRouter(prefix="/policy-canonical", tags=["policy-canonical-admin"])
read_router = APIRouter(prefix="/policy-canonical", tags=["policy-canonical"])


@admin_router.post("/ingest")
def ingest_policy(
    payload: CanonicalPolicyIngestRequest,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    target_company_id = resolve_target_company_id(user, db, explicit_company_id=payload.company_id)
    try:
        return ingest_canonical_policy_document(
            db,
            company_id=target_company_id,
            file_path=payload.file_path,
            source_policy_document_id=payload.source_policy_document_id,
            source_uri=payload.source_uri,
            filename=payload.filename,
            mime_type=payload.mime_type,
            default_currency=payload.default_currency,
            assignment_types=payload.assignment_types,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/from-existing/{source_policy_document_id}")
def ingest_existing_policy(
    source_policy_document_id: str,
    use_fallback: bool = Query(False),
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    source_doc = db.get_policy_document(source_policy_document_id)
    if not source_doc:
        raise HTTPException(status_code=404, detail="Source policy document not found")
    ensure_company_scope_for_write(user, str(source_doc.get("company_id") or ""), db)
    try:
        document = ingest_canonical_policy_document(
            db,
            company_id=str(source_doc.get("company_id") or ""),
            source_policy_document_id=source_policy_document_id,
        )
        chunk_canonical_policy_document(db, str(document["id"]))
        extraction = extract_canonical_policy_facts(
            db,
            str(document["id"]),
            use_fallback=use_fallback,
        )
        return {"document": document, "extraction": extraction}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.patch("/documents/{canonical_document_id}")
def update_document(
    canonical_document_id: str,
    payload: CanonicalPolicyUpdateRequest,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    ensure_company_scope_for_write(user, str(document.get("company_id") or ""), db)
    db.update_canonical_policy_document(
        canonical_document_id,
        title=payload.title,
        version_label=payload.version_label,
        default_currency=payload.default_currency,
        metadata_json=payload.metadata_json,
    )
    return db.get_canonical_policy_document(canonical_document_id)


@admin_router.delete("/documents/{canonical_document_id}")
def delete_document(
    canonical_document_id: str,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    ensure_company_scope_for_write(user, str(document.get("company_id") or ""), db)
    db.delete_canonical_policy_artifacts(canonical_document_id)
    with db.engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(text("DELETE FROM canonical_policy_documents WHERE id = :id"), {"id": canonical_document_id})
    return {"ok": True, "deleted_document_id": canonical_document_id}


@admin_router.post("/{canonical_document_id}/chunk")
def chunk_policy(
    canonical_document_id: str,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    ensure_company_scope_for_write(user, str(document.get("company_id") or ""), db)
    try:
        chunks = chunk_canonical_policy_document(db, canonical_document_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"document_id": canonical_document_id, "chunks_count": len(chunks), "chunks": chunks}


@admin_router.post("/{canonical_document_id}/extract")
def extract_policy(
    canonical_document_id: str,
    use_fallback: bool = Query(False),
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    ensure_company_scope_for_write(user, str(document.get("company_id") or ""), db)
    try:
        return extract_canonical_policy_facts(db, canonical_document_id, use_fallback=use_fallback)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get("/documents")
def list_documents(
    company_id: Optional[str] = Query(None),
    extraction_status: Optional[str] = Query(None),
    source_policy_document_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    target_company_id = resolve_target_company_id(user, db, explicit_company_id=company_id)
    return db.list_canonical_policy_documents(
        company_id=target_company_id,
        source_policy_document_id=source_policy_document_id,
        extraction_status=extraction_status,
    )


@admin_router.get("/documents/{canonical_document_id}")
def get_document(
    canonical_document_id: str,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    ensure_company_scope_for_read(user, str(document.get("company_id") or ""), db)
    return document


@admin_router.get("/documents/{canonical_document_id}/chunks")
def list_chunks(
    canonical_document_id: str,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    ensure_company_scope_for_read(user, str(document.get("company_id") or ""), db)
    return db.list_canonical_policy_document_chunks(canonical_document_id, company_id=str(document.get("company_id") or ""))


@admin_router.get("/documents/{canonical_document_id}/facts")
def list_facts(
    canonical_document_id: str,
    phase: Optional[str] = Query(None),
    benefit_category: Optional[str] = Query(None),
    value_type: Optional[str] = Query(None),
    provider_entity: Optional[str] = Query(None),
    assignment_type: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    company_id = ensure_company_scope_for_read(user, str(document.get("company_id") or ""), db)
    return db.list_canonical_policy_facts(
        canonical_document_id,
        company_id=company_id,
        phase=phase,
        benefit_category=benefit_category,
        value_type=value_type,
        provider_entity=provider_entity,
        assignment_type=assignment_type,
    )


@admin_router.get("/documents/{canonical_document_id}/validation-errors")
def list_validation_errors(
    canonical_document_id: str,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    company_id = ensure_company_scope_for_read(user, str(document.get("company_id") or ""), db)
    return db.list_canonical_policy_validation_errors(canonical_document_id, company_id=company_id)


@admin_router.get("/documents/{canonical_document_id}/audit")
def get_audit_summary(
    canonical_document_id: str,
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    document = _document_or_404(canonical_document_id)
    company_id = ensure_company_scope_for_read(user, str(document.get("company_id") or ""), db)
    return db.get_canonical_policy_audit_summary(canonical_document_id, company_id=company_id)


@read_router.get("/render/current")
def render_current_company_policy(
    user: Dict[str, Any] = Depends(_require_policy_reader),
):
    company_id = resolve_user_company_id(user, db)
    document = db.get_active_canonical_policy_document_for_company(company_id)
    if not document:
        raise HTTPException(status_code=404, detail="No canonical policy available for this company")
    facts = db.list_canonical_policy_facts(str(document["id"]), company_id=company_id)
    markdown = render_canonical_policy_markdown(document, facts)
    return {
        "company_id": company_id,
        "canonical_policy_document_id": str(document["id"]),
        "title": str(document.get("title") or document.get("filename") or document.get("id")),
        "markdown": markdown,
    }


@read_router.post("/query")
def query_current_company_policy(
    payload: CanonicalPolicyQueryRequest,
    user: Dict[str, Any] = Depends(_require_policy_reader),
):
    company_id = resolve_user_company_id(user, db)
    if payload.canonical_policy_document_id:
        document = _document_or_404(payload.canonical_policy_document_id)
        ensure_company_scope_for_read(user, str(document.get("company_id") or ""), db)
    try:
        return answer_company_scoped_policy_query(
            db,
            company_id=company_id,
            user_id=str(user.get("id") or ""),
            user_role=str(user.get("role") or ""),
            query=payload.message,
            canonical_policy_document_id=payload.canonical_policy_document_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@read_router.get("/query-audit")
def list_query_audit(
    limit: int = Query(100, le=500),
    user: Dict[str, Any] = Depends(_require_policy_reader),
):
    company_id = resolve_user_company_id(user, db)
    return db.list_canonical_policy_query_audit_logs(company_id=company_id, limit=limit)

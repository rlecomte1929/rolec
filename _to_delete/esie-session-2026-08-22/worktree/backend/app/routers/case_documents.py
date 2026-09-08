"""
Case-scoped document upload + status endpoints (DOCFLOW P1).

Generic upload→satisfy loop over the roadmap ``required_inputs`` document-key vocabulary
(passport_copy, employment_letter, spouse_passport_copy, income_proof, …). Reuses the
existing storage + case_evidence → case_documents pipeline — no new table, migration, or
bucket.

- POST /api/cases/{case_id}/documents  — multipart upload for a single document_key.
- GET  /api/cases/{case_id}/documents  — the case's required documents as a keyed list.

File validation + storage mirror ``cases_write.upload_form_document`` (20 MiB cap, the
case-documents bucket MIME allowlist, service-role Supabase upload).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from ..auth_deps import get_current_user
from ..services.case_service import _assert_case_access
from ..services.rce_document_ingest import bridge_case_document_to_rce
from ..services.relocation_plan_view_service import invalidate_relocation_plan_cache
from ..services.passport_case_document_sync_service import (
    ensure_case_document_for_key,
    map_case_evidence_status_to_document_status,
)
from ...database import db as main_db
from ...relocation_plan_service import build_phased_plan_from_milestones

# Reuse the exact validation + storage primitives from the per-form upload handler so
# the two upload paths stay byte-for-byte consistent (same bucket, cap, MIME allowlist).
from .cases_write import (
    _FORM_DOC_ALLOWED_MIME,  # noqa: F401 — kept for parity / documentation of the allowlist
    _FORM_DOC_BUCKET,
    _FORM_DOC_MAX_BYTES,
    _resolve_doc_mime,
    _safe_filename,
)

from sqlalchemy import text as _sql_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["case-documents"])


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------
def _resolve_assignment(case_id: str) -> Dict[str, Any]:
    """case_id (cases / relocation_cases / assignment id) → assignment row, or 404."""
    assignment = main_db.get_assignment_by_case_id(case_id) or main_db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Case not found")
    return assignment


def _effective_case_id(assignment: Dict[str, Any], fallback: str) -> str:
    cc = (assignment.get("canonical_case_id") or "").strip()
    if cc:
        return cc
    return (assignment.get("case_id") or "").strip() or fallback


def _evidence_case_id(assignment: Dict[str, Any], fallback: str) -> str:
    """case_evidence.case_id must reference the wizard/relocation case row."""
    return (assignment.get("case_id") or "").strip() or fallback


def _parse_doc_metadata(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _case_documents_by_key(mobility_case_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Map document_key → {status, file_url, uploaded_at} for a mobility case."""
    out: Dict[str, Dict[str, Any]] = {}
    if not mobility_case_id:
        return out
    try:
        with main_db.engine.connect() as conn:
            rows = conn.execute(
                _sql_text(
                    "SELECT document_key, document_status, metadata, updated_at, created_at "
                    "FROM case_documents WHERE case_id = :cid"
                ),
                {"cid": mobility_case_id},
            ).mappings().all()
    except Exception as exc:  # schema missing / transient — treat as no docs
        logger.debug("case_documents read failed for %s: %s", mobility_case_id, exc)
        return out
    for row in rows:
        dk = str(row.get("document_key") or "").strip().lower()
        if not dk:
            continue
        meta = _parse_doc_metadata(row.get("metadata"))
        out[dk] = {
            "status": str(row.get("document_status") or "").strip() or None,
            "file_url": meta.get("file_url"),
            "uploaded_at": row.get("updated_at") or row.get("created_at"),
        }
    return out


def _document_keys_for_case(eff_case_id: str) -> List[Dict[str, str]]:
    """Document-type required_inputs for the case, sourced from the relocation plan
    view's task computation. Deduped by key, first label/order wins."""
    try:
        milestones = main_db.list_case_milestones(eff_case_id)
    except Exception as exc:
        logger.debug("list_case_milestones failed for %s: %s", eff_case_id, exc)
        milestones = []
    blocks = build_phased_plan_from_milestones(milestones)
    seen: set[str] = set()
    out: List[Dict[str, str]] = []
    for block in blocks:
        for task in block.tasks:
            for ri in getattr(task, "required_inputs", ()) or ():
                if not isinstance(ri, dict):
                    continue
                if str(ri.get("type") or "").strip().lower() != "document":
                    continue
                key = str(ri.get("key") or "").strip()
                if not key or key.lower() in seen:
                    continue
                seen.add(key.lower())
                out.append({"key": key, "label": str(ri.get("label") or key)})
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/{case_id}/documents")
async def upload_case_document(
    case_id: str,
    req: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_key: str = Form(...),
    requirement_id: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Upload a file for a single document_key, satisfying its roadmap task.

    Stores the file in the private ``case-documents`` bucket, records a case_evidence
    row (evidence_type=document_key), then syncs the derived case_documents index,
    then bridges the upload into the rce case engine so extraction can run.
    """
    _assert_case_access(user, case_id)

    dk = (document_key or "").strip()
    if not dk:
        raise HTTPException(status_code=422, detail="document_key is required")

    assignment = _resolve_assignment(case_id)
    assignment_id = str(assignment.get("id"))
    request_id = getattr(req.state, "request_id", None)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(contents) > _FORM_DOC_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB limit")

    content_type = _resolve_doc_mime(file.content_type, file.filename)
    if content_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF or image (PNG, JPEG, WebP, TIFF).",
        )

    file_name = _safe_filename(file.filename or "upload")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    storage_path = f"case-docs/{case_id}/{dk}/{ts}_{file_name}"

    # Upload to Supabase Storage (service-role client).
    try:
        from ..services.supabase_client import get_supabase_admin_client  # lazy import

        sb = get_supabase_admin_client()
        sb.storage.from_(_FORM_DOC_BUCKET).upload(
            storage_path,
            contents,
            {"content-type": content_type, "upsert": "true"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("case_doc upload: storage error case_id=%s key=%s", case_id, dk)
        if "mime" in str(exc).lower():
            raise HTTPException(
                status_code=415,
                detail="Unsupported file type. Upload a PDF or image (PNG, JPEG, WebP, TIFF).",
            )
        raise HTTPException(status_code=502, detail="Storage unavailable — upload failed")

    # Record case_evidence (source of truth), then sync the derived case_documents index.
    try:
        main_db.insert_case_evidence(
            case_id=_evidence_case_id(assignment, case_id),
            assignment_id=assignment_id,
            participant_id=None,
            requirement_id=(requirement_id or None),
            evidence_type=dk,
            file_url=storage_path,
            metadata={
                "uploaded_by": user.get("id") or user.get("sub"),
                "file_name": file_name,
                "content_type": content_type,
                "size_bytes": len(contents),
            },
            status="submitted",
            request_id=request_id,
        )
    except Exception:
        logger.exception("case_doc upload: case_evidence insert failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to record uploaded document")

    # Best-effort mobility-graph linkage so the sync can resolve the mobility case.
    try:
        from ..services.assignment_mobility_link_service import (
            ensure_mobility_case_link_for_assignment,
        )
        from ..services.employee_case_person_service import (
            ensure_employee_case_person_for_assignment,
        )

        ensure_mobility_case_link_for_assignment(main_db, assignment_id, request_id=request_id)
        ensure_employee_case_person_for_assignment(main_db, assignment_id, request_id=request_id)
    except Exception as exc:
        logger.warning("case_doc upload: mobility graph linkage failed: %s", exc)

    ensure_case_document_for_key(main_db, assignment_id, dk, request_id=request_id)

    eff_case_id = _effective_case_id(assignment, case_id)
    invalidate_relocation_plan_cache(case_id=eff_case_id, assignment_id=assignment_id)

    # [AIQ-1780] Bridge into the rce case engine so the extraction agents can run.
    #
    # This is the upload path users actually reach (roadmap task CTA →
    # /employee/case/:caseId/documents). Until now only the *immigration* upload
    # endpoint bridged, and its UI has no inbound nav links — so rce.documents sat at
    # 0 forever and every registered extraction agent was inert.
    #
    # The case_id argument is the entire fix. It MUST be the canonical/relocation case
    # id, which is what rce.cases is keyed on — NOT `mobility_case_id` resolved two
    # lines below for the case_documents index. mobility_cases ids are minted per
    # assignment and have no FK path to public.cases, so passing one would make
    # _case_exists() fail for every upload, forever, silently.
    #
    # Guarded at the call site as well as inside the bridge. By this point the file is
    # in storage and case_evidence is committed, so letting anything here raise would
    # 500 an upload that actually succeeded — the user retries and duplicates it.
    # Extraction is best-effort; the document is not. Same shape as the mobility-graph
    # linkage block above. Mirrors immigration_documents.py's E-PIPE-1/E-PIPE-7 pairing.
    try:
        rce_document_id = bridge_case_document_to_rce(
            case_id=eff_case_id,
            content=contents,
            mime_type=content_type,
            storage_uri=storage_path,
            original_filename=file_name,
            uploaded_by=user.get("id") or user.get("sub"),
        )
        if rce_document_id:
            from ..services.rce_pipeline_worker import process_rce_document  # lazy: heavy deps

            background_tasks.add_task(process_rce_document, rce_document_id)
    except Exception as exc:  # noqa: BLE001 — extraction must never cost a document
        logger.warning(
            "case_doc upload: rce bridge failed case_id=%s key=%s: %s", eff_case_id, dk, exc
        )

    mobility_case_id = main_db.get_mobility_case_id_for_assignment(assignment_id, request_id=request_id)
    docs = _case_documents_by_key(mobility_case_id)
    doc = docs.get(dk.lower())
    document_status = (doc or {}).get("status") or map_case_evidence_status_to_document_status("submitted")

    return {
        "document_key": dk,
        "document_status": document_status,
        "file_url": storage_path,
    }


@router.get("/{case_id}/documents")
def list_case_documents(
    case_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List the case's required documents as a keyed list.

    Required document keys+labels come from the relocation plan view's document-type
    ``required_inputs``; each is LEFT JOINed against case_documents for its current
    status/file. Un-uploaded items report status 'required'.
    """
    _assert_case_access(user, case_id)

    assignment = _resolve_assignment(case_id)
    assignment_id = str(assignment.get("id"))
    eff_case_id = _effective_case_id(assignment, case_id)
    request_id = getattr(req.state, "request_id", None)

    mobility_case_id = main_db.get_mobility_case_id_for_assignment(assignment_id, request_id=request_id)
    docs = _case_documents_by_key(mobility_case_id)

    out: List[Dict[str, Any]] = []
    for item in _document_keys_for_case(eff_case_id):
        key = item["key"]
        doc = docs.get(key.lower())
        out.append(
            {
                "key": key,
                "label": item["label"],
                "status": (doc or {}).get("status") or "required",
                "uploaded_at": (doc or {}).get("uploaded_at"),
                "file_url": (doc or {}).get("file_url"),
            }
        )
    return out

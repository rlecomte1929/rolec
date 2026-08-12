"""
[P4-3] Ad-hoc "Add document" — forms outside the template registry.

Lets HR attach a custom document to a case that has no FieldDefinition-backed
form_template. The row lives in the existing public.case_forms table with
form_template_id = NULL and is_adhoc = TRUE, so it shows up in the dossier list
(rendered with a "Custom" badge) and can be added to a DossierPackage.

Endpoints (registered in BOTH backend/app/main.py and backend/main.py):
  POST /api/cases/{case_id}/forms/adhoc            — create an ad-hoc form
  POST /api/cases/{case_id}/forms/{form_id}/replace-pdf — swap the uploaded PDF
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
import uuid
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text as _sql_text

from ..auth_deps import get_current_user
from ..services.case_service import _assert_case_access, _pg_table, _sql_now
from .cases import CaseFormSummary, _fetch_single_form_summary
from ...database import db as main_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["case-forms-adhoc"])

# Ad-hoc forms start in_progress — there are no fields to fill, so HR drives the
# status manually via the existing "Change status" dropdown.
_ADHOC_DEFAULT_STATUS = "in_progress"

# Supabase Storage bucket shared with the rest of the dossier PDFs.
_BUCKET = "case-forms"
_ALLOWED_PDF_TYPES = {"application/pdf", "application/octet-stream"}

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _actor_uuid(user: Dict[str, Any]) -> Optional[str]:
    """``case_form_events.actor_id`` is uuid-typed. Legacy/seed sessions carry a
    non-UUID text id (e.g. ``seed-emp-testingapril``); inserting that fails the
    uuid cast and — inside the form-creation transaction — poisons it, silently
    rolling back the ad-hoc form (surfaced as a misleading 404). Return the
    caller's canonical Supabase uuid (``auth_uuid``), else their id only when it
    is uuid-shaped, else ``None`` (the column is nullable)."""
    for v in (user.get("auth_uuid"), user.get("id")):
        s = str(v) if v else ""
        if _UUID_RE.match(s):
            return s
    return None


async def _read_pdf(upload: UploadFile) -> Tuple[Optional[bytes], Optional[str]]:
    """Validate and read an uploaded PDF. Returns (bytes, content_type)."""
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in _ALLOWED_PDF_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF uploads are accepted")
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
    return data, (content_type or "application/pdf")


def _store_adhoc_pdf(form_id: str, pdf_bytes: bytes, content_type: str) -> Optional[str]:
    """
    Upload an ad-hoc form PDF to Supabase Storage and return a 7-day signed URL.
    Returns None when storage is unavailable (dev mode) — the form is still created.
    """
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = f"adhoc-forms/{form_id}/{ts}.pdf"
        sb.storage.from_(_BUCKET).upload(
            path,
            pdf_bytes,
            {"content-type": content_type or "application/pdf", "upsert": "true"},
        )
        signed = sb.storage.from_(_BUCKET).create_signed_url(path, 60 * 60 * 24 * 7)
        return signed.get("signedURL") or signed.get("signedUrl")
    except Exception:
        logger.exception("adhoc: PDF storage failed form_id=%s", form_id)
        return None


@router.post(
    "/{case_id}/forms/adhoc",
    response_model=CaseFormSummary,
    status_code=201,
)
async def create_adhoc_form(
    case_id: str,
    name: str = Form(...),
    authority: Optional[str] = Form(None),
    person_id: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> CaseFormSummary:
    """Create an ad-hoc (template-less) CaseForm and return it as a CaseFormSummary."""
    # Key on the RESOLVED id. `cases_read.list_case_forms` resolves before querying, so an
    # ad-hoc form stored under an assignment id was created successfully and then never
    # appeared in the Dossier. The sibling `replace_adhoc_pdf` below was fixed for exactly
    # this by AIQ-1776; this one was missed.
    resolved_case_id = _assert_case_access(user, case_id)

    clean_name = (name or "").strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Document name is required")

    pdf_bytes: Optional[bytes] = None
    pdf_type: Optional[str] = None
    if file is not None:
        pdf_bytes, pdf_type = await _read_pdf(file)

    form_id = str(uuid.uuid4())
    original_file_url: Optional[str] = None
    if pdf_bytes is not None:
        original_file_url = _store_adhoc_pdf(form_id, pdf_bytes, pdf_type or "application/pdf")

    try:
        with main_db.engine.begin() as conn:
            conn.execute(
                _sql_text(
                    f"INSERT INTO {_pg_table('case_forms')} "
                    "(id, case_id, form_template_id, person_id, status, completion_pct, "
                    " is_adhoc, adhoc_name, adhoc_authority, notes, deadline, original_file_url) "
                    "VALUES "
                    "(:id, :case_id, NULL, :person_id, :status, 0, "
                    " :is_adhoc, :adhoc_name, :adhoc_authority, :notes, :deadline, :original_file_url)"
                ),
                {
                    "id": form_id,
                    "case_id": resolved_case_id,
                    "person_id": (person_id or None),
                    "status": _ADHOC_DEFAULT_STATUS,
                    "is_adhoc": True,
                    "adhoc_name": clean_name,
                    "adhoc_authority": ((authority or "").strip() or None),
                    "notes": ((notes or "").strip() or None),
                    "deadline": (deadline or None),
                    "original_file_url": original_file_url,
                },
            )
            # fix: [ADHOC-FORM] isolate the audit-event insert in a SAVEPOINT.
            # case_form_events may be absent in legacy schemas, and a failed
            # insert (e.g. a non-uuid actor_id) would otherwise poison the outer
            # transaction and silently roll back the form → misleading 404.
            try:
                with conn.begin_nested():
                    conn.execute(
                        _sql_text(
                            f"INSERT INTO {_pg_table('case_form_events')} "
                            "(case_form_id, event_type, actor_id, note) "
                            "VALUES (:form_id, 'adhoc_created', :actor_id, :note)"
                        ),
                        {"form_id": form_id, "actor_id": _actor_uuid(user), "note": clean_name},
                    )
            except Exception:
                logger.warning(
                    "adhoc: case_form_events insert skipped (savepoint rollback) form_id=%s",
                    form_id,
                )
    except HTTPException:
        raise
    except Exception:
        logger.exception("adhoc: insert failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to create ad-hoc document")

    # MUST use the resolved id too: _fetch_single_form_summary ends
    # `WHERE cf.id = :form_id AND cf.case_id = :case_id`, so re-fetching with the raw param
    # after inserting the resolved one would 404 the row we just created. (Before this fix
    # both sides were raw, so they matched each other while being invisible to every other
    # reader — fixing the write alone would have converted that into a 404-after-write.)
    return _fetch_single_form_summary(resolved_case_id, form_id)


@router.post(
    "/{case_id}/forms/{form_id}/replace-pdf",
    response_model=CaseFormSummary,
)
async def replace_adhoc_pdf(
    case_id: str,
    form_id: str,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> CaseFormSummary:
    """Replace the uploaded PDF on an ad-hoc form."""
    # [AIQ-1776] case_forms.case_id holds the canonical case id; this route's
    # {case_id} may be an assignment id. Key both statements on the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)

    with main_db.engine.connect() as conn:
        row = conn.execute(
            _sql_text(
                f"SELECT is_adhoc FROM {_pg_table('case_forms')} "
                "WHERE id = :form_id AND case_id = :case_id"
            ),
            {"form_id": form_id, "case_id": resolved_case_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Form not found")
    if not bool(row.get("is_adhoc")):
        raise HTTPException(status_code=409, detail="Replace PDF is only available for ad-hoc documents")

    pdf_bytes, pdf_type = await _read_pdf(file)
    original_file_url = _store_adhoc_pdf(form_id, pdf_bytes, pdf_type or "application/pdf")

    try:
        with main_db.engine.begin() as conn:
            conn.execute(
                _sql_text(
                    f"UPDATE {_pg_table('case_forms')} "
                    f"SET original_file_url=:url, updated_at={_sql_now()} "
                    "WHERE id=:form_id AND case_id=:case_id"
                ),
                {"url": original_file_url, "form_id": form_id, "case_id": resolved_case_id},
            )
            # fix: [ADHOC-FORM] SAVEPOINT-isolate the audit-event insert so a
            # non-uuid actor_id (legacy sessions) can't poison the outer tx.
            try:
                with conn.begin_nested():
                    conn.execute(
                        _sql_text(
                            f"INSERT INTO {_pg_table('case_form_events')} "
                            "(case_form_id, event_type, actor_id) "
                            "VALUES (:form_id, 'adhoc_pdf_replaced', :actor_id)"
                        ),
                        {"form_id": form_id, "actor_id": _actor_uuid(user)},
                    )
            except Exception:
                logger.warning(
                    "adhoc: replace-pdf event insert skipped (savepoint rollback) form_id=%s",
                    form_id,
                )
    except Exception:
        logger.exception("adhoc: replace-pdf failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to replace PDF")

    return _fetch_single_form_summary(case_id, form_id)

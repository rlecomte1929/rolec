"""
[P2-4] CaseForm — original blank-template PDF endpoint.

GET /api/cases/{case_id}/forms/{form_id}/original

Returns a 1-hour Supabase Storage signed URL for the blank PDF behind a
CaseForm. The OriginalPdfDrawer (frontend) opens this URL in an iframe and
exposes a "Download original" link.

Why a standalone router file (not added to cases.py)?
  cases.py is a large file currently being incrementally refactored. Keeping
  the P2-4 endpoint self-contained lets us ship it without entangling
  in-flight changes to the dossier handlers.

Storage layout
  - Bucket:   `form-templates` (migration 20260521040000, private)
  - Path key: `form_templates.original_pdf_url` stores the bucket-relative
              path (e.g. 'UTL-2011/1.0.0.pdf'). Legacy rows may hold a full
              URL; we strip the `/form-templates/` prefix before signing.

Empty-state contract
  When a template hasn't been associated with a PDF yet (the common case
  for the Norway seed templates from P1-4), we return HTTP 200 with
  `signed_url = null` and `expires_in = 0`. The drawer renders an empty
  state instead of treating that as an error. This keeps the UI from
  flashing a transient error banner for an expected-empty case.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ..services.case_service import _assert_case_access
from ...database import db


router = APIRouter(prefix="/api/cases", tags=["case-form-pdf"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect helper — same pattern as trigger_engine.py / prefill_engine.py
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


# ---------------------------------------------------------------------------
# Access check
# ---------------------------------------------------------------------------
# [AIQ-1776] This module used to define its OWN _assert_case_access, described in
# a comment as mirroring cases.py. It had drifted from the canonical helper in
# three ways that mattered:
#   1. it queried public.cases ONLY, with no case_assignments resolution, so an
#      assignment id — one of the three forms every other case-scoped route
#      accepts — 404'd here instead of resolving;
#   2. it raised 500 on a DB error, violating the B24-REGRESSION fail-safe that
#      requires lookup failures to degrade to 404;
#   3. it compared against the token's user["company_id"] rather than looking the
#      company up in profiles.
# Duplicating an auth boundary means it drifts. There is now one implementation,
# imported above from ..services.case_service.


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class OriginalPdfResponse(BaseModel):
    signed_url: Optional[str]
    file_name: str
    template_code: str
    template_name: str
    version: str
    expires_in: int  # seconds; 0 when signed_url is None


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

@router.get(
    "/{case_id}/forms/{form_id}/original",
    response_model=OriginalPdfResponse,
)
def get_form_original_pdf(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> OriginalPdfResponse:
    """Return a 1-hour signed Supabase Storage URL for the blank template PDF."""
    # [AIQ-1776] case_forms.case_id holds the CANONICAL case id, while this route's
    # {case_id} may be an assignment id. Key the query on the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)

    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT ft.code, ft.name, ft.version, ft.original_pdf_url
                    FROM {_t('case_forms')} cf
                    JOIN {_t('form_templates')} ft
                      ON ft.id = cf.form_template_id
                    WHERE cf.id = :form_id AND cf.case_id = :case_id
                    """
                ),
                {"form_id": form_id, "case_id": resolved_case_id},
            ).mappings().first()
    except Exception:
        logger.exception("forms.original: query failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to load form template")

    if not row:
        raise HTTPException(status_code=404, detail="Form not found")

    code = str(row.get("code") or "")
    name = str(row.get("name") or "")
    version = str(row.get("version") or "")
    storage_path = row.get("original_pdf_url")

    # Empty-state: template has no PDF attached → 200 + signed_url=None.
    if not storage_path:
        return OriginalPdfResponse(
            signed_url=None,
            file_name=f"{code or 'form'}.pdf",
            template_code=code,
            template_name=name,
            version=version,
            expires_in=0,
        )

    # Tolerate legacy data where the column holds a full Storage URL rather
    # than a bucket-relative key. We sign by key, not by URL.
    path = str(storage_path)
    bucket_prefix_marker = "/form-templates/"
    if bucket_prefix_marker in path:
        path = path.split(bucket_prefix_marker, 1)[1]

    expires_in = 60 * 60  # 1 hour
    signed_url: Optional[str] = None
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        signed = sb.storage.from_("form-templates").create_signed_url(path, expires_in)
        signed_url = signed.get("signedURL") or signed.get("signedUrl")
    except Exception as exc:
        # Dev / SQLite mode without Supabase configured — surface a 200 with
        # signed_url=None so the drawer renders the empty-state rather than
        # showing a hard error.
        logger.warning(
            "forms.original: storage unavailable form_id=%s err=%s", form_id, exc
        )
        signed_url = None

    return OriginalPdfResponse(
        signed_url=signed_url,
        file_name=f"{code or 'form'}-{version or 'latest'}.pdf",
        template_code=code,
        template_name=name,
        version=version,
        expires_in=expires_in if signed_url else 0,
    )

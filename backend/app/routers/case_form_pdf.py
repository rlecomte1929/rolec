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
# Access check — mirrors cases.py::_assert_case_access logic
# ---------------------------------------------------------------------------

def _assert_case_access(user: Dict[str, Any], case_id: str) -> None:
    """Ensure the current user can read this case.

    Admin users always pass. Otherwise we require either:
      - the user is the case's employee (cases.employee_id matches user.id), or
      - the user is the HR owner of the case (cases.hr_owner_id matches), or
      - the user belongs to the same company as the case.

    Raises HTTPException(403) on denial, HTTPException(404) if the case
    doesn't exist.
    """
    if user.get("is_admin") or user.get("role") in ("ADMIN", "admin"):
        return

    user_id = user.get("id") or user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id")

    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT employee_id, hr_owner_id, company_id "
                    f"FROM {_t('cases')} WHERE id = :id"
                ),
                {"id": case_id},
            ).mappings().first()
    except Exception:
        logger.exception("case access query failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to verify access")

    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    if str(row.get("employee_id") or "") == str(user_id):
        return
    if str(row.get("hr_owner_id") or "") == str(user_id):
        return

    case_company_id = row.get("company_id")
    user_company_id = user.get("company_id")
    if case_company_id and user_company_id and str(case_company_id) == str(user_company_id):
        return

    raise HTTPException(status_code=403, detail="Forbidden")


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
    _assert_case_access(user, case_id)

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
                {"form_id": form_id, "case_id": case_id},
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
        from ...services.supabase_client import get_supabase_admin_client
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

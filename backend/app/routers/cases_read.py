"""
cases_read.py — Read-only (GET) handlers extracted from cases.py
(AUDIT-B9-cases-3 / AIQ-451).

Houses the 20 GET handlers extracted from backend/app/routers/cases.py as part
of the cases decomposition (parent: AUDIT-B9-cases, task brief in
backend/docs/cases-router-inventory.md §3, §4, §5).

Buckets covered:
  - Employee reads          (§3): `list_employee_cases`
  - HR reads                (§4): currently empty (no HR-only GETs live here)
  - Shared reads (emp + HR) (§5): the remaining 19 handlers — case detail,
    requirements, roadmap, forms, dossiers, budget summary, messages,
    vendors, budget lines.

All handlers are copied verbatim from cases.py. The router prefix and tag
match cases.py exactly so behaviour is identical when this module is wired up.

DORMANT: this router is **not** wired into backend/app/main.py. Canonical
registration still happens via cases.py until AUDIT-B9-cases-6 (AIQ-454)
retires the original handlers.
"""
from __future__ import annotations

import io
import json
import logging
import datetime as _dt
import zipfile as _zipfile
from typing import Any, Dict, List, Optional

import requests as _requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text as _sql_text

from .. import crud, schemas
from ..auth_deps import get_current_user, require_case_access
from ..db import SessionLocal
from ..services.requirements_builder import compute_case_requirements
from ..services.roadmap_builder import derive_roadmap
from ..services.roadmap_projection import project_tracks, track_label_for_form
from ..services.feature_flags import is_flag_enabled_for, LIVE_EEA_ROADMAP_FLAG
from ..services.roadmap_confidence_gate import is_ai_roadmap, gate_roadmap_for_case
from ..services.roadmap_staleness import annotate_staleness
from ..services.case_roadmap_profile import generate_ai_roadmap_for_case
from ..services.case_service import (
    _assert_case_access,
    _case_dto,
    _dossier_is_stale,
    _pg_conn,
    _pg_table,
    _sql_now,
)
from ...database import db as main_db

router = APIRouter(prefix="/api/cases", tags=["cases"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# [P1-6] Roadmap tracks V2 — response models
# ─────────────────────────────────────────────────────────────────────────────

class RoadmapDocChip(BaseModel):
    doc_count: int
    worst_doc_status: Optional[str] = None


class RoadmapStepV2(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    owner: str
    due_date: Optional[str] = None
    sort_order: int
    ai_suggestion: Optional[str] = None
    dependency_ids: List[str] = []
    vendor_id: Optional[str] = None
    doc_count: int = 0
    worst_doc_status: Optional[str] = None
    # [P3-04e] Confidence + source provenance, derived from the step's linked
    # requirement (requirements.confidence_pct / citations). Absent when the
    # step has no requirement link — the employee UI then shows no badge.
    confidence_level: Optional[str] = None   # 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
    source_url: Optional[str] = None
    source_fetched_at: Optional[str] = None
    source_excerpt: Optional[str] = None


class RoadmapTrackV2(BaseModel):
    id: str
    name: str
    icon: str
    sort_order: int
    progress_pct: int
    steps: List[RoadmapStepV2] = []


class RoadmapTracksResponse(BaseModel):
    tracks: List[RoadmapTrackV2]


def _bucket_confidence(pct: Optional[int]) -> Optional[str]:
    """Map a requirement's confidence_pct (0-100) to a display level.

    Thresholds match the documented RequirementCard bands
    (requirements.confidence_pct: >80 green, 50-80 yellow, <50 red).
    Returns None when there is no linked requirement, so the step shows no badge.
    """
    if pct is None:
        return None
    if pct >= 80:
        return "HIGH"
    if pct >= 50:
        return "MEDIUM"
    return "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# [P1-5] Dossier & Forms — response models
# ─────────────────────────────────────────────────────────────────────────────

class _DossierFormTemplate(BaseModel):
    id: str
    code: str
    name: str
    authority_code: Optional[str]
    authority_name: Optional[str]
    country: str
    category: Optional[str]
    version: str
    fields_total: int
    # [P1-05] Official Tier-1 authority URL where this form is completed/submitted.
    source_url: Optional[str] = None
    # [P1-05d] When the source URL was last fetched/verified (source_pages.last_fetched_at).
    source_last_verified: Optional[str] = None
    # [P1-05 checklist] Required supporting documents, derived from the template
    # fields that carry requires_original=true. Each item: {"key","label"}.
    required_documents: List[Dict[str, str]] = []


class _DossierFormPerson(BaseModel):
    kind: str            # 'employee' | 'spouse' | 'child' | 'other'
    name: Optional[str]
    dependent_id: Optional[str]
    profile_id: Optional[str]


class _DossierFieldsSummary(BaseModel):
    total: int
    filled_by_ai: int
    filled_by_human: int
    reviewed: int
    overridden: int
    missing_required: int


class CaseFormSummary(BaseModel):
    id: str
    case_id: str
    status: str
    completion_pct: int
    deadline: Optional[str]
    deadline_trigger: Optional[str]
    blocker_form_id: Optional[str]
    blocker_form_code: Optional[str]
    # [P2-6] True when this form has an unresolved blocker (the blocking form
    # is not yet approved). Derived server-side so the frontend doesn't need
    # to join across forms.
    is_blocked: bool = False
    original_file_url: Optional[str]
    draft_pdf_url: Optional[str]
    submitted_at: Optional[str]
    receipt_ref: Optional[str]
    rejection_reason: Optional[str] = None   # [P4-5] set when status='rejected'
    roadmap_step_id: Optional[str] = None   # [P1-6] step that triggered this form
    roadmap_step_title: Optional[str] = None   # [P1-05] human-readable title of that step
    is_adhoc: bool = False   # [P4-3] true when this is an ad-hoc "Add document" entry
    notes: Optional[str] = None   # [P4-3] free-text notes from the Add-document modal
    template: _DossierFormTemplate
    person: _DossierFormPerson
    fields_summary: _DossierFieldsSummary
    created_at: str
    updated_at: str


# ─────────────────────────────────────────────────────────────────────────────
# [P1-05c] Per-form supporting document
# ─────────────────────────────────────────────────────────────────────────────

class FormDocumentItem(BaseModel):
    id: str
    case_form_id: str
    case_id: str
    file_name: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_by: Optional[str] = None
    created_at: str
    # [P1-05 checklist] the required-document item this upload satisfies, if any.
    doc_key: Optional[str] = None
    # 1-hour signed Storage URL; None when storage is unavailable (dev/test).
    download_url: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# [P2-2] Field value response model
# ─────────────────────────────────────────────────────────────────────────────

class FieldValueItem(BaseModel):
    """A single field value as returned by the GET endpoint."""
    field_id: str
    label: str
    field_type: str           # text | date | select | boolean | …
    required: bool
    position: int
    prefill_source: Optional[str]
    requires_original: bool
    options: Optional[List[str]]   # only for select fields
    # Stored value metadata (None if no value has been saved yet)
    value: Optional[str]
    filled_by: Optional[str]       # ai | system | employee | specialist | hr
    ai_confidence: Optional[float]
    reviewed: bool
    overridden: bool


# ─────────────────────────────────────────────────────────────────────────────
# Comment / event response models
# ─────────────────────────────────────────────────────────────────────────────

class CommentItem(BaseModel):
    id: str
    case_form_id: str
    author_id: str
    author_name: Optional[str]
    content: str
    created_at: str


class EventItem(BaseModel):
    id: str
    case_form_id: str
    event_type: str
    actor_id: Optional[str]
    actor_name: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    note: Optional[str]
    created_at: str


# ─────────────────────────────────────────────────────────────────────────────
# Dossier package response models
# ─────────────────────────────────────────────────────────────────────────────

class DossierPackageResponse(BaseModel):
    id: str
    case_id: str
    name: str
    form_ids: List[str]
    cover_page: bool
    pdf_url: Optional[str]
    generated_at: Optional[str]
    created_at: str


class DossierPackageDetailResponse(BaseModel):
    id: str
    case_id: str
    name: str
    form_ids: List[str]
    cover_page: bool
    pdf_url: Optional[str]
    generated_at: Optional[str]
    created_at: str
    is_stale: bool


# ─────────────────────────────────────────────────────────────────────────────
# Private GET-only helpers (transformers + PDF builders)
# ─────────────────────────────────────────────────────────────────────────────


def _row_to_summary(row: Dict[str, Any]) -> CaseFormSummary:
    """Map a flat SQL result row into the structured CaseFormSummary shape."""
    # JSONB columns come back as list/dict from Postgres; as str from SQLite test harness.
    fields = row.get("template_fields") or []
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except (json.JSONDecodeError, TypeError):
            fields = []
    fields_total = len(fields) if isinstance(fields, list) else 0

    # [P1-05 checklist] Required supporting documents = template fields that
    # must be backed by an original document (requires_original=true).
    required_documents: List[Dict[str, str]] = [
        {"key": str(f.get("id")), "label": str(f.get("label") or f.get("id"))}
        for f in fields
        if isinstance(f, dict) and f.get("requires_original") and f.get("id")
    ] if isinstance(fields, list) else []

    # Person resolution: dependent wins (more specific) over employee profile.
    dep_id = row.get("dependent_id")
    if dep_id:
        rel = (row.get("dependent_relationship") or "").lower()
        kind = "spouse" if rel in ("spouse", "partner") else ("child" if rel == "child" else "other")
        person = _DossierFormPerson(
            kind=kind,
            name=row.get("dependent_name"),
            dependent_id=str(dep_id),
            profile_id=None,
        )
    else:
        # person_id may map to a profiles row (employee or HR); we default to 'employee'
        # since the trigger engine only sets person_id for the employee path.
        person = _DossierFormPerson(
            kind="employee",
            name=(row.get("profile_full_name") or row.get("profile_email") or None),
            dependent_id=None,
            profile_id=(str(row["person_id"]) if row.get("person_id") else None),
        )

    def _iso(v: Any) -> Optional[str]:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            try:
                return v.isoformat()
            except Exception:
                return str(v)
        return str(v)

    # [P2-6] is_blocked: the form has an unresolved blocker iff blocker_form_id
    # is set, this form is not yet terminal, and the blocker is not yet approved.
    current_status = str(row.get("status") or "")
    terminal_statuses = {"submitted", "approved", "rejected"}
    blocker_status = str(row.get("blocker_status") or "")
    is_blocked = (
        bool(row.get("blocker_form_id"))
        and current_status not in terminal_statuses
        and blocker_status != "approved"
    )

    # [P4-3] Ad-hoc forms have no form_template — synthesize a "Custom" pseudo-template
    # so the dossier list still renders a name/authority for them.
    is_adhoc = bool(row.get("is_adhoc")) or row.get("template_id") is None
    if is_adhoc:
        template = _DossierFormTemplate(
            id="adhoc",
            code="CUSTOM",
            name=(row.get("adhoc_name") or "Custom document"),
            authority_code=None,
            authority_name=(row.get("adhoc_authority") or None),
            country="",
            category=None,
            version="—",
            fields_total=0,
            source_url=None,
            source_last_verified=None,
            required_documents=[],
        )
    else:
        template = _DossierFormTemplate(
            id=str(row["template_id"]),
            code=str(row["template_code"]),
            name=str(row["template_name"]),
            authority_code=row.get("template_authority_code"),
            authority_name=row.get("template_authority_name"),
            country=str(row["template_country"]),
            category=row.get("template_category"),
            version=str(row["template_version"]),
            fields_total=fields_total,
            source_url=row.get("template_source_url"),  # [P1-05]
            source_last_verified=_iso(row.get("source_last_verified")),  # [P1-05d]
            required_documents=required_documents,  # [P1-05 checklist]
        )

    return CaseFormSummary(
        id=str(row["id"]),
        case_id=str(row["case_id"]),
        status=str(row["status"]),
        completion_pct=int(row.get("completion_pct") or 0),
        deadline=_iso(row.get("deadline")),
        deadline_trigger=row.get("deadline_trigger"),
        blocker_form_id=(str(row["blocker_form_id"]) if row.get("blocker_form_id") else None),
        blocker_form_code=row.get("blocker_form_code"),
        is_blocked=is_blocked,
        original_file_url=row.get("original_file_url"),
        draft_pdf_url=row.get("draft_pdf_url"),
        submitted_at=_iso(row.get("submitted_at")),
        receipt_ref=row.get("receipt_ref"),
        rejection_reason=row.get("rejection_reason") or None,   # [P4-5]
        roadmap_step_id=(str(row["roadmap_step_id"]) if row.get("roadmap_step_id") else None),  # [P1-6]
        roadmap_step_title=(
            row.get("roadmap_step_title")
            or (None if is_adhoc else track_label_for_form(
                row.get("template_category"), row.get("template_code")))
        ),  # [P1-05] persisted step title, else [AIQ-800] computed track label
        is_adhoc=is_adhoc,   # [P4-3]
        notes=row.get("notes") or None,   # [P4-3]
        template=template,
        person=person,
        fields_summary=_DossierFieldsSummary(
            total=fields_total,
            filled_by_ai=int(row.get("fv_filled_by_ai") or 0),
            filled_by_human=int(row.get("fv_filled_by_human") or 0),
            reviewed=int(row.get("fv_reviewed") or 0),
            overridden=int(row.get("fv_overridden") or 0),
            # missing_required = fields_total - any field that has a value
            # (computed by caller from the inputs we already have)
            missing_required=max(
                0,
                fields_total
                - int(row.get("fv_filled_by_ai") or 0)
                - int(row.get("fv_filled_by_human") or 0),
            ),
        ),
        created_at=_iso(row.get("created_at")) or "",
        updated_at=_iso(row.get("updated_at")) or "",
    )


def _load_form_with_template(
    conn: Any,
    case_id: str,
    form_id: str,
) -> Optional[Dict[str, Any]]:
    """Return the case_form row joined with its template fields, or None if not found."""
    row = conn.execute(
        _sql_text(
            f"""
            SELECT cf.id, cf.case_id, cf.status, cf.completion_pct,
                   cf.deadline, cf.deadline_trigger, cf.blocker_form_id,
                   cf.original_file_url, cf.draft_pdf_url,
                   cf.submitted_at, cf.receipt_ref, cf.rejection_reason,
                   cf.person_id, cf.dependent_id,
                   cf.created_at, cf.updated_at,
                   ft.id      AS template_id,
                   ft.code    AS template_code,
                   ft.name    AS template_name,
                   ft.authority_code AS template_authority_code,
                   ft.authority_name AS template_authority_name,
                   ft.country AS template_country,
                   ft.category AS template_category,
                   ft.version AS template_version,
                   ft.fields  AS template_fields,
                   cf.is_adhoc, cf.adhoc_name, cf.adhoc_authority, cf.notes
            FROM {_pg_table('case_forms')} cf
            -- [P4-3] LEFT JOIN so ad-hoc forms (form_template_id IS NULL) still appear.
            LEFT JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
            WHERE cf.id = :form_id AND cf.case_id = :case_id
            """
        ),
        {"form_id": form_id, "case_id": case_id},
    ).mappings().first()
    return dict(row) if row else None


def _compute_completion(
    template_fields: List[Dict[str, Any]],
    stored_values: Dict[str, str],
) -> int:
    """Return completion_pct (0-100) based on required fields with a non-empty value."""
    required = [f for f in template_fields if f.get("required")]
    if not required:
        # No required fields → count all fields
        total = len(template_fields)
        if not total:
            return 0
        filled = sum(1 for f in template_fields if stored_values.get(f["id"]) not in (None, ""))
        return round(filled / total * 100)
    filled_required = sum(
        1 for f in required if stored_values.get(f["id"]) not in (None, "")
    )
    return round(filled_required / len(required) * 100)


def _build_overlay_page(
    page_width: float,
    page_height: float,
    fields_on_page: List[Dict[str, Any]],
    field_values: Dict[str, str],
) -> Optional[bytes]:
    """
    Build a single-page transparent PDF overlay using reportlab.
    Returns raw bytes of a 1-page PDF, or None if no values to draw.
    """
    try:
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        logger.warning("reportlab not available — PDF overlay skipped")
        return None

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))

    drew_any = False
    for field in fields_on_page:
        fid = field.get("id")
        value = field_values.get(fid) if fid else None
        if value is None or str(value).strip() == "":
            continue
        pdf_x = field.get("pdf_x")
        pdf_y = field.get("pdf_y")
        if pdf_x is None or pdf_y is None:
            continue

        font_size = float(field.get("pdf_font_size") or 10)
        max_width = field.get("pdf_max_width")
        text = str(value)

        c.setFont("Helvetica", font_size)
        c.setFillColorRGB(0, 0, 0)

        if max_width:
            # Use reportlab's drawString with available width constraint
            c.drawString(float(pdf_x), float(pdf_y), text)
        else:
            c.drawString(float(pdf_x), float(pdf_y), text)
        drew_any = True

    if not drew_any:
        return None

    c.save()
    buf.seek(0)
    return buf.read()


def _generate_filled_pdf(
    original_pdf_bytes: bytes,
    template_fields: List[Dict[str, Any]],
    field_values: Dict[str, str],
) -> bytes:
    """
    Overlay field values onto an existing PDF using pypdf + reportlab.
    Fields without pdf_x/pdf_y/pdf_page are skipped.
    """
    from pypdf import PdfWriter, PdfReader

    reader = PdfReader(io.BytesIO(original_pdf_bytes))
    num_pages = len(reader.pages)

    # Group fields by page index (0-based)
    fields_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for field in template_fields:
        pdf_page = field.get("pdf_page")
        if pdf_page is None:
            continue
        page_idx = int(pdf_page) - 1
        if page_idx < 0 or page_idx >= num_pages:
            continue
        fields_by_page.setdefault(page_idx, []).append(field)

    # Build overlay PDFs per page
    overlay_readers: Dict[int, Any] = {}
    for page_idx, fields_on_page in fields_by_page.items():
        page = reader.pages[page_idx]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        overlay_bytes = _build_overlay_page(w, h, fields_on_page, field_values)
        if overlay_bytes:
            from pypdf import PdfReader as _R
            overlay_readers[page_idx] = _R(io.BytesIO(overlay_bytes))

    # Merge overlays into output
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in overlay_readers:
            overlay_page = overlay_readers[i].pages[0]
            page.merge_page(overlay_page)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


def _make_blank_pdf(title: str, message: str) -> bytes:
    """Generate a minimal single-page PDF when no original is available."""
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
    except ImportError:
        # Fall back to raw minimal PDF
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \nttrailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, title)
    c.setFont("Helvetica", 11)
    c.drawString(50, 720, message)
    c.save()
    buf.seek(0)
    return buf.read()


def _safe_filename_part(s: Optional[str]) -> str:
    """Slugify a string for use in a filename."""
    if not s:
        return "unknown"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s.strip())


def _try_store_draft_pdf(
    case_form_id: str,
    pdf_bytes: bytes,
    conn: Any,
) -> Optional[str]:
    """
    Upload PDF to Supabase Storage and update draft_pdf_url on the case_form row.
    Returns the public URL, or None if storage is unavailable (dev mode).
    """
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = f"case-forms/{case_form_id}/draft_{ts}.pdf"
        sb.storage.from_("case-forms").upload(
            path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        # Get a signed URL valid for 7 days
        signed = sb.storage.from_("case-forms").create_signed_url(path, 60 * 60 * 24 * 7)
        public_url: Optional[str] = signed.get("signedURL") or signed.get("signedUrl")
        if public_url:
            conn.execute(
                _sql_text(
                    f"UPDATE {_pg_table('case_forms')} "
                    f"SET draft_pdf_url = :url, updated_at = {_sql_now()} "
                    f"WHERE id = :id"
                ),
                {"url": public_url, "id": case_form_id},
            )
        return public_url
    except Exception as exc:
        logger.warning("draft_pdf storage unavailable for form %s: %s", case_form_id, exc)
        return None


def _build_cover_page(
    package_name: str,
    case_id: str,
    forms_meta: List[Dict[str, Any]],
    page_width: float = 595.0,
    page_height: float = 842.0,
) -> bytes:
    """
    Generate an A4 cover page PDF for the dossier package.
    Includes: package name, case ID, date, list of included forms.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    w, h = float(page_width), float(page_height)
    c = rl_canvas.Canvas(buf, pagesize=(w, h))

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 80, package_name)

    # Subtitle line
    c.setFont("Helvetica", 11)
    today = _dt.date.today().isoformat()
    c.drawString(50, h - 106, f"Generated: {today}")

    # Divider line
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(50, h - 120, w - 50, h - 120)

    # Table header
    c.setFont("Helvetica-Bold", 10)
    y = h - 148
    c.drawString(50, y, "#")
    c.drawString(80, y, "Code")
    c.drawString(160, y, "Form name")
    c.drawString(390, y, "Authority")
    c.line(50, y - 6, w - 50, y - 6)

    # Form rows
    c.setFont("Helvetica", 9)
    for i, meta in enumerate(forms_meta, 1):
        y -= 22
        if y < 80:
            break  # Truncate if too many forms
        c.drawString(50, y, str(i))
        c.drawString(80, y, str(meta.get("code") or "")[:12])
        c.drawString(160, y, str(meta.get("name") or "")[:40])
        c.drawString(390, y, str(meta.get("authority_code") or "")[:16])

    c.save()
    buf.seek(0)
    return buf.read()


def _build_divider_page(
    form_code: str,
    form_name: str,
    authority_name: Optional[str],
    page_width: float = 595.0,
    page_height: float = 842.0,
) -> bytes:
    """
    Generate a clean white divider page for a single form in the merged dossier.
    Shows form title, authority name, and form code centered on the page.
    """
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    w, h = float(page_width), float(page_height)
    c = rl_canvas.Canvas(buf, pagesize=(w, h))

    mid_y = h / 2
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, mid_y + 30, form_name)

    c.setFont("Helvetica", 11)
    if authority_name:
        c.drawCentredString(w / 2, mid_y, authority_name)
        c.setFont("Helvetica", 10)
        c.drawCentredString(w / 2, mid_y - 22, form_code)
    else:
        c.drawCentredString(w / 2, mid_y - 11, form_code)

    c.save()
    buf.seek(0)
    return buf.read()


def _fetch_form_pdf_bytes(
    conn: Any,
    case_id: str,
    form_id: str,
) -> bytes:
    """
    Generate a filled PDF for one form using the shared P3-1 helpers.
    Falls back to a blank placeholder if no original PDF exists.
    """
    form_row = _load_form_with_template(conn, case_id, form_id)
    if not form_row:
        return _make_blank_pdf(f"Form {form_id}", "Form not found")

    fv_rows = conn.execute(
        _sql_text(
            f"SELECT field_id, value FROM {_pg_table('case_form_field_values')} "
            f"WHERE case_form_id = :fid AND value IS NOT NULL AND value != ''"
        ),
        {"fid": form_id},
    ).mappings().all()
    field_values: Dict[str, str] = {str(r["field_id"]): str(r["value"]) for r in fv_rows}

    raw_fields = form_row.get("template_fields")
    if isinstance(raw_fields, str):
        template_fields: List[Dict[str, Any]] = json.loads(raw_fields)
    else:
        template_fields = list(raw_fields) if raw_fields else []

    original_url = form_row.get("original_file_url")
    if original_url:
        try:
            resp = _requests.get(original_url, timeout=15)
            resp.raise_for_status()
            return _generate_filled_pdf(resp.content, template_fields, field_values)
        except Exception as exc:
            logger.warning("dossier: failed to fetch original for form %s: %s", form_id, exc)

    return _make_blank_pdf(
        form_row.get("template_name") or form_row.get("template_code") or form_id,
        "Original PDF unavailable. "
        + ", ".join(f"{k}: {v}" for k, v in list(field_values.items())[:8]),
    )


def _merge_pdfs(
    pdf_buffers: List[bytes],
) -> bytes:
    """Concatenate a list of PDFs into a single output PDF using pypdf."""
    from pypdf import PdfWriter, PdfReader

    writer = PdfWriter()
    for pdf_bytes in pdf_buffers:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


# ─────────────────────────────────────────────────────────────────────────────
# §3 Employee reads — `list_employee_cases`
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", tags=["cases"])
def list_employee_cases(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GET /api/cases — returns the authenticated employee's assigned cases.
    Mirrors /api/employee/cases for frontend and E2E test compatibility.
    HR/admin tokens receive an empty list (use /api/hr/cases instead).
    Fixes B12b: previously returned 404 because no root route existed on this router.
    """
    role = (user.get("role") or "employee").lower()
    if role not in ("employee",):
        # Role isolation: HR/admin must use /api/hr/cases, not this endpoint.
        return {"cases": []}

    uid = user.get("id") or user.get("user_id") or user.get("sub")
    rid = getattr(request.state, "request_id", None)
    try:
        linked = main_db.list_linked_assignments_for_employee(uid, request_id=rid)
    except Exception:
        logger.exception("list_employee_cases: DB query failed for uid=%s", uid)
        linked = []

    cases = []
    for row in linked:
        d = dict(row)
        case_id = d.get("case_id") or d.get("id")
        cases.append({
            "id": case_id,
            "caseId": case_id,
            "assignmentId": d.get("id"),
            "status": d.get("status"),
            "employeeIdentifier": d.get("employee_identifier"),
        })
    return {"cases": cases}


# ─────────────────────────────────────────────────────────────────────────────
# §5 Shared reads — case detail, requirements, roadmap, research status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}", response_model=schemas.CaseDTO)
def get_case(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        _assert_case_access(user, case_id)
        draft = json.loads(case.draft_json)
        return _case_dto(case, draft)


@router.get("/{case_id}/requirements", response_model=schemas.CaseRequirementsDTO)
def get_case_requirements(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    _assert_case_access(user, case_id)
    try:
        return compute_case_requirements(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found")


# ─────────────────────────────────────────────────────────────────────────────
# GAP 2 / GAP 5: Multi-track roadmap endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/roadmap")
def get_case_roadmap(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """
    GAP 2 & GAP 5: Returns a multi-track relocation roadmap derived from the case draft.
    Replaces window.PATHWAY_V2.deriveTimeline() with a real server-side computation.
    Tracks: Visa & Permit | Civil Documents | Family (conditional) | Settlement.
    """
    _assert_case_access(user, case_id)
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        draft = json.loads(case.draft_json or "{}")

    case_dict = {
        "id": case_id,
        "status": case.status,
        "draft": draft,
    }
    # P2-01e: for an allowlisted (flag-on) account, serve the live AI EEA roadmap
    # from the RAG pipeline — confidence-gated (P2-01b) and staleness-annotated
    # (P2-01c). Anything that doesn't generate cleanly (uncovered corridor →
    # RULE_NOT_FOUND, unmappable case, or pipeline error) falls back to the
    # deterministic roadmap, so a user never sees an empty/refusal roadmap.
    if is_flag_enabled_for(user.get("id"), LIVE_EEA_ROADMAP_FLAG):
        try:
            candidate = generate_ai_roadmap_for_case(case_dict)
        except Exception:
            logger.exception(
                "AI roadmap generation failed for case %s; serving deterministic roadmap",
                case_id,
            )
            candidate = None
        if is_ai_roadmap(candidate) and candidate.get("result") == "OK":
            candidate = gate_roadmap_for_case(case_id, candidate)
            candidate = annotate_staleness(candidate, now=_dt.datetime.now(_dt.timezone.utc))
            candidate["ai_roadmap_eligible"] = True
            return candidate
    return derive_roadmap(case_dict)


@router.get("/{case_id}/roadmap/tracks", response_model=RoadmapTracksResponse)
def get_case_roadmap_tracks(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> RoadmapTracksResponse:
    """
    [P1-6 / AIQ-800] Returns the case roadmap as tracks → steps, projected at
    read time from the case's real case_forms (Option B). Each form is a step in
    its track bucket; the never-written roadmap_tracks/roadmap_steps tables are
    no longer read. Used by the employee RoadmapScreen.
    """
    _assert_case_access(user, case_id)

    # [AIQ-800] Option B — project the roadmap from the case's real forms instead
    # of reading the (never-written) roadmap_tracks/roadmap_steps tables. Reuses
    # the Dossier's form-loading path, so it shares the same (correct) case-id
    # handling; each form becomes a step in its track bucket.
    summaries = _load_case_form_summaries(case_id)
    projected = project_tracks(summaries)
    tracks = [
        RoadmapTrackV2(
            id=t.key,
            name=t.name,
            icon=t.icon,
            sort_order=t.sort_order,
            progress_pct=t.progress_pct,
            steps=[
                RoadmapStepV2(
                    id=s.id,
                    title=s.title,
                    description=None,
                    status=s.status,
                    owner=s.owner,
                    due_date=s.due_date,
                    sort_order=s.sort_order,
                    ai_suggestion=None,
                    dependency_ids=[],
                    vendor_id=None,
                    # [AIQ-800] doc chip + dossier deep-link deferred (follow-up);
                    # the roadmap renders tracks/steps/status/progress without it.
                    doc_count=0,
                    worst_doc_status=None,
                )
                for s in t.steps
            ],
        )
        for t in projected
    ]
    return RoadmapTracksResponse(tracks=tracks)


# ─────────────────────────────────────────────────────────────────────────────
# GAP 9: Research status polling endpoint (Option B — polling, no SSE)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/research/status")
def get_research_status(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 9: Poll-based research progress for the S2 discovery log.
    Returns {status, progress_pct, events[{ts, msg}]}.
    Client polls every 2s; no SSE infrastructure required.

    SEC fix (GAP-9): require an authenticated session and case-level access.
    Employees can poll only their own cases; HR / admins can poll any case in
    their company. Previously this endpoint was unauthenticated and any
    case_id known to the caller leaked the discovery event log.
    """
    require_case_access(case_id, user)
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        draft = json.loads(case.draft_json or "{}")

    basics = draft.get("relocationBasics", {})
    dest = basics.get("destCountry", "")
    purpose = basics.get("purpose", "employment")

    # Check if requirements snapshot exists (research completed)
    snapshot_id = case.requirements_snapshot_id
    if snapshot_id:
        # Research has been run — compute a realistic event log from the requirements
        try:
            reqs = compute_case_requirements(case_id)
            req_count = len(reqs.requirements) if reqs.requirements else 0
            doc_count = len([r for r in (reqs.requirements or []) if "document" in (r.category or "").lower()])
        except Exception:
            req_count = 0
            doc_count = 0

        events = [
            {"ts": "14:02:11", "msg": f"Authenticating immigration authority API for {dest}"},
            {"ts": "14:02:13", "msg": f"Pulling {purpose} permit schema… OK"},
            {"ts": "14:02:17", "msg": f"Cross-referencing bilateral agreements"},
            {"ts": "14:02:21", "msg": "Detecting dependent profile from case draft"},
            {"ts": "14:02:28", "msg": f"Compiling requirement graph ({req_count} nodes)"},
            {"ts": "14:02:34", "msg": "Validating salary threshold against assignment data"},
            {"ts": "14:02:38", "msg": "Recommending specialist advisors for corridor"},
            {"ts": "14:02:45", "msg": f"Plan compiled. {req_count} requirements, {doc_count} documents."},
        ]
        return {
            "status": "completed",
            "progress_pct": 100,
            "job_id": snapshot_id,
            "events": events,
        }

    # No snapshot — research hasn't been run yet
    return {
        "status": "not_started",
        "progress_pct": 0,
        "job_id": None,
        "events": [],
        "hint": "Call POST /api/cases/{case_id}/research/start to begin discovery.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# §5 Shared reads — Dossier & Forms list
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/forms", response_model=List[CaseFormSummary])
def list_case_forms(
    case_id: str,
    status: Optional[str] = None,
    roadmap_step_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[CaseFormSummary]:
    """
    List all CaseForms for a case, with template metadata, person name, and
    a FieldValue summary count. The frontend uses this to render the Dossier
    & Forms list view.

    Optional `?status=` filter narrows by document_status (e.g. 'ready').
    Optional `?roadmap_step_id=` filter narrows by roadmap step [P1-6].
    """
    _assert_case_access(user, case_id)
    return _load_case_form_summaries(case_id, status=status, roadmap_step_id=roadmap_step_id)


def _load_case_form_summaries(
    case_id: str,
    status: Optional[str] = None,
    roadmap_step_id: Optional[str] = None,
) -> List[CaseFormSummary]:
    """[AIQ-800] Shared loader behind both the Dossier list (`list_case_forms`)
    and the roadmap projection (`get_case_roadmap_tracks`). No auth check —
    callers must `_assert_case_access` first.
    """
    # Build the join in one statement. The aggregate over case_form_field_values
    # is done as a correlated sub-select per row — simpler than a GROUP BY and
    # cheap given typical row counts (<50 forms per case).
    extra_where = ""
    params: Dict[str, Any] = {"case_id": case_id}
    if status:
        extra_where += " AND cf.status = :status"
        params["status"] = status
    if roadmap_step_id:
        extra_where += " AND cf.roadmap_step_id = :roadmap_step_id"
        params["roadmap_step_id"] = roadmap_step_id
    where_status = extra_where  # keep existing variable name used below

    sql = f"""
        SELECT
          cf.id,
          cf.case_id,
          cf.status,
          cf.completion_pct,
          cf.deadline,
          cf.deadline_trigger,
          cf.blocker_form_id,
          (SELECT ft2.code FROM {_pg_table('case_forms')} cf2
            JOIN {_pg_table('form_templates')} ft2 ON ft2.id = cf2.form_template_id
            WHERE cf2.id = cf.blocker_form_id) AS blocker_form_code,
          -- [P2-6] Status of the blocking form — used to compute is_blocked in Python
          (SELECT cf_b.status FROM {_pg_table('case_forms')} cf_b
            WHERE cf_b.id = cf.blocker_form_id) AS blocker_status,
          cf.original_file_url,
          cf.draft_pdf_url,
          cf.submitted_at,
          cf.receipt_ref,
          cf.rejection_reason,
          cf.person_id,
          cf.dependent_id,
          cf.roadmap_step_id,
          cf.created_at,
          cf.updated_at,
          ft.id      AS template_id,
          ft.code    AS template_code,
          ft.name    AS template_name,
          ft.authority_code AS template_authority_code,
          ft.authority_name AS template_authority_name,
          ft.country AS template_country,
          ft.category AS template_category,
          ft.version AS template_version,
          ft.fields  AS template_fields,
          ft.source_url AS template_source_url,
          sp.last_fetched_at AS source_last_verified,
          rs.title AS roadmap_step_title,
          cf.is_adhoc, cf.adhoc_name, cf.adhoc_authority, cf.notes,
          cd.relationship AS dependent_relationship,
          cd.full_name    AS dependent_name,
          p.full_name     AS profile_full_name,
          p.email         AS profile_email,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.filled_by = 'ai') AS fv_filled_by_ai,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.filled_by IN ('employee','hr','specialist','system')) AS fv_filled_by_human,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.reviewed = TRUE) AS fv_reviewed,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.overridden = TRUE) AS fv_overridden
        FROM {_pg_table('case_forms')} cf
        -- [P4-3] LEFT JOIN so ad-hoc forms (form_template_id IS NULL) still appear.
        LEFT JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
        -- [P1-05d] source freshness: last_fetched_at for this form's official URL.
        LEFT JOIN {_pg_table('source_pages')} sp ON sp.url = ft.source_url
        -- [P1-05] roadmap step title for the "which step" label on the form card.
        LEFT JOIN {_pg_table('roadmap_steps')} rs ON rs.id = cf.roadmap_step_id
        LEFT JOIN {_pg_table('case_dependents')} cd ON cd.id = cf.dependent_id
        LEFT JOIN {_pg_table('profiles')} p ON CAST(p.id AS TEXT) = cf.person_id
        WHERE cf.case_id = :case_id{where_status}
        ORDER BY
          -- Forms with an unresolved blocker (UI-blocked) come first so the
          -- user can see what's gating their progress. `blocker_form_id IS NOT
          -- NULL` is the canonical signal — there's no `blocked` value in the
          -- document_status enum.
          CASE WHEN cf.blocker_form_id IS NOT NULL
                AND cf.status NOT IN ('submitted','approved')
               THEN 0 ELSE 1 END,
          CASE cf.status
            WHEN 'pending_doc' THEN 1
            WHEN 'auto_filled' THEN 2
            WHEN 'in_progress' THEN 3
            WHEN 'ready'       THEN 4
            WHEN 'not_started' THEN 5
            WHEN 'submitted'   THEN 6
            WHEN 'approved'    THEN 7
            WHEN 'rejected'    THEN 8
            ELSE 99
          END,
          cf.created_at ASC
    """

    try:
        with main_db.engine.connect() as conn:
            rows = conn.execute(_sql_text(sql), params).mappings().all()
    except Exception:
        logger.exception("dossier: failed to list case_forms case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to load case forms")

    return [_row_to_summary(dict(r)) for r in rows]


@router.get(
    "/{case_id}/forms/{form_id}/documents",
    response_model=List[FormDocumentItem],
)
def list_form_documents(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[FormDocumentItem]:
    """
    [P1-05c] List the supporting documents uploaded against a single case_form.
    Each item carries a 1-hour signed download URL (None if storage is
    unavailable, e.g. dev/test).
    """
    _assert_case_access(user, case_id)

    with main_db.engine.connect() as conn:
        rows = conn.execute(
            _sql_text(
                f"""
                SELECT id, case_form_id, case_id, file_name, storage_path,
                       content_type, size_bytes, uploaded_by, doc_key, created_at
                FROM {_pg_table('case_form_documents')}
                WHERE case_form_id = :form_id AND case_id = :case_id
                ORDER BY created_at DESC
                """
            ),
            {"form_id": form_id, "case_id": case_id},
        ).mappings().all()

    # Best-effort signing — never fail the list because storage is down.
    sb = None
    try:
        from ..services.supabase_client import get_supabase_admin_client  # lazy
        sb = get_supabase_admin_client()
    except Exception:
        sb = None

    items: List[FormDocumentItem] = []
    for r in rows:
        download_url: Optional[str] = None
        if sb is not None:
            try:
                signed = sb.storage.from_("case-documents").create_signed_url(
                    str(r["storage_path"]), 3600
                )
                download_url = signed.get("signedURL") or signed.get("signedUrl")
            except Exception:
                download_url = None
        items.append(
            FormDocumentItem(
                id=str(r["id"]),
                case_form_id=str(r["case_form_id"]),
                case_id=str(r["case_id"]),
                file_name=str(r["file_name"]),
                content_type=r.get("content_type"),
                size_bytes=(int(r["size_bytes"]) if r.get("size_bytes") is not None else None),
                uploaded_by=(str(r["uploaded_by"]) if r.get("uploaded_by") else None),
                doc_key=(str(r["doc_key"]) if r.get("doc_key") else None),
                created_at=str(r["created_at"]),
                download_url=download_url,
            )
        )
    return items


# ─────────────────────────────────────────────────────────────────────────────
# §5 Shared reads — Form fields, comments, events
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/forms/{form_id}/fields", response_model=List[FieldValueItem])
def get_form_fields(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[FieldValueItem]:
    """
    Return every field in the form template merged with the stored FieldValue (if any).
    Fields with no stored value still appear in the list with value=None.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.connect() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            # Load all stored field values for this form
            fv_rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT field_id, value, filled_by, ai_confidence, reviewed, overridden
                    FROM {_pg_table('case_form_field_values')}
                    WHERE case_form_id = :form_id
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        logger.exception("fields: failed to load fields case_id=%s form_id=%s", case_id, form_id)
        raise HTTPException(status_code=500, detail="Failed to load form fields")

    # Index stored values by field_id
    stored: Dict[str, Dict[str, Any]] = {str(r["field_id"]): dict(r) for r in fv_rows}

    # Parse template fields JSONB
    raw_fields = form_row.get("template_fields") or []
    if isinstance(raw_fields, str):
        try:
            raw_fields = json.loads(raw_fields)
        except (json.JSONDecodeError, TypeError):
            raw_fields = []

    items: List[FieldValueItem] = []
    for fd in sorted(raw_fields, key=lambda f: f.get("position", 0)):
        fid = fd.get("id", "")
        sv = stored.get(fid)
        items.append(FieldValueItem(
            field_id=fid,
            label=fd.get("label", fid),
            field_type=fd.get("type", "text"),
            required=bool(fd.get("required", False)),
            position=int(fd.get("position", 0)),
            prefill_source=fd.get("prefill_source"),
            requires_original=bool(fd.get("requires_original", False)),
            options=fd.get("options"),
            value=sv["value"] if sv else None,
            filled_by=sv["filled_by"] if sv else None,
            ai_confidence=sv["ai_confidence"] if sv else None,
            reviewed=bool(sv["reviewed"]) if sv else False,
            overridden=bool(sv["overridden"]) if sv else False,
        ))

    return items


@router.get("/{case_id}/forms/{form_id}/comments", response_model=List[CommentItem])
def list_form_comments(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[CommentItem]:
    """List all comments on a CaseForm, newest first."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.connect() as conn:
            # Verify the form belongs to this case
            exists = conn.execute(
                _sql_text(
                    f"SELECT id FROM {_pg_table('case_forms')} "
                    f"WHERE id = :form_id AND case_id = :case_id"
                ),
                {"form_id": form_id, "case_id": case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT c.id, c.case_form_id, c.author_id, c.content, c.created_at,
                           p.full_name AS author_name
                    FROM {_pg_table('case_form_comments')} c
                    LEFT JOIN {_pg_table('profiles')} p ON CAST(p.id AS TEXT) = c.author_id
                    WHERE c.case_form_id = :form_id
                    ORDER BY c.created_at ASC
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        logger.exception("comments: list failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to load comments")

    return [
        CommentItem(
            id=str(r["id"]),
            case_form_id=str(r["case_form_id"]),
            author_id=str(r["author_id"]),
            author_name=r.get("author_name"),
            content=str(r["content"]),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.get("/{case_id}/forms/{form_id}/events", response_model=List[EventItem])
def list_form_events(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[EventItem]:
    """Return the history log for a CaseForm, newest first."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.connect() as conn:
            exists = conn.execute(
                _sql_text(
                    f"SELECT id FROM {_pg_table('case_forms')} "
                    f"WHERE id = :form_id AND case_id = :case_id"
                ),
                {"form_id": form_id, "case_id": case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT e.id, e.case_form_id, e.event_type, e.actor_id,
                           e.from_status, e.to_status, e.note, e.created_at,
                           p.full_name AS actor_name
                    FROM {_pg_table('case_form_events')} e
                    LEFT JOIN {_pg_table('profiles')} p ON CAST(p.id AS TEXT) = e.actor_id
                    WHERE e.case_form_id = :form_id
                    ORDER BY e.created_at ASC
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        logger.exception("events: list failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to load events")

    return [
        EventItem(
            id=str(r["id"]),
            case_form_id=str(r["case_form_id"]),
            event_type=str(r["event_type"]),
            actor_id=str(r["actor_id"]) if r.get("actor_id") else None,
            actor_name=r.get("actor_name"),
            from_status=r.get("from_status"),
            to_status=r.get("to_status"),
            note=r.get("note"),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# §5 Shared reads — Form original + filled PDF
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/forms/{form_id}/original")
def get_form_original(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> JSONResponse:
    """
    [P2-4] Return a 1-hour signed URL for the blank template PDF.

    Fetches form_templates.original_pdf_url for this CaseForm's template.
    - If the stored URL is a Supabase Storage path (no http prefix), generates
      a signed URL via the admin storage client.
    - If it is already an http(s) URL, returns it directly.
    - Returns 404 when no original PDF has been attached to the template yet.
    """
    _assert_case_access(user, case_id)

    with main_db.engine.connect() as conn:
        row = conn.execute(
            _sql_text(
                f"""
                SELECT ft.original_pdf_url, ft.code, ft.name
                FROM   {_pg_table('case_forms')} cf
                JOIN   {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
                WHERE  cf.id = :form_id AND cf.case_id = :case_id
                """
            ),
            {"form_id": form_id, "case_id": case_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Form not found")

    original_url: Optional[str] = row.get("original_pdf_url")
    if not original_url:
        raise HTTPException(
            status_code=404,
            detail="No original PDF has been attached to this template yet",
        )

    # Already a public/external URL — return as-is
    if original_url.startswith("http"):
        return JSONResponse({"signedUrl": original_url})

    # Supabase Storage path: "<bucket>/<path/to/file.pdf>"
    # Generate a 1-hour signed URL so the raw bucket URL is never exposed.
    try:
        from ..services.supabase_client import get_supabase_admin_client  # lazy import
        sb = get_supabase_admin_client()
        bucket, _, path = original_url.partition("/")
        signed = sb.storage.from_(bucket).create_signed_url(path, 3600)
        signed_url: Optional[str] = signed.get("signedURL") or signed.get("signedUrl")
        if not signed_url:
            raise HTTPException(status_code=502, detail="Could not generate signed URL for original PDF")
        return JSONResponse({"signedUrl": signed_url})
    except HTTPException:
        raise
    except Exception as exc:  # storage unavailable in dev / missing config
        logger.warning("original pdf signed url error for form %s: %s", form_id, exc)
        raise HTTPException(status_code=502, detail="Storage unavailable — cannot sign original PDF URL")


@router.get("/{case_id}/forms/{form_id}/pdf")
def get_form_pdf(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    [P3-1] Generate (or return a cached) filled PDF for a CaseForm.

    - Fetches the original template PDF from original_file_url.
    - Overlays all FieldValues at their pdf_x/pdf_y/pdf_page coordinates.
    - Stores result to Supabase Storage and caches draft_pdf_url.
    - Returns PDF as a download with a human-readable filename.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.begin() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            # Check if status allows download (not_started → still allow, just empty)
            if form_row.get("status") == "blocked":
                raise HTTPException(
                    status_code=409,
                    detail="Cannot generate PDF for a blocked form",
                )

            # Fetch all current field values
            fv_rows = conn.execute(
                _sql_text(
                    f"SELECT field_id, value FROM {_pg_table('case_form_field_values')} "
                    f"WHERE case_form_id = :form_id AND value IS NOT NULL AND value != ''"
                ),
                {"form_id": form_id},
            ).mappings().all()
            field_values: Dict[str, str] = {
                str(r["field_id"]): str(r["value"]) for r in fv_rows
            }

            # Parse template fields JSON
            raw_fields = form_row.get("template_fields")
            if isinstance(raw_fields, str):
                import json as _json
                template_fields: List[Dict[str, Any]] = _json.loads(raw_fields)
            else:
                template_fields = list(raw_fields) if raw_fields else []

            # Build filename: {form_code}_{last_name}_{first_name}_{date}.pdf
            form_code = _safe_filename_part(form_row.get("template_code") or "form")
            today_str = _dt.date.today().isoformat().replace("-", "")

            # Try to get person name for filename
            person_id = form_row.get("person_id") or form_row.get("dependent_id")
            person_name_slug = "employee"
            if person_id:
                try:
                    name_row = conn.execute(
                        _sql_text(
                            f"SELECT full_name FROM {_pg_table('employees')} "
                            f"WHERE id = :pid LIMIT 1"
                        ),
                        {"pid": person_id},
                    ).mappings().first()
                    if name_row and name_row.get("full_name"):
                        parts = str(name_row["full_name"]).split()
                        if len(parts) >= 2:
                            person_name_slug = (
                                _safe_filename_part(parts[-1])
                                + "_"
                                + _safe_filename_part(parts[0])
                            )
                        else:
                            person_name_slug = _safe_filename_part(parts[0])
                except Exception:
                    pass  # name is cosmetic, don't fail

            filename = f"{form_code}_{person_name_slug}_{today_str}.pdf"

            # Fetch and generate PDF
            original_url = form_row.get("original_file_url")
            if original_url:
                try:
                    resp = _requests.get(original_url, timeout=15)
                    resp.raise_for_status()
                    original_bytes = resp.content
                except Exception as exc:
                    logger.warning(
                        "pdf: failed to fetch original PDF for form %s: %s", form_id, exc
                    )
                    original_bytes = None
            else:
                original_bytes = None

            if original_bytes:
                try:
                    pdf_bytes = _generate_filled_pdf(
                        original_bytes, template_fields, field_values
                    )
                except Exception as exc:
                    logger.exception("pdf: generation failed form_id=%s: %s", form_id, exc)
                    raise HTTPException(
                        status_code=500, detail="PDF generation failed"
                    )
            else:
                # No original PDF — generate a placeholder
                form_name = form_row.get("template_name") or form_code
                pdf_bytes = _make_blank_pdf(
                    title=form_name,
                    message=(
                        "This form has not been uploaded yet. "
                        "Field values captured so far: "
                        + ", ".join(f"{k}: {v}" for k, v in list(field_values.items())[:10])
                    ),
                )

            # Async-friendly: try to cache to storage (non-blocking failure)
            _try_store_draft_pdf(form_id, pdf_bytes, conn)

    except HTTPException:
        raise
    except Exception:
        logger.exception("pdf: unexpected error form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# §5 Shared reads — Dossier package downloads + detail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/dossiers/{dossier_id}/zip")
def get_dossier_zip(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    [P3-5] Generate a ZIP archive of individual filled PDFs for a DossierPackage.

    Each file is named: {NN}_{form_code}_{person_slug}_{date}.pdf
    Returns as application/zip download.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.begin() as conn:
            pkg_row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not pkg_row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            raw_ids = pkg_row["form_ids"]
            if isinstance(raw_ids, str):
                form_ids: List[str] = json.loads(raw_ids)
            else:
                form_ids = list(raw_ids) if raw_ids else []

            if not form_ids:
                raise HTTPException(status_code=422, detail="Dossier has no forms")

            # Build ZIP in memory
            zip_buf = io.BytesIO()
            today_str = _dt.date.today().isoformat().replace("-", "")
            with _zipfile.ZipFile(zip_buf, mode="w", compression=_zipfile.ZIP_DEFLATED) as zf:
                for idx, form_id in enumerate(form_ids, 1):
                    form_row = _load_form_with_template(conn, case_id, form_id)
                    if not form_row:
                        continue
                    form_code = _safe_filename_part(form_row.get("template_code") or "form")
                    pdf_bytes = _fetch_form_pdf_bytes(conn, case_id, form_id)
                    zip_name = f"{idx:02d}_{form_code}_{today_str}.pdf"
                    zf.writestr(zip_name, pdf_bytes)

            zip_buf.seek(0)
            zip_bytes = zip_buf.read()

    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: zip failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to generate ZIP")

    pkg_name = _safe_filename_part(str(pkg_row["name"]))
    zip_filename = f"dossier_{pkg_name}_{_dt.date.today().isoformat().replace('-', '')}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )


# ── [P3-6] List dossiers ──────────────────────────────────────────────────────

@router.get("/{case_id}/dossiers", response_model=List[DossierPackageDetailResponse])
def list_dossiers(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[DossierPackageDetailResponse]:
    """[P3-6] List all DossierPackage records for a case, with staleness flag."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page,
                           pdf_url, generated_at, created_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE case_id = :cid
                    ORDER BY created_at DESC
                    """
                ),
                {"cid": case_id},
            ).mappings().all()

            result = []
            for row in rows:
                raw_ids = row["form_ids"]
                form_ids: List[str] = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
                is_stale = _dossier_is_stale(conn, form_ids, row.get("generated_at"))
                result.append(
                    DossierPackageDetailResponse(
                        id=str(row["id"]),
                        case_id=str(row["case_id"]),
                        name=str(row["name"]),
                        form_ids=form_ids,
                        cover_page=bool(row["cover_page"]),
                        pdf_url=row.get("pdf_url"),
                        generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
                        created_at=str(row["created_at"]),
                        is_stale=is_stale,
                    )
                )
            return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list dossiers")


# ── [P3-6] Get one dossier ────────────────────────────────────────────────────

@router.get("/{case_id}/dossiers/{dossier_id}", response_model=DossierPackageDetailResponse)
def get_dossier(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> DossierPackageDetailResponse:
    """[P3-6] Get a single DossierPackage with staleness flag."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page,
                           pdf_url, generated_at, created_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            raw_ids = row["form_ids"]
            form_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            is_stale = _dossier_is_stale(conn, form_ids, row.get("generated_at"))

            return DossierPackageDetailResponse(
                id=str(row["id"]),
                case_id=str(row["case_id"]),
                name=str(row["name"]),
                form_ids=form_ids,
                cover_page=bool(row["cover_page"]),
                pdf_url=row.get("pdf_url"),
                generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
                created_at=str(row["created_at"]),
                is_stale=is_stale,
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: get failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to get dossier")


# ── [P3-6] Download merged PDF ────────────────────────────────────────────────

@router.get("/{case_id}/dossiers/{dossier_id}/pdf")
def get_dossier_pdf(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    [P3-6] Download the merged PDF for a DossierPackage.
    If pdf_url is set, redirect/stream it; otherwise regenerate on-the-fly.
    """
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page, pdf_url, generated_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            # If we have a stored PDF, stream it from storage
            pdf_url = row.get("pdf_url")
            if pdf_url:
                try:
                    resp = _requests.get(pdf_url, timeout=15)
                    if resp.ok:
                        pkg_name = _safe_filename_part(str(row["name"]))
                        filename = f"dossier_{pkg_name}.pdf"
                        return Response(
                            content=resp.content,
                            media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                        )
                except Exception:
                    logger.warning("dossier: failed to fetch stored PDF, regenerating dossier_id=%s", dossier_id)

            # Fallback: regenerate merged PDF on-the-fly
            raw_ids = row["form_ids"]
            form_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            if not form_ids:
                raise HTTPException(status_code=422, detail="Dossier has no forms")

            pdf_parts: List[bytes] = []

            if row["cover_page"]:
                cover_meta: List[Dict[str, Any]] = []
                for fid in form_ids:
                    fr = _load_form_with_template(conn, case_id, fid)
                    if fr:
                        cover_meta.append({
                            "code": fr.get("template_code"),
                            "name": fr.get("template_name"),
                            "authority_code": fr.get("authority_code"),
                        })
                pdf_parts.append(_build_cover_page(str(row["name"]), case_id, cover_meta))

            for fid in form_ids:
                fr = _load_form_with_template(conn, case_id, fid)
                if fr:
                    pdf_parts.append(
                        _build_divider_page(
                            str(fr.get("template_code") or ""),
                            str(fr.get("template_name") or ""),
                            fr.get("authority_name"),
                        )
                    )
                pdf_parts.append(_fetch_form_pdf_bytes(conn, case_id, fid))

            merged = _merge_pdfs(pdf_parts)
            pkg_name = _safe_filename_part(str(row["name"]))
            filename = f"dossier_{pkg_name}.pdf"
            return Response(
                content=merged,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: pdf download failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to download dossier PDF")


# ─────────────────────────────────────────────────────────────────────────────
# §5 Shared reads — Budget summary, messages, vendors, budget lines
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/budget-summary")
def get_budget_summary(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return HR-policy budget caps vs. the services selected for this case.
    Employees and HR can call this; the caller must be linked to a company.

    AUDIT-A2-followup: access is gated by _assert_case_access — employees must
    own the case, HR must belong to the same company, admins always pass.
    Returns 404 for missing cases and 403 for cross-company / cross-tenant
    access attempts. Mirrors the pattern from get_case / patch_case /
    list_case_forms.
    """
    _assert_case_access(user, case_id)

    # Resolve company from profile
    profile = main_db.get_profile_record(user.get("id"))
    company_id: str = (profile or {}).get("company_id") or user.get("company") or ""

    # Pull selected services from the case draft_json
    selected_services: List[str] = []
    try:
        with SessionLocal() as db_sess:
            case = crud.get_case(db_sess, case_id)
        if case:
            draft = json.loads(case.draft_json or "{}")
            selected_services = draft.get("services", [])
    except Exception:
        pass

    # Pull published HR policy budget caps
    categories: List[Dict[str, Any]] = []
    if company_id:
        try:
            policies = main_db.list_hr_policies_by_company(company_id)
            published = next(
                (p for p in policies if (p.get("status") or "").lower() == "published"),
                None,
            )
            if published:
                policy_data = json.loads(published.get("policy_json") or "{}")
                # Try common key variants for budget caps
                caps = (
                    policy_data.get("budget_caps")
                    or policy_data.get("categories")
                    or {}
                )
                if isinstance(caps, dict):
                    for svc, cap in caps.items():
                        categories.append({
                            "name": svc,
                            "cap_amount": cap.get("amount") if isinstance(cap, dict) else cap,
                            "cap_currency": (cap.get("currency", "EUR") if isinstance(cap, dict) else "EUR"),
                            "estimated_amount": None,
                            "status": "within_budget",
                        })
        except Exception:
            logger.exception("budget-summary: failed to read policy company=%s", company_id)

    # Fall back: return selected services with no_cap when no policy exists
    if not categories:
        for svc in (selected_services or ["housing", "moving", "immigration"]):
            categories.append({
                "name": svc,
                "cap_amount": None,
                "cap_currency": "EUR",
                "estimated_amount": None,
                "status": "no_cap",
            })

    return {"case_id": case_id, "categories": categories}


@router.get("/{case_id}/messages")
def list_case_messages(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return the full message thread for a case, oldest-first.
    """
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    """
                    SELECT * FROM public.case_messages
                    WHERE case_id = :case_id
                    ORDER BY created_at ASC
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
    except Exception:
        logger.exception("messages: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list messages")

    result = []
    for row in rows:
        d = dict(row)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                try:
                    d[k] = v.isoformat()
                except Exception:
                    d[k] = str(v)
        result.append({
            "id": str(d["id"]),
            "case_id": str(d["case_id"]),
            "sender_id": str(d["sender_id"]),
            "sender_role": d["sender_role"],
            "content": d["content"],
            "created_at": d["created_at"],
        })
    return result


# ---------------------------------------------------------------------------
# T11 – Vendor Display (MVP-7)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/vendors")
def list_case_vendors(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return vendors assigned to the case from case_vendor_shortlist joined with
    the vendors table.  Available to HR and ADMIN roles.
    """
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    """
                    SELECT
                        cvs.id            AS shortlist_id,
                        cvs.service_key   AS category,
                        cvs.status,
                        cvs.contact_name,
                        cvs.contact_email,
                        v.name            AS vendor_name,
                        v.website         AS vendor_website
                    FROM public.case_vendor_shortlist cvs
                    LEFT JOIN public.vendors v ON v.id = cvs.vendor_id
                    WHERE cvs.case_id = :case_id
                    ORDER BY cvs.service_key, v.name
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
    except Exception:
        logger.exception("vendors: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list vendors")

    result = []
    for row in rows:
        d = dict(row)
        result.append({
            "shortlist_id": str(d["shortlist_id"]) if d.get("shortlist_id") else None,
            "category": d.get("category"),
            "status": d.get("status", "Assigned"),
            "contact_name": d.get("contact_name"),
            "contact_email": d.get("contact_email"),
            "vendor_name": d.get("vendor_name"),
            "vendor_website": d.get("vendor_website"),
        })
    return result


# ---------------------------------------------------------------------------
# T12 – Budget View (MVP-7)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/budget-lines")
def list_case_budget_lines(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return budget line items for the case.  Available to HR and ADMIN roles.
    """
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    """
                    SELECT
                        id,
                        case_id,
                        category,
                        estimated_eur,
                        created_at
                    FROM public.case_budget_lines
                    WHERE case_id = :case_id
                    ORDER BY category
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
    except Exception:
        logger.exception("budget-lines: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list budget lines")

    result = []
    for row in rows:
        d = dict(row)
        result.append({
            "id": str(d["id"]),
            "case_id": str(d["case_id"]),
            "category": d.get("category"),
            "estimated_eur": float(d["estimated_eur"]) if d.get("estimated_eur") is not None else 0.0,
            "created_at": d["created_at"].isoformat() if hasattr(d.get("created_at"), "isoformat") else str(d.get("created_at", "")),
        })
    return result

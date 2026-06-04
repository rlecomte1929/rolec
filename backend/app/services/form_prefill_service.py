"""
form_prefill_service.py — IMM-11

Immigration form library + PDF pre-fill.

Public API:
  get_available_forms(corridor_to, visa_type) -> List[FormDefinition]
      Forms that can be pre-filled for a corridor/visa combination.

  generate_prefilled_pdf(form_id, case_id, employee_profile) -> PrefilledPdfResult
      Read the blank AcroForm template from Supabase Storage (bucket
      "form-templates"), map vault fields via form_field_mappings, fill the
      AcroForm fields with pypdf applying each field's format_rule, store the
      output in Supabase Storage (bucket "case-documents",
      {case_id}/prefilled/{form_id}.pdf) and return a time-limited signed
      download URL plus a field_fill_report.

The pure helpers (build_fill_plan, fill_acroform, apply_format_rule) carry the
testable logic and have no DB / Storage dependency. build_synthetic_acroform is
a seed/test helper that generates a stand-in AcroForm template with named
fields (used until the real government PDFs are uploaded).
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from ...database import db

log = logging.getLogger(__name__)

# Storage buckets (per IMM-11 spec).
TEMPLATE_BUCKET = "form-templates"
OUTPUT_BUCKET = "case-documents"

# How long the returned download URL stays valid.
SIGNED_URL_TTL_SECONDS = 3600

# Fill-report status values.
STATUS_FILLED = "filled"
STATUS_BLANK = "blank_missing_data"
STATUS_WARNING = "warning"


@dataclass
class FormDefinition:
    form_id: str
    form_name: str
    corridor_to: str
    visa_type: str
    field_count: int
    form_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "form_id": self.form_id,
            "form_name": self.form_name,
            "corridor_to": self.corridor_to,
            "visa_type": self.visa_type,
            "field_count": self.field_count,
            "form_url": self.form_url,
        }


@dataclass
class FieldFillStatus:
    form_field_id: str
    vault_field_path: str
    label: Optional[str]
    status: str                       # STATUS_FILLED | STATUS_BLANK | STATUS_WARNING
    value: Optional[str] = None
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "form_field_id": self.form_field_id,
            "vault_field_path": self.vault_field_path,
            "label": self.label,
            "status": self.status,
            "value": self.value,
            "warning": self.warning,
        }


@dataclass
class PrefilledPdfResult:
    form_id: str
    case_id: str
    storage_path: str
    download_url: Optional[str]
    field_fill_report: List[FieldFillStatus] = dc_field(default_factory=list)
    pdf_bytes: bytes = b""

    @property
    def filled_count(self) -> int:
        return sum(1 for f in self.field_fill_report if f.status != STATUS_BLANK)

    @property
    def blank_count(self) -> int:
        return sum(1 for f in self.field_fill_report if f.status == STATUS_BLANK)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.field_fill_report if f.status == STATUS_WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "form_id": self.form_id,
            "case_id": self.case_id,
            "storage_path": self.storage_path,
            "download_url": self.download_url,
            "filled_count": self.filled_count,
            "blank_count": self.blank_count,
            "warning_count": self.warning_count,
            "fields": [f.to_dict() for f in self.field_fill_report],
        }


# ---------------------------------------------------------------------------
# Format rules
# ---------------------------------------------------------------------------

def apply_format_rule(value: Any, rule: Optional[str]) -> str:
    """Coerce a raw vault value to the string a form field expects.

    Supported rules: uppercase, name_normalise, passport_format,
    dd/mm/yyyy, yyyy-mm-dd. Unknown/empty rules fall through to a plain str().
    """
    if isinstance(value, bool):
        s = "Yes" if value else "No"
    else:
        s = str(value)
    s = s.strip()

    if not rule:
        return s

    rule = rule.strip().lower()
    if rule == "uppercase":
        return s.upper()
    if rule == "name_normalise":
        # Collapse internal whitespace; preserve diacritics and casing.
        return re.sub(r"\s+", " ", s).strip()
    if rule == "passport_format":
        return re.sub(r"\s+", "", s).upper()
    if rule in ("dd/mm/yyyy", "yyyy-mm-dd"):
        parsed = _parse_date(s)
        if parsed is None:
            return s
        return parsed.strftime("%d/%m/%Y") if rule == "dd/mm/yyyy" else parsed.strftime("%Y-%m-%d")
    return s


def _parse_date(s: str) -> Optional[date]:
    candidate = s[:10]
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                from datetime import datetime as _dt
                return _dt.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


# Characters that survive a copy/paste but commonly get mangled in official
# transcription (apostrophes, accented letters, hyphens). On a field flagged
# exact_match_required we surface these for a human double-check.
_SPECIAL_CHARS = re.compile(r"[^A-Za-z0-9 .,/]")


def _exact_match_warning(rendered: str) -> Optional[str]:
    if _SPECIAL_CHARS.search(rendered):
        return (
            "Contains special characters (e.g. apostrophe or accent). This field "
            "must exactly match the official document — please verify."
        )
    return None


# ---------------------------------------------------------------------------
# Pure fill planning
# ---------------------------------------------------------------------------

def build_fill_plan(
    mappings: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> Tuple[Dict[str, str], List[FieldFillStatus]]:
    """Resolve every mapping against the vault profile.

    Returns (field_values, report):
      field_values — {form_field_id: rendered_value} for fields that have data
      report       — one FieldFillStatus per mapping
    """
    field_values: Dict[str, str] = {}
    report: List[FieldFillStatus] = []

    for m in mappings:
        form_field_id = m["form_field_id"]
        vault_path = m["vault_field_path"]
        label = m.get("form_field_label")
        rule = m.get("format_rule")
        exact = bool(m.get("exact_match_required"))

        raw = profile.get(vault_path)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            report.append(FieldFillStatus(
                form_field_id=form_field_id,
                vault_field_path=vault_path,
                label=label,
                status=STATUS_BLANK,
                value=None,
            ))
            continue

        rendered = apply_format_rule(raw, rule)
        max_length = m.get("max_length")
        if isinstance(max_length, int) and max_length > 0:
            rendered = rendered[:max_length]

        field_values[form_field_id] = rendered

        warning = _exact_match_warning(rendered) if exact else None
        report.append(FieldFillStatus(
            form_field_id=form_field_id,
            vault_field_path=vault_path,
            label=label,
            status=STATUS_WARNING if warning else STATUS_FILLED,
            value=rendered,
            warning=warning,
        ))

    return field_values, report


# ---------------------------------------------------------------------------
# AcroForm filling (pypdf)
# ---------------------------------------------------------------------------

def fill_acroform(template_bytes: bytes, field_values: Dict[str, str]) -> bytes:
    """Fill the AcroForm fields of a PDF template and return the new PDF bytes."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(template_bytes))
    writer = PdfWriter()
    writer.append(reader)

    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, field_values)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("update_page_form_field_values failed on a page: %s", exc)

    # Ask viewers to regenerate field appearances so the values render.
    try:
        writer.set_need_appearances_writer(True)
    except Exception:  # pragma: no cover - older pypdf signature
        try:
            writer.set_need_appearances_writer()
        except Exception:
            pass

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------

def get_available_forms(corridor_to: str, visa_type: str) -> List[FormDefinition]:
    """Forms with at least one field mapping for this corridor/visa combination."""
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT form_id, form_name, corridor_to, visa_type,
                       MAX(form_url) AS form_url, COUNT(*) AS field_count
                FROM public.form_field_mappings
                WHERE corridor_to = :corridor_to AND visa_type = :visa_type
                GROUP BY form_id, form_name, corridor_to, visa_type
                ORDER BY form_name
            """),
            {"corridor_to": corridor_to, "visa_type": visa_type},
        ).mappings().all()

    return [
        FormDefinition(
            form_id=r["form_id"],
            form_name=r["form_name"],
            corridor_to=r["corridor_to"],
            visa_type=r["visa_type"],
            field_count=int(r["field_count"]),
            form_url=r["form_url"],
        )
        for r in rows
    ]


def _load_field_mappings(form_id: str) -> List[Dict[str, Any]]:
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT form_field_id, form_field_label, vault_field_path,
                       format_rule, exact_match_required, max_length
                FROM public.form_field_mappings
                WHERE form_id = :form_id
                ORDER BY form_field_id
            """),
            {"form_id": form_id},
        ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Supabase Storage
# ---------------------------------------------------------------------------

def _download_template(form_id: str) -> bytes:
    from .supabase_client import get_supabase_admin_client
    sb = get_supabase_admin_client()
    return sb.storage.from_(TEMPLATE_BUCKET).download(f"{form_id}.pdf")


def _upload_output(case_id: str, form_id: str, pdf_bytes: bytes) -> str:
    from .supabase_client import get_supabase_admin_client
    sb = get_supabase_admin_client()
    path = f"{case_id}/prefilled/{form_id}.pdf"
    sb.storage.from_(OUTPUT_BUCKET).upload(
        path,
        pdf_bytes,
        {"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def _signed_url(path: str) -> Optional[str]:
    from .supabase_client import get_supabase_admin_client
    sb = get_supabase_admin_client()
    signed = sb.storage.from_(OUTPUT_BUCKET).create_signed_url(path, SIGNED_URL_TTL_SECONDS)
    if isinstance(signed, dict):
        return signed.get("signedURL") or signed.get("signedUrl")
    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def generate_prefilled_pdf(
    form_id: str,
    case_id: str,
    employee_profile: Dict[str, Any],
) -> PrefilledPdfResult:
    """Fill `form_id` for `case_id` from `employee_profile` and store the PDF.

    Raises ValueError if the form has no field mappings.
    """
    mappings = _load_field_mappings(form_id)
    if not mappings:
        raise ValueError(f"No field mappings found for form_id '{form_id}'.")

    field_values, report = build_fill_plan(mappings, employee_profile)

    template_bytes = _download_template(form_id)
    pdf_bytes = fill_acroform(template_bytes, field_values)

    storage_path = _upload_output(case_id, form_id, pdf_bytes)
    download_url = _signed_url(storage_path)

    return PrefilledPdfResult(
        form_id=form_id,
        case_id=case_id,
        storage_path=storage_path,
        download_url=download_url,
        field_fill_report=report,
        pdf_bytes=pdf_bytes,
    )


# ---------------------------------------------------------------------------
# Seed / test helper — synthetic AcroForm template
# ---------------------------------------------------------------------------

def build_synthetic_acroform(field_ids: List[str], title: str = "Synthetic immigration form") -> bytes:
    """Generate a stand-in AcroForm PDF containing a text field per field_id.

    Used by the seed/upload script and tests until the real government PDFs are
    available. The field NAMES match form_field_mappings.form_field_id so the
    same fill pipeline works unchanged when real templates replace these.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    form = c.acroForm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(56, height - 56, title)

    y = height - 96
    c.setFont("Helvetica", 9)
    for fid in field_ids:
        if y < 80:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = height - 80
        c.drawString(56, y + 3, fid)
        form.textfield(
            name=fid,
            x=240,
            y=y - 4,
            width=300,
            height=16,
            borderStyle="inset",
            forceBorder=True,
            fontSize=9,
        )
        y -= 28

    c.save()
    return buf.getvalue()

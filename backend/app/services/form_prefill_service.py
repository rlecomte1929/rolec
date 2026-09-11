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
# The vault had a value but it did NOT land in the PDF — almost always because the mapping's
# form_field_id doesn't match any AcroForm field name in the template. Reported honestly rather
# than counted as filled; see reconcile_report_against_pdf.
STATUS_NOT_IN_PDF = "not_in_pdf"


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
        # Only what genuinely reached the PDF. Was `!= STATUS_BLANK`, which counted a field
        # whose name doesn't exist in the template as a success.
        return sum(
            1 for f in self.field_fill_report
            if f.status in (STATUS_FILLED, STATUS_WARNING)
        )

    @property
    def not_in_pdf_count(self) -> int:
        return sum(1 for f in self.field_fill_report if f.status == STATUS_NOT_IN_PDF)

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
            # Mapped fields whose name doesn't exist in the template, so nothing was written.
            "not_in_pdf_count": self.not_in_pdf_count,
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
# Choice groups — value → which radio/checkbox button to tick
# ---------------------------------------------------------------------------
# Some AcroForm fields are not text but a GROUP of independent checkboxes, one per
# option (FR CERFA: applicantGenderM/F/Other; applicantMaritalCEL/MAR/SEP/DIV/VEU/AUT).
# A single vault value (gender, marital_status) selects exactly ONE button — which the
# scalar text pipeline (build_fill_plan) cannot express. These map a normalised vault
# value to the one button to tick.

# Sentinel meaning "tick this checkbox". build_choice_fill emits it; fill_acroform translates it
# to the field's REAL on-state read from the template (_resolve_checkbox_states), because the
# on-state is template-specific — the real FR CERFA uses /On, reportlab synthetic forms use /Yes.
# The value is "/Yes" only so a synthetic-form fill still lands if resolution is somehow skipped.
CHECKBOX_ON = "/Yes"


def _norm_choice(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


# Vault value → canonical option code. Tolerant of English/French and common synonyms.
_GENDER_CODES = {
    "m": "M", "male": "M", "man": "M", "homme": "M", "h": "M", "masculin": "M",
    "f": "F", "female": "F", "woman": "F", "femme": "F", "feminin": "F", "féminin": "F",
}
_MARITAL_CODES = {
    "single": "SINGLE", "celibataire": "SINGLE", "célibataire": "SINGLE", "unmarried": "SINGLE",
    "married": "MARRIED", "marie": "MARRIED", "marié": "MARRIED", "mariee": "MARRIED", "mariée": "MARRIED",
    "separated": "SEPARATED", "separe": "SEPARATED", "séparé": "SEPARATED",
    "divorced": "DIVORCED", "divorce": "DIVORCED", "divorcé": "DIVORCED",
    "widowed": "WIDOWED", "widow": "WIDOWED", "widower": "WIDOWED", "veuf": "WIDOWED", "veuve": "WIDOWED",
}


def _canonical_choice(vault_path: str, value: Any) -> Optional[str]:
    n = _norm_choice(value)
    if vault_path == "gender":
        return _GENDER_CODES.get(n, "OTHER")
    if vault_path == "marital_status":
        return _MARITAL_CODES.get(n, "OTHER")
    return None


# form_id → vault_field_path → { canonical option code → button form_field_id }.
# The button ids are the real FR CERFA AcroForm names (docs/form-autofill/artifacts/
# fr_cerfa_14571-05_acroform_fields.json). Add a form's groups here to make its radios fillable.
CHOICE_GROUPS: Dict[str, Dict[str, Dict[str, str]]] = {
    "FR_cerfa_14571_v2024": {
        "gender": {
            "M": "applicantGenderM",
            "F": "applicantGenderF",
            "OTHER": "applicantGenderOther",
        },
        "marital_status": {
            "SINGLE": "applicantMaritalCEL",
            "MARRIED": "applicantMaritalMAR",
            "SEPARATED": "applicantMaritalSEP",
            "DIVORCED": "applicantMaritalDIV",
            "WIDOWED": "applicantMaritalVEU",
            "OTHER": "applicantMaritalAUT",
        },
    },
}


def build_choice_fill(
    form_id: str,
    profile: Dict[str, Any],
) -> Tuple[Dict[str, str], List[FieldFillStatus]]:
    """Resolve the radio/checkbox GROUPS declared for ``form_id`` from the vault profile.

    Returns (button_values, report): ``button_values`` ticks exactly the selected button
    (``{button_field_id: CHECKBOX_ON}``) and leaves the rest of the group untouched (so they
    stay unchecked); ``report`` carries one row per group. A group whose vault value is missing
    is reported STATUS_BLANK and ticks nothing — never guess a protected attribute.
    """
    groups = CHOICE_GROUPS.get(form_id, {})
    button_values: Dict[str, str] = {}
    report: List[FieldFillStatus] = []

    for vault_path, code_to_button in groups.items():
        raw = profile.get(vault_path)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            report.append(FieldFillStatus(
                form_field_id=code_to_button.get("OTHER") or next(iter(code_to_button.values())),
                vault_field_path=vault_path, label=vault_path, status=STATUS_BLANK, value=None,
            ))
            continue
        code = _canonical_choice(vault_path, raw)
        button = code_to_button.get(code) or code_to_button.get("OTHER")
        if not button:
            continue
        button_values[button] = CHECKBOX_ON
        report.append(FieldFillStatus(
            form_field_id=button, vault_field_path=vault_path, label=vault_path,
            status=STATUS_FILLED, value=code,
        ))

    return button_values, report


# ---------------------------------------------------------------------------
# AcroForm filling (pypdf)
# ---------------------------------------------------------------------------

class TemplateNotFillableError(RuntimeError):
    """The template has no AcroForm, so nothing can be pre-filled into it.

    Raised instead of returning the blank template. Previously a flattened or scanned PDF made
    ``update_page_form_field_values`` raise per page into a bare ``except``, and the caller
    received a byte-identical copy of the blank form together with a report claiming every field
    was filled — an empty PDF served as a successful fill, with a working download link.
    """


def _checkbox_on_state(field: Any) -> Optional[str]:
    """The 'checked' export value of a checkbox field, read from the template — the first of its
    states that is not /Off. None if the field isn't a checkbox or exposes no states."""
    if not isinstance(field, dict) or field.get("/FT") != "/Btn":
        return None
    for state in field.get("/_States_") or []:
        if state != "/Off":
            return state
    return None


def _resolve_checkbox_states(
    field_values: Dict[str, str],
    template_fields: Dict[str, Any],
) -> Dict[str, str]:
    """Rewrite the CHECKBOX_ON sentinel to each checkbox's real on-state (from the template).

    Leaves text values and non-checkbox fields untouched; if a checkbox exposes no resolvable
    on-state the sentinel is left as-is (reconcile_report_against_pdf then flags it honestly
    rather than the caller assuming a tick that never landed)."""
    resolved = dict(field_values)
    for name, value in field_values.items():
        if value != CHECKBOX_ON:
            continue
        on = _checkbox_on_state(template_fields.get(name))
        if on:
            resolved[name] = on
    return resolved


def fill_acroform(template_bytes: bytes, field_values: Dict[str, str]) -> bytes:
    """Fill the AcroForm fields of a PDF template and return the new PDF bytes.

    Raises TemplateNotFillableError when the template carries no AcroForm fields — see
    docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md, where 4 of 5 official French candidates
    turned out to be flattened print forms.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(template_bytes))

    # Fail closed BEFORE writing anything: a template with no fields can never be filled, and
    # silently returning it looks identical to success.
    try:
        template_fields = reader.get_fields() or {}
    except Exception as exc:  # noqa: BLE001 — a malformed AcroForm is also "not fillable"
        raise TemplateNotFillableError(f"template AcroForm unreadable: {exc}") from exc
    if not template_fields:
        raise TemplateNotFillableError(
            "template has no AcroForm fields (flattened or scanned PDF) — it cannot be "
            "pre-filled; nothing was written"
        )

    # Resolve checkbox on-states. build_choice_fill emits the CHECKBOX_ON sentinel to mean "tick
    # this box"; the actual on-state is template-specific (the real FR CERFA uses /On, reportlab
    # /Yes, others vary). Translate the sentinel to THIS field's real on-state so the tick lands;
    # a hardcoded value silently misses (update_page_form_field_values drops an unknown state).
    field_values = _resolve_checkbox_states(field_values, template_fields)

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


def reconcile_report_against_pdf(
    pdf_bytes: bytes,
    report: List["FieldFillStatus"],
) -> "tuple[List[FieldFillStatus], int, int]":
    """Re-read the written PDF and downgrade any field that didn't actually land.

    ``build_fill_plan`` decides ``filled`` from the VAULT, before the PDF is opened, and
    ``update_page_form_field_values`` drops unmatched field names without raising. So a mapping
    whose ``form_field_id`` doesn't match the template produced a confident ``filled`` for a
    field that is blank in the delivered document. This is the check that makes the report mean
    what it says.

    Returns (report, pdf_field_count, unmapped_pdf_field_count). Never raises: if the PDF can't
    be re-read the report is returned untouched — a verification failure must not lose the fill.
    """
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pdf_fields = reader.get_fields() or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("fill verification skipped — could not re-read output PDF: %s", exc)
        return report, 0, 0

    def _written(name: str) -> bool:
        entry = pdf_fields.get(name)
        if entry is None:
            return False
        v = entry.get("/V")
        return v is not None and str(v).strip() != ""

    mapped = set()
    for item in report:
        if item.status in (STATUS_FILLED, STATUS_WARNING):
            mapped.add(item.form_field_id)
            if not _written(item.form_field_id):
                item.status = STATUS_NOT_IN_PDF
                item.warning = (
                    (item.warning + " | " if item.warning else "")
                    + f"'{item.form_field_id}' is not a field in this template — value not written"
                )

    unmapped = len([n for n in pdf_fields if n not in mapped])
    if any(i.status == STATUS_NOT_IN_PDF for i in report):
        log.error(
            "prefill: %d mapped field(s) did not land in the PDF — mapping names likely do not "
            "match the template (%d of %d template fields unmapped)",
            sum(1 for i in report if i.status == STATUS_NOT_IN_PDF), unmapped, len(pdf_fields),
        )
    return report, len(pdf_fields), unmapped


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------

def visa_types_for_corridor(corridor_to: str) -> List[str]:
    """Visa types that actually have mapped forms for this corridor.

    [AIQ-1771] The catalogue is data, not a constant: prod carries
    ``DE/blue_card`` and ``FR/long_stay``, so the visa type is corridor-specific
    and cannot be defaulted. Callers use this to resolve the visa type instead of
    assuming one:

      * exactly one  -> use it
      * none         -> this corridor has no fillable form (e.g. Norway, which is
                        a portal/data-sheet corridor) — an empty form list is the
                        correct answer, not an error
      * more than one -> genuinely ambiguous; the caller must specify

    Sorted for deterministic behaviour when a corridor grows a second type.
    """
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT DISTINCT visa_type
                FROM public.form_field_mappings
                WHERE corridor_to = :corridor_to
                ORDER BY visa_type
            """),
            {"corridor_to": corridor_to},
        ).mappings().all()
    return [r["visa_type"] for r in rows]


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

    # Radio/checkbox groups (gender, marital status) — one vault value ticks one button.
    choice_values, choice_report = build_choice_fill(form_id, employee_profile)
    field_values.update(choice_values)
    report.extend(choice_report)

    template_bytes = _download_template(form_id)
    pdf_bytes = fill_acroform(template_bytes, field_values)

    # Verify against the DELIVERED document, not the plan. Without this the report reflects
    # only what the vault held, so a name mismatch reads as a complete fill.
    report, _pdf_field_count, _unmapped = reconcile_report_against_pdf(pdf_bytes, report)

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

def build_synthetic_acroform(
    field_ids: List[str],
    title: str = "Synthetic immigration form",
    checkbox_ids: Optional[List[str]] = None,
) -> bytes:
    """Generate a stand-in AcroForm PDF: a text field per ``field_ids`` plus a checkbox per
    ``checkbox_ids`` (the choice-group buttons — see build_choice_fill). Its checkboxes use the
    reportlab default on-state ``/Yes`` (== CHECKBOX_ON).

    Used by the seed/upload script and tests until the real government PDFs are available. The
    field NAMES match form_field_mappings.form_field_id / the CHOICE_GROUPS button ids so the
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

    for cid in checkbox_ids or []:
        if y < 80:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = height - 80
        c.drawString(56, y + 3, cid)
        form.checkbox(
            name=cid,
            x=240,
            y=y - 4,
            size=14,
            borderStyle="solid",
            forceBorder=True,
            checked=False,
        )
        y -= 28

    c.save()
    return buf.getvalue()

"""Personal relocation data sheet — the employee's takeaway artifact (AIQ-1759).

For corridors with no fillable government form (FR→NO, and DE per the AcroForm feasibility
check in ``docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md``), the deliverable is NOT a
submit-ready official PDF. It is a sheet of the employee's own data, organised by the authority
that asks for it, which they carry to the appointment and copy into the portal.

This replaces a placeholder that rendered two lines of Helvetica containing a comma-joined dump
of at most ten ``snake_case_id: value`` pairs.

Deliberate properties:

* **Sectioned by authority**, in template order — the sheet reads as the sequence of
  appointments it actually is.
* **Unanswered fields are shown, not omitted.** The sheet doubles as a checklist; hiding a gap
  would make it look complete when it isn't.
* **Consult-professional determinations carry no value**, matching the on-screen treatment —
  ReloPass never pre-fills tax residency, A1, contract classification, shadow payroll or PE.
* **Never claims to be an official form.** The header says what it is and the footer repeats the
  confirm-with-the-authority line.

Typography note: `DESIGN.md` specifies Inter, which is not among reportlab's built-in fonts and
is not worth shipping a TTF for here — Helvetica is the metric-compatible stand-in. The navy
(#0b2b43) and accent teal (#1f8e8b) brand colours ARE honoured.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from .localised_labels import localised_label

log = logging.getLogger(__name__)

_NAVY = "#0b2b43"
_ACCENT = "#1f8e8b"
_MUTED = "#4a5f73"     # --marketing-text-muted; ~7:1 on white
_AMBER = "#92400e"
_RULE = "#d7dee6"

# Machine section keys → the authority that issues the step. Mirrors SECTION_LABELS in
# frontend/src/pages/employee/FormEditorPage.tsx; keep the two in step.
_SECTION_LABELS = {
    "d_number": "D-number (Skatteetaten)",
    "skattekort": "Tax card / skattekort (Skatteetaten)",
    "eea_registration": "EEA registration (Politiet)",
    "folkeregister": "National registry / folkeregister (Skatteetaten)",
    "a1": "A1 social-security certificate",
}

# case_form_field_values.source → what the employee is told about where a value came from.
# Mirrors SOURCE_META in frontend/src/features/platform-v2/form-editor/FieldRow.tsx.
_SOURCE_LABELS = {
    "intake_profile": "From your intake",
    "contract": "From your contract",
    "banking": "From your banking details",
    "passport_ocr": "From your passport scan",
    "prior_form": "From an earlier form",
    "authority_lookup": "From an authority lookup",
    "ai": "AI suggestion — please check",
}


def _section_label(key: str) -> str:
    if not key:
        return "Your details"
    named = _SECTION_LABELS.get(key)
    if named:
        return named
    spaced = key.replace("_", " ").replace("-", " ").strip()
    return spaced[:1].upper() + spaced[1:]


def render_data_sheet(
    *,
    title: str,
    fields: List[Dict[str, Any]],
    values: Dict[str, str],
    sources: Optional[Dict[str, str]] = None,
    subtitle: Optional[str] = None,
    source_language: Optional[str] = None,
    sections: Optional[List[Dict[str, Any]]] = None,
) -> Optional[bytes]:
    """Render the data sheet, or None when reportlab is unavailable.

    Returning None rather than raising lets the caller fall back to its existing placeholder —
    a missing optional dependency must not turn a download into a 500.

    `source_language` is the template's own language (`form_templates.source_language`). When it
    names a language we seed labels for, each field prints its localised label under the English
    one — so the employee can match what they read here against what the authority's counter
    actually says. Defaults to None (English only), which is also what an older caller that does
    not pass it gets.

    `sections` is the template's `form_templates.sections` array. When non-empty it IS the
    layout — its order is display order, each entry supplies its own title, and its `field_ids`
    select the fields. Omit it (or pass an empty list) and the sheet falls back to grouping by
    `fields[].section` with the titles in `_SECTION_LABELS`, which is what every template except
    RP-NO-DATASHEET does today.
    """
    try:
        from reportlab.lib import colors as _colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
        )
    except ImportError:  # pragma: no cover - reportlab is in requirements
        log.warning("data_sheet_pdf: reportlab unavailable, falling back to placeholder")
        return None

    import io

    sources = sources or {}

    s_title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16, leading=20,
                             textColor=_colors.HexColor(_NAVY), alignment=TA_LEFT)
    s_sub = ParagraphStyle("s", fontName="Helvetica", fontSize=9.5, leading=13,
                           textColor=_colors.HexColor(_MUTED), spaceBefore=3)
    s_section = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                               textColor=_colors.HexColor(_NAVY), spaceBefore=14, spaceAfter=2)
    s_label = ParagraphStyle("l", fontName="Helvetica-Bold", fontSize=9, leading=12,
                             textColor=_colors.HexColor(_NAVY), spaceBefore=7)
    s_label_localised = ParagraphStyle("lloc", fontName="Helvetica-Oblique", fontSize=8, leading=11,
                                       textColor=_colors.HexColor(_MUTED))
    s_value = ParagraphStyle("v", fontName="Helvetica", fontSize=10.5, leading=14,
                             textColor=_colors.HexColor("#1f2937"), spaceBefore=1)
    s_missing = ParagraphStyle("m", fontName="Helvetica-Oblique", fontSize=10, leading=14,
                               textColor=_colors.HexColor(_MUTED), spaceBefore=1)
    s_consult = ParagraphStyle("c", fontName="Helvetica-Oblique", fontSize=9, leading=12,
                               textColor=_colors.HexColor(_AMBER), spaceBefore=1)
    s_meta = ParagraphStyle("meta", fontName="Helvetica", fontSize=7.5, leading=10,
                            textColor=_colors.HexColor(_MUTED), spaceBefore=1)
    s_note = ParagraphStyle("n", fontName="Helvetica", fontSize=8, leading=11,
                            textColor=_colors.HexColor(_MUTED), spaceBefore=2)
    s_link = ParagraphStyle("lk", fontName="Helvetica", fontSize=8, leading=11,
                            textColor=_colors.HexColor(_ACCENT), spaceBefore=1)

    story: List[Any] = [
        Paragraph(escape(title), s_title),
    ]
    if subtitle:
        story.append(Paragraph(escape(subtitle), s_sub))
    story.append(Paragraph(
        "This is your own information, organised for the appointments ahead — not an official "
        "form and not a submission. Always confirm the current requirements with the issuing "
        "authority before you file.",
        s_sub,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=_colors.HexColor(_RULE)))

    # [S1] Two ways to lay this out, and the order matters.
    #
    # When the template declares `sections`, that array IS the layout: its order is display
    # order, each entry carries its own title, and its field_ids say which fields belong to
    # it. A section may reference a field that another section also references (each authority
    # appointment needs its own packet) and may reference NONE at all — France's headline fact
    # is the ABSENCE of an arrival registration, which is a section that is a statement.
    #
    # Otherwise fall back to grouping by fields[].section with the titles from _SECTION_LABELS,
    # which is what every template except RP-NO-DATASHEET still does.
    ordered = sorted(fields, key=lambda f: int(f.get("position") or 0))
    layout: List[Tuple[str, List[Dict[str, Any]]]] = []

    if sections:
        by_id = {str(f.get("id") or ""): f for f in ordered}
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            title = str(sec.get("title") or "").strip() or _section_label(
                str(sec.get("id") or "")
            )
            # A referenced id that isn't in fields[] is dropped rather than crashing a
            # download; backend/tests/test_data_sheet_sections.py fails on it instead, and
            # the employee still gets the rest of their sheet.
            picked = [by_id[i] for i in (sec.get("field_ids") or []) if i in by_id]
            layout.append((title, picked))
    else:
        seen: List[str] = []
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for fd in ordered:
            key = (fd.get("section") or "").strip()
            if key not in grouped:
                grouped[key] = []
                seen.append(key)
            grouped[key].append(fd)
        layout = [(_section_label(key), grouped[key]) for key in seen]

    for title, section_fields in layout:
        story.append(Paragraph(escape(title), s_section))
        story.append(HRFlowable(width="100%", thickness=0.4, color=_colors.HexColor(_RULE)))
        for fd in section_fields:
            fid = str(fd.get("id") or "")
            block: List[Any] = [
                Paragraph(escape(str(fd.get("label") or fid)), s_label)
            ]
            localised = localised_label(fd, source_language)
            if localised:
                block.append(Paragraph(escape(localised), s_label_localised))

            if fd.get("consult_professional"):
                block.append(Paragraph(
                    "Consult a regulated professional — ReloPass does not pre-fill this.",
                    s_consult,
                ))
            else:
                raw = (values.get(fid) or "").strip()
                if raw:
                    block.append(Paragraph(escape(raw), s_value))
                    src = _SOURCE_LABELS.get(str(sources.get(fid) or ""))
                    if src:
                        block.append(Paragraph(escape(src), s_meta))
                else:
                    needed = " (required)" if fd.get("required") else ""
                    block.append(Paragraph(f"Needs input{needed}", s_missing))

            note = fd.get("note")
            if note:
                block.append(Paragraph(escape(str(note)), s_note))
            portal = fd.get("portal_url")
            if portal:
                safe = escape(str(portal))
                block.append(Paragraph(f'<link href="{safe}">{safe}</link>', s_link))

            # Keep a field and its guidance on one page — a note orphaned from its label
            # reads as guidance for the wrong field.
            story.append(KeepTogether(block))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.4, color=_colors.HexColor(_RULE)))
    story.append(Paragraph(
        f"Generated by ReloPass on {_dt.date.today().isoformat()}. "
        "Indicative guidance — confirm current requirements with the issuing authority.",
        s_meta,
    ))

    def _footer(canvas, doc):  # page numbers, drawn outside the flow
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_colors.HexColor(_MUTED))
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=title, author="ReloPass",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.read()

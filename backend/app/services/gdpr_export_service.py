"""
gdpr_export_service.py — builds the GDPR Article 15 "right of access" PDF (IMM-17).

Pure and importable: takes already-loaded, already-decrypted data and renders an
in-memory PDF (bytes). It performs no DB access and holds no FastAPI concerns, so it
can be unit-tested without a database or a request context.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Profile columns that are pure housekeeping / internal plumbing — not the data
# subject's "personal data", so they're omitted from the export for clarity.
_PROFILE_SKIP = {
    "id",
    "case_id",
    "employee_id",
    "org_id",
    "field_sources",
    "created_at",
    "updated_at",
}


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "—"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items()) if value else "—"
    return str(value)


def _kv_table(rows: List[List[str]], styles) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", styles["BodyText"]), Paragraph(_fmt(v), styles["BodyText"])]
            for k, v in rows]
    if not data:
        data = [[Paragraph("No records.", styles["BodyText"]), Paragraph("", styles["BodyText"])]]
    t = Table(data, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_data_export_pdf(
    *,
    case_id: str,
    employee_id: str,
    profile: Optional[Dict[str, Any]],
    interview_answers: Dict[str, Any],
    consent_records: List[Dict[str, Any]],
    access_log: List[Dict[str, Any]],
    generated_at: Optional[datetime] = None,
) -> bytes:
    """Render the Article 15 data-access export as PDF bytes (nothing is persisted)."""
    generated_at = generated_at or datetime.now(timezone.utc)
    styles = getSampleStyleSheet()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
        title="Personal Data Export",
    )
    story: List[Any] = []

    # ── Cover ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Personal Data Export", styles["Title"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "This document contains the personal data ReloPass holds about you in connection "
        "with your immigration relocation case, provided in response to a data subject "
        "access request under <b>Article 15 of the GDPR</b> (right of access).",
        styles["BodyText"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_kv_table([
        ["Relocation case", case_id],
        ["Data subject (employee id)", employee_id],
        ["Generated at (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Legal basis for processing", "Immigration processing (contract / legal obligation)"],
        ["Scope", "Profile data, interview answers, consent history, and access log for this case"],
    ], styles))
    story.append(Spacer(1, 8 * mm))

    # ── 1. Profile ───────────────────────────────────────────────────────────
    story.append(Paragraph("1. Profile data", styles["Heading2"]))
    if profile:
        prof_rows = [[k, v] for k, v in sorted(profile.items()) if k not in _PROFILE_SKIP]
        story.append(_kv_table(prof_rows, styles))
    else:
        story.append(Paragraph("No immigration profile on file for this case.", styles["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    # ── 2. Interview answers ─────────────────────────────────────────────────
    story.append(Paragraph("2. Interview answers", styles["Heading2"]))
    ans_rows = [[k, v] for k, v in sorted((interview_answers or {}).items())]
    story.append(_kv_table(ans_rows, styles))
    story.append(Spacer(1, 6 * mm))

    # ── 3. Consent history ───────────────────────────────────────────────────
    story.append(Paragraph("3. Consent history", styles["Heading2"]))
    if consent_records:
        header = ["Purpose", "Consented", "Version", "When", "Withdrawn"]
        data = [[Paragraph(f"<b>{h}</b>", styles["BodyText"]) for h in header]]
        for c in consent_records:
            data.append([
                Paragraph(_fmt(c.get("purpose")), styles["BodyText"]),
                Paragraph("Yes" if c.get("consented") else "No", styles["BodyText"]),
                Paragraph(_fmt(c.get("consent_version")), styles["BodyText"]),
                Paragraph(_fmt(c.get("consented_at") or c.get("created_at")), styles["BodyText"]),
                Paragraph(_fmt(c.get("withdrawn_at")), styles["BodyText"]),
            ])
        t = Table(data, colWidths=[45 * mm, 20 * mm, 25 * mm, 45 * mm, 30 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No consent records on file.", styles["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    # ── 4. Data access log ───────────────────────────────────────────────────
    story.append(Paragraph("4. Who accessed your data", styles["Heading2"]))
    story.append(Paragraph(
        "Each entry records that your data was accessed — by whom, when, and which "
        "fields — without copying the field values themselves.", styles["BodyText"]))
    story.append(Spacer(1, 2 * mm))
    if access_log:
        header = ["When (UTC)", "Role", "Action", "Fields", "Purpose"]
        data = [[Paragraph(f"<b>{h}</b>", styles["BodyText"]) for h in header]]
        for a in access_log:
            data.append([
                Paragraph(_fmt(a.get("accessed_at")), styles["BodyText"]),
                Paragraph(_fmt(a.get("accessed_by_role")), styles["BodyText"]),
                Paragraph(_fmt(a.get("action")), styles["BodyText"]),
                Paragraph(_fmt(a.get("fields_accessed")), styles["BodyText"]),
                Paragraph(_fmt(a.get("purpose")), styles["BodyText"]),
            ])
        t = Table(data, colWidths=[38 * mm, 22 * mm, 22 * mm, 48 * mm, 35 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No access log entries on file.", styles["BodyText"]))

    doc.build(story)
    return buf.getvalue()

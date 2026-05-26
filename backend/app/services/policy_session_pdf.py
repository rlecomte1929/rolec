"""
P5-4: Policy Q&A session PDF export.

Generates a PDF document summarising a completed Policy Assistant session:
  - Header: company, employee, tier, policy version, session date
  - Q&A pairs with answer text and inline source citations
  - Footer: generation timestamp + disclaimer

Uses reportlab (already in requirements.txt).
Designed for server-side use — no browser dependency.
"""

from __future__ import annotations

import io
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def build_policy_session_pdf(
    turns: List[Dict[str, Any]],
    *,
    employee_name: Optional[str] = None,
    company_name: Optional[str] = None,
    tier: Optional[str] = None,
    policy_version: Optional[str] = None,
    session_date: Optional[str] = None,
) -> bytes:
    """
    Render a PDF of the policy Q&A session and return raw bytes.

    Parameters
    ----------
    turns:
        List of dicts, each with keys:
            - question:    str
            - answer_text: str
            - evidence:    list of {label, excerpt} (optional)
    employee_name, company_name, tier, policy_version:
        Header metadata. Any that are None are omitted from the header.
    session_date:
        ISO date string e.g. "2026-05-22". Defaults to today (UTC) if not given.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            BaseDocTemplate,
            Frame,
            PageTemplate,
            Paragraph,
            Spacer,
            HRFlowable,
            KeepTogether,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF export") from exc

    # ------------------------------------------------------------------
    # Colours / typographic palette
    # ------------------------------------------------------------------
    NAVY = HexColor("#0b2b43")
    SLATE_600 = HexColor("#475569")
    SLATE_400 = HexColor("#94a3b8")
    SLATE_200 = HexColor("#e2e8f0")
    SLATE_50 = HexColor("#f8fafc")
    WHITE = HexColor("#ffffff")

    PAGE_W, PAGE_H = A4
    MARGIN_L = 20 * mm
    MARGIN_R = 20 * mm
    MARGIN_T = 18 * mm
    MARGIN_B = 20 * mm
    FOOTER_H = 14 * mm

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------
    base = getSampleStyleSheet()

    def _style(name: str, **kw) -> ParagraphStyle:
        s = ParagraphStyle(name, parent=base["Normal"], **kw)
        return s

    s_header_company = _style(
        "header_company",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=SLATE_600,
        leading=13,
    )
    s_header_meta = _style(
        "header_meta",
        fontName="Helvetica",
        fontSize=9,
        textColor=SLATE_400,
        leading=12,
    )
    s_section_label = _style(
        "section_label",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        textColor=SLATE_400,
        leading=10,
        spaceAfter=2,
    )
    s_question = _style(
        "question",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=NAVY,
        leading=14,
        spaceAfter=4,
    )
    s_answer = _style(
        "answer",
        fontName="Helvetica",
        fontSize=10,
        textColor=HexColor("#1e293b"),
        leading=14,
        spaceAfter=4,
    )
    s_evidence_label = _style(
        "ev_label",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=NAVY,
        leading=11,
    )
    s_evidence_excerpt = _style(
        "ev_excerpt",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=SLATE_600,
        leading=12,
    )
    s_footer = _style(
        "footer",
        fontName="Helvetica",
        fontSize=7.5,
        textColor=SLATE_400,
        leading=10,
        alignment=TA_CENTER,
    )
    s_disclaimer = _style(
        "disclaimer",
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=SLATE_400,
        leading=11,
    )

    # ------------------------------------------------------------------
    # Header / footer canvas callbacks
    # ------------------------------------------------------------------
    today_str = session_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gen_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _on_page(canvas, doc):
        """Draw page header rule + branding + footer on each page."""
        canvas.saveState()
        y_top = PAGE_H - MARGIN_T

        # Navy top rule
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(1.5)
        canvas.line(MARGIN_L, y_top, PAGE_W - MARGIN_R, y_top)

        # Brand label
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(NAVY)
        canvas.drawString(MARGIN_L, y_top + 3 * mm, "ReloPass  Policy Assistant")

        # Page number (right-aligned)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(SLATE_400)
        canvas.drawRightString(
            PAGE_W - MARGIN_R,
            y_top + 3 * mm,
            f"Page {doc.page}",
        )

        # Footer rule + text
        canvas.setStrokeColor(SLATE_200)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_L, MARGIN_B, PAGE_W - MARGIN_R, MARGIN_B)

        footer_text = (
            f"Generated by ReloPass Policy Assistant — {gen_timestamp}    "
            "This document reflects the published policy at the time of generation. "
            "For binding commitments, refer to your signed employment contract and the HR Business Partner."
        )
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SLATE_400)
        canvas.drawCentredString(PAGE_W / 2, MARGIN_B - 4 * mm, footer_text)

        canvas.restoreState()

    # ------------------------------------------------------------------
    # Build document
    # ------------------------------------------------------------------
    buf = io.BytesIO()

    # usable area below header rule (which sits at PAGE_H - MARGIN_T)
    # subtract another 8 mm for the brand label row
    frame_top_margin = MARGIN_T + 8 * mm

    frame = Frame(
        MARGIN_L,
        MARGIN_B + FOOTER_H,
        PAGE_W - MARGIN_L - MARGIN_R,
        PAGE_H - frame_top_margin - MARGIN_B - FOOTER_H,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=frame_top_margin,
        bottomMargin=MARGIN_B + FOOTER_H,
    )
    template = PageTemplate(id="main", frames=[frame], onPage=_on_page)
    doc.addPageTemplates([template])

    # ------------------------------------------------------------------
    # Story: session header block
    # ------------------------------------------------------------------
    story: list = []

    header_lines: list = []
    if company_name:
        header_lines.append(Paragraph(f"Company: {company_name}", s_header_company))
    if employee_name:
        header_lines.append(Paragraph(f"Employee: {employee_name}", s_header_company))
    if tier:
        header_lines.append(Paragraph(f"Tier: {tier}", s_header_meta))
    if policy_version:
        header_lines.append(Paragraph(f"Policy Version: {policy_version}", s_header_meta))
    header_lines.append(Paragraph(f"Session Date: {today_str}", s_header_meta))

    if header_lines:
        story.extend(header_lines)
        story.append(Spacer(1, 4 * mm))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=SLATE_200,
                spaceAfter=4 * mm,
            )
        )

    # ------------------------------------------------------------------
    # Story: Q&A pairs
    # ------------------------------------------------------------------
    for idx, turn in enumerate(turns, start=1):
        question = (turn.get("question") or "").strip()
        answer_text = (turn.get("answer_text") or "").strip()
        evidence_list = turn.get("evidence") or []

        qa_block: list = []

        qa_block.append(Paragraph(f"Q{idx}", s_section_label))
        qa_block.append(Paragraph(_escape(question), s_question))
        qa_block.append(Paragraph(_escape(answer_text), s_answer))

        # Evidence
        if evidence_list:
            qa_block.append(Spacer(1, 2 * mm))
            qa_block.append(Paragraph("Sources", s_section_label))
            for ev in evidence_list:
                ev_label = (ev.get("label") or "Policy source").strip()
                ev_excerpt = (ev.get("excerpt") or "").strip()
                qa_block.append(Paragraph(f"• {_escape(ev_label)}", s_evidence_label))
                if ev_excerpt:
                    qa_block.append(
                        Paragraph(f"“{_escape(ev_excerpt)}”", s_evidence_excerpt)
                    )

        qa_block.append(Spacer(1, 3 * mm))
        if idx < len(turns):
            qa_block.append(
                HRFlowable(
                    width="100%",
                    thickness=0.4,
                    color=SLATE_200,
                    spaceAfter=3 * mm,
                )
            )

        story.append(KeepTogether(qa_block) if len(qa_block) <= 20 else qa_block[0])
        if len(qa_block) > 1:
            story.extend(qa_block[1:])

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Escape characters that would break ReportLab XML parsing."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

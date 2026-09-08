"""
W2-4 (BureauAI-audit remediation): exportable HR policy-compliance pack.

HR's #1 unmet need from the buyer-value audit is *proof they can take away* — yet
there was no export anywhere. This adds CSV + PDF exports of the existing
policy-compliance matrix (the 13-benefit heatmap already served by
hr_analytics.get_policy_compliance_matrix). No new data is queried — we reuse that
handler and just serialise it, tenant-scoped by the same require_admin_or_hr auth.

Registered in BOTH backend/app/main.py and backend/main.py (prod boots
backend.main:app).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse

from ..auth_deps import require_admin_or_hr
from . import hr_analytics
from .hr_analytics import BENEFIT_COLUMNS, BENEFIT_LABELS

router = APIRouter(prefix="/api/hr", tags=["hr-export"])

_BASE_COLS = ["Employee", "Initials", "Origin", "Destination", "Tier",
              "Assignment", "Start date", "Budget EUR", "Spend EUR"]


def _matrix(period: str, tier: Optional[str], destination: Optional[str], user: Dict[str, Any]):
    """Reuse the existing compliance-matrix handler (plain function call — the
    Depends only fires when FastAPI invokes it, not here)."""
    return hr_analytics.get_policy_compliance_matrix(
        period=period, tier=tier, destination=destination, user=user
    )


def _filename(ext: str) -> str:
    return f"policy_compliance_{datetime.now(timezone.utc).strftime('%Y%m%d')}.{ext}"


@router.get("/policy-compliance-matrix/export.csv")
def export_compliance_matrix_csv(
    period: str = Query("12mo"),
    tier: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> StreamingResponse:
    """One row per case: roster + budget/spend + the 13 benefit-compliance cells."""
    matrix = _matrix(period, tier, destination, user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_BASE_COLS + [BENEFIT_LABELS[k] for k in BENEFIT_COLUMNS])
    for row in matrix.cases:
        w.writerow([
            row.name, row.init, row.origin or "", row.dest or "", row.tier or "",
            row.assignment_type or "", row.start_date or "",
            "" if row.budget_eur is None else row.budget_eur,
            "" if row.spend_eur is None else row.spend_eur,
            *[row.cells.get(k, "") for k in BENEFIT_COLUMNS],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={_filename('csv')}"},
    )


def _build_pdf(matrix, period: str) -> bytes:
    """Compact, readable HR report: KPIs + per-case over-policy / pending flags.
    (Mirrors the reportlab pattern in gdpr_export_service.)"""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    k = matrix.kpis
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
        title="Policy Compliance Report",
    )
    story = [
        Paragraph(f"Policy Compliance Report — {period}", styles["Title"]),
        Paragraph(
            f"Compliance: <b>{k.compliance_pct}%</b> &nbsp; Active cases: <b>{k.active_count}</b> &nbsp; "
            f"Avg overage: <b>{('€%s' % k.avg_overage_eur) if k.avg_overage_eur is not None else '—'}</b> &nbsp; "
            f"Most overrun: <b>{k.most_overrun_benefit or '—'}</b>",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]

    header = ["Employee", "Dest", "Tier", "Budget €", "Spend €", "Over-policy benefits", "Exceptions pending"]
    data = [header]
    for row in matrix.cases:
        over = [BENEFIT_LABELS[bk] for bk in BENEFIT_COLUMNS if row.cells.get(bk) == "red"]
        pending = [BENEFIT_LABELS[bk] for bk in BENEFIT_COLUMNS if row.cells.get(bk) == "blue"]
        data.append([
            row.name, row.dest or "—", row.tier or "—",
            "—" if row.budget_eur is None else f"{row.budget_eur:,}",
            "—" if row.spend_eur is None else f"{row.spend_eur:,}",
            ", ".join(over) or "—", ", ".join(pending) or "—",
        ])
    table = Table(data, repeatRows=1, colWidths=[40 * mm, 18 * mm, 20 * mm, 24 * mm, 24 * mm, 70 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()


@router.get("/policy-compliance-matrix/export.pdf")
def export_compliance_matrix_pdf(
    period: str = Query("12mo"),
    tier: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Response:
    """KPIs + per-case over-policy / pending-exception summary."""
    matrix = _matrix(period, tier, destination, user)
    pdf = _build_pdf(matrix, period)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={_filename('pdf')}"},
    )

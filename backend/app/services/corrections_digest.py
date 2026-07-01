"""[AIQ-945 / C2-03-FU] Weekly corrections digest.

Renders + delivers a weekly summary of HR contradiction-resolution corrections,
grouped by reason_code (the locked 6-value taxonomy). Builds on the analytics
shipped in AIQ-554 (correction_analytics) and the Resend delivery path shared by
the HR invite / mobility-status emails.

MVP scope (matches the repo's manual-cron pattern, e.g. P1-08d): manual trigger
via POST /api/admin/corrections/digest/run. A real scheduler (pg_cron / GitHub
Actions) is a documented Phase-2 follow-up.

Delivery is best-effort: with no RESEND_API_KEY the digest is logged, never sent,
and the run still returns ok (never raises).
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

from .assignment_invite_email import _resend_send
from .correction_analytics import (
    REASON_CODES,
    summarize_by_reason,
    weekly_corrections_by_reason,
)

log = logging.getLogger(__name__)

# Human-readable labels for the render — mirrors apps/hr-dashboard reasonCodes.ts
# REASON_CODE_LABELS so the email reads the same as the Resolution UI.
_REASON_LABELS: Dict[str, str] = {
    "OCR_ERROR": "OCR misread",
    "TYPO_IN_SOURCE": "Typo in source",
    "AMBIGUOUS_PARTICLE": "Ambiguous particle",
    "LEGITIMATE_VARIATION": "Legitimate variation",
    "FRAUD_SUSPECTED": "Fraud suspected",
    "OTHER": "Other",
}


def render_corrections_digest(
    totals: Dict[str, int],
    week_start: date,
    employer_id: Optional[str] = None,
) -> Dict[str, str]:
    """Pure render → {subject, text, html}. Lists all 6 reason codes (zero-filled),
    so a 0-correction week still renders every reason at 0 (criterion 5)."""
    total = sum(int(v) for v in totals.values())
    scope = f" — employer {employer_id}" if employer_id else " — all employers"
    subject = f"ReloPass weekly corrections digest (week of {week_start.isoformat()}){scope}"

    # Stable ordering = the locked taxonomy order.
    lines = [f"  {_REASON_LABELS.get(code, code)} ({code}): {int(totals.get(code, 0))}" for code in REASON_CODES]
    if total == 0:
        head = f"No corrections were recorded for the week of {week_start.isoformat()}."
    else:
        head = f"{total} correction(s) recorded for the week of {week_start.isoformat()}, by reason:"
    text = subject + "\n\n" + head + "\n" + "\n".join(lines) + "\n"

    rows_html = "".join(
        f"<li><strong>{_REASON_LABELS.get(code, code)}</strong> "
        f"(<code>{code}</code>): {int(totals.get(code, 0))}</li>"
        for code in REASON_CODES
    )
    html = (
        f"<h2>{subject}</h2><p>{head}</p><ul>{rows_html}</ul>"
        "<p style=\"color:#888;font-size:12px\">Reason taxonomy is the locked 6-value set; "
        "weeks with no corrections still list every reason at 0.</p>"
    )
    return {"subject": subject, "text": text, "html": html}


def _recipients() -> List[str]:
    """Digest recipients from CORRECTIONS_DIGEST_TO (comma-separated). Empty → none
    (the run logs the rendered digest instead of sending)."""
    raw = os.getenv("CORRECTIONS_DIGEST_TO", "")
    return [e.strip() for e in raw.split(",") if e.strip()]


def run_corrections_digest(
    employer_id: Optional[str] = None,
    week_start: Optional[date] = None,
    *,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch the last week's corrections → summarize → render → deliver (best-effort).

    Returns {ok, week_start, total, totals, recipients, results}. Never raises.
    """
    from .correction_analytics import _week_start_utc  # local: same Monday anchor as the analytics

    wk = week_start or _week_start_utc().date()  # _week_start_utc() is a datetime (Monday 00:00 UTC)
    rows = weekly_corrections_by_reason(employer_id=employer_id, weeks_back=1)
    totals = summarize_by_reason(rows)
    rendered = render_corrections_digest(totals, wk, employer_id)

    recipients = _recipients()
    results: List[Dict[str, Any]] = []
    if not recipients:
        log.info("corrections_digest (no CORRECTIONS_DIGEST_TO — logged, not sent):\n\n%s", rendered["text"])
        results.append({"to": None, "status": "no_recipients"})
    else:
        for to in recipients:
            res = _resend_send(
                to_email=to,
                subject=rendered["subject"],
                plain=rendered["text"],
                html=rendered["html"],
                request_id=request_id,
                context="corrections_digest",
            )
            results.append({"to": to, "status": res.get("status")})

    return {
        "ok": True,
        "week_start": wk.isoformat(),
        "total": sum(int(v) for v in totals.values()),
        "totals": totals,
        "recipients": recipients,
        "results": results,
    }

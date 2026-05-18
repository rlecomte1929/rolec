"""
Prescreening completion email notification  (AIQ-13-E)

Sends a branded HTML + plain-text email to the HR reviewer when
document pre-screening finishes.

Usage
-----
    from backend.app.services.prescreening_notification import send_prescreening_complete_email

    send_prescreening_complete_email(
        to="hr@company.com",
        employee_name="Adrien Martin",
        document_type="Passport",
        case_id="abc-123",
        result_summary="2 checks passed, 1 flag: expiry within 6 months",
        flag_count=1,
        review_url="https://app.relopass.com/hr/cases/abc-123",
    )

Behaviour
---------
- Uses RESEND_API_KEY env var; if unset logs the email body at INFO level (dev).
- Set EMAIL_FROM to control the sender (default: noreply@relopass.com).
- Fire-and-forget: wrapped in try/except — never raises to caller.
- reviewer_email is derived from relocation_cases.hr_user_id → users.email;
  no separate reviewer_email column is needed on the cases table.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests as http_requests

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Email template
# ---------------------------------------------------------------------------

_SUBJECT_CLEAN = "Document ready for review — {employee_name} ({document_type})"
_SUBJECT_FLAGS = "⚠ {flag_count} flag(s) — {employee_name} ({document_type})"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Document Pre-Screening Complete</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f8fafc;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#0b2b43;padding:24px 32px;">
            <span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">ReloPass</span>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px;">
            <p style="margin:0 0 8px;font-size:22px;font-weight:700;color:#0b2b43;">
              Document pre-screening complete
            </p>
            <p style="margin:0 0 24px;font-size:15px;color:#64748b;">
              {employee_name}&nbsp;·&nbsp;{document_type}
            </p>

            <!-- Result badge -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              <tr>
                <td style="background:{badge_bg};color:{badge_fg};border-radius:6px;padding:8px 16px;font-size:14px;font-weight:600;">
                  {badge_label}
                </td>
              </tr>
            </table>

            <p style="margin:0 0 24px;font-size:15px;color:#334155;line-height:1.6;">
              {result_summary}
            </p>

            <!-- CTA -->
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:#0b2b43;border-radius:6px;padding:12px 24px;">
                  <a href="{review_url}" style="color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;">
                    Review document →
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px 24px;border-top:1px solid #f1f5f9;">
            <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.5;">
              This is a pre-screening flag for your review.
              ReloPass does not make compliance determinations.
              You are receiving this email because you are the HR reviewer on this case.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""

_PLAIN_TEMPLATE = """\
Document pre-screening complete — ReloPass

Employee: {employee_name}
Document type: {document_type}
Result: {result_summary}

Review document:
{review_url}

---
This is a pre-screening flag for your review. ReloPass does not make compliance determinations.
"""


def _render(
    employee_name: str,
    document_type: str,
    case_id: str,
    result_summary: str,
    flag_count: int,
    review_url: str,
) -> tuple[str, str, str]:
    """Return (subject, plain_text, html_body)."""
    if flag_count > 0:
        subject = _SUBJECT_FLAGS.format(
            flag_count=flag_count,
            employee_name=employee_name,
            document_type=document_type,
        )
        badge_bg, badge_fg, badge_label = "#fef3c7", "#92400e", f"⚠ {flag_count} flag{'s' if flag_count != 1 else ''} found"
    else:
        subject = _SUBJECT_CLEAN.format(
            employee_name=employee_name,
            document_type=document_type,
        )
        badge_bg, badge_fg, badge_label = "#dcfce7", "#166534", "✓ Pre-screening passed"

    html = _HTML_TEMPLATE.format(
        employee_name=employee_name,
        document_type=document_type,
        result_summary=result_summary,
        review_url=review_url,
        badge_bg=badge_bg,
        badge_fg=badge_fg,
        badge_label=badge_label,
    )
    plain = _PLAIN_TEMPLATE.format(
        employee_name=employee_name,
        document_type=document_type,
        result_summary=result_summary,
        review_url=review_url,
    )
    return subject, plain, html


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_prescreening_complete_email(
    *,
    to: str,
    employee_name: str,
    document_type: str,
    case_id: str,
    result_summary: str,
    flag_count: int = 0,
    review_url: Optional[str] = None,
) -> None:
    """
    Send the pre-screening complete notification email.

    Parameters
    ----------
    to : str
        Recipient email address (the HR reviewer — derived from
        relocation_cases.hr_user_id → users.email).
    employee_name : str
        Full name of the employee whose document was screened.
    document_type : str
        Human-readable document label, e.g. "Passport" or "Work Permit".
    case_id : str
        Relocation case UUID — used to build the review_url fallback.
    result_summary : str
        Short human-readable summary, e.g. "2 checks passed, 1 flag: expiry date".
    flag_count : int
        Number of flags raised by the prescreening pipeline (0 = clean pass).
    review_url : str, optional
        Deep-link to the DocumentReviewCard. Falls back to
        https://app.relopass.com/hr/cases/{case_id} if not provided.
    """
    if not review_url:
        base = os.getenv("APP_BASE_URL", "https://app.relopass.com")
        review_url = f"{base}/hr/cases/{case_id}"

    try:
        subject, plain, html = _render(
            employee_name=employee_name,
            document_type=document_type,
            case_id=case_id,
            result_summary=result_summary,
            flag_count=flag_count,
            review_url=review_url,
        )

        resend_key = os.getenv("RESEND_API_KEY", "")
        from_addr = os.getenv("EMAIL_FROM", "noreply@relopass.com")

        if resend_key:
            resp = http_requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_addr,
                    "to": [to],
                    "subject": subject,
                    "text": plain,
                    "html": html,
                },
                timeout=10,
            )
            if resp.ok:
                log.info("Prescreening notification sent to %s (case %s)", to, case_id)
            else:
                log.error(
                    "Resend delivery failed for prescreening notification: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
        else:
            # Dev fallback — log so local testing works without email config
            log.info(
                "PRESCREENING NOTIFICATION (no RESEND_API_KEY): to=%s subject=%r\n\n%s",
                to,
                subject,
                plain,
            )

    except Exception as exc:  # noqa: BLE001
        # Never let email failure propagate to the pipeline caller
        log.error("Prescreening notification error (suppressed): %s", exc)


def get_reviewer_email_for_case(case_id: str) -> Optional[str]:
    """
    Derive the HR reviewer's email from the case record.

    Joins relocation_cases.hr_user_id → users.email.
    Returns None if not found (caller should skip notification silently).

    Note: no reviewer_email column is needed on relocation_cases —
    the HR user's email is always available via this join.
    """
    try:
        from ...database import db  # lazy import avoids circular at module load

        with db.engine.connect() as conn:
            from sqlalchemy import text
            row = conn.execute(
                text(
                    "SELECT u.email FROM relocation_cases rc "
                    "JOIN users u ON u.id = rc.hr_user_id "
                    "WHERE rc.id = :case_id LIMIT 1"
                ),
                {"case_id": case_id},
            ).mappings().first()
        if row:
            return row["email"]
    except Exception as exc:  # noqa: BLE001
        log.error("Could not resolve reviewer email for case %s: %s", case_id, exc)
    return None

"""
AIQ-40-C · RFQ (Request for Quote) flow

POST /api/hr/rfq-requests
  — Creates rfq_requests row and sends structured email to vendor.

GET  /api/hr/rfq-requests?case_id=<uuid>
  — Returns RFQs for a given case (for AIQ-40-D pending list).

PATCH /api/hr/rfq-requests/{id}
  — HR updates status (quote_received, accepted, cancelled).
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests as http_requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ..auth_deps import get_current_user
from ...database import db
from ...schemas import UserRole

router = APIRouter(tags=["hr_rfq"])
log = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@relopass.com")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RfqCreateRequest(BaseModel):
    case_id: str
    vendor_id: str
    service_category: str
    move_date: Optional[str] = None          # ISO date string YYYY-MM-DD
    budget_range: Optional[str] = None
    special_requirements: Optional[str] = None

    # IMM-15: optional immigration case context. Present only when the RFQ
    # originates from the immigration panel; stored as JSONB on rfq_requests.
    visa_type: Optional[str] = None
    corridor_from: Optional[str] = None
    corridor_to: Optional[str] = None
    employee_nationality: Optional[str] = None
    has_dependents: Optional[bool] = None
    risk_flags: Optional[List[str]] = None   # flag_type strings


def _build_immigration_context(body: "RfqCreateRequest") -> Optional[Dict[str, Any]]:
    """Assemble the immigration_context JSONB payload from the request.

    Returns None when no immigration fields were supplied so non-immigration
    RFQs leave the column NULL (backward-compatible — see migration).
    """
    ctx: Dict[str, Any] = {}
    if body.visa_type:
        ctx["visa_type"] = body.visa_type
    if body.corridor_from:
        ctx["corridor_from"] = body.corridor_from
    if body.corridor_to:
        ctx["corridor_to"] = body.corridor_to
    if body.employee_nationality:
        ctx["employee_nationality"] = body.employee_nationality
    if body.has_dependents is not None:
        ctx["has_dependents"] = body.has_dependents
    if body.risk_flags:
        ctx["risk_flags"] = body.risk_flags
    return ctx or None


class RfqStatusUpdate(BaseModel):
    status: str                          # quote_received | accepted | cancelled
    quote_amount: Optional[float] = None
    quote_currency: Optional[str] = None
    quote_deadline: Optional[str] = None # ISO date YYYY-MM-DD
    quote_deliverable: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_hr(user: Dict[str, Any]) -> tuple[str, str]:
    """Assert HR/Admin; return (company_id, user_email)."""
    role = (user.get("role") or "").upper()
    if role not in (UserRole.HR.value, UserRole.ADMIN.value) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company") or ""
    email = (profile or {}).get("email") or user.get("email") or ""
    name = (
        f"{(profile or {}).get('first_name', '')} {(profile or {}).get('last_name', '')}".strip()
        or email
    )
    return company_id, email, name   # type: ignore[return-value]


def _send_rfq_email(
    vendor_email: str,
    vendor_name: str,
    service_category: str,
    corridor: str,
    move_date: Optional[str],
    budget_range: Optional[str],
    special_requirements: Optional[str],
    hr_name: str,
    hr_email: str,
) -> None:
    """Fire-and-forget RFQ email to vendor via Resend."""
    subject = f"Quote Request — {service_category} for relocation to {corridor}"

    move_date_display = move_date or "TBD"
    budget_display = budget_range or "Not specified"
    requirements_display = special_requirements or "None"

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#111;">
  <div style="background:#0b2b43;padding:16px 24px;border-radius:8px 8px 0 0;">
    <p style="color:#fff;font-size:18px;font-weight:600;margin:0;">ReloPass — Quote Request</p>
  </div>
  <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px;">
    <p>Dear <strong>{vendor_name}</strong>,</p>
    <p>We are seeking a quote for the following relocation service:</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr style="background:#f8fafc;">
        <td style="padding:10px 12px;font-weight:600;width:40%;border-bottom:1px solid #e2e8f0;">Service</td>
        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{service_category}</td>
      </tr>
      <tr>
        <td style="padding:10px 12px;font-weight:600;border-bottom:1px solid #e2e8f0;">Corridor</td>
        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{corridor}</td>
      </tr>
      <tr style="background:#f8fafc;">
        <td style="padding:10px 12px;font-weight:600;border-bottom:1px solid #e2e8f0;">Move date</td>
        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{move_date_display}</td>
      </tr>
      <tr>
        <td style="padding:10px 12px;font-weight:600;border-bottom:1px solid #e2e8f0;">Budget range</td>
        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{budget_display}</td>
      </tr>
      <tr style="background:#f8fafc;">
        <td style="padding:10px 12px;font-weight:600;">Special requirements</td>
        <td style="padding:10px 12px;">{requirements_display}</td>
      </tr>
    </table>
    <p>Please reply directly to this email with your quote. All correspondence will be handled by:</p>
    <p><strong>{hr_name}</strong><br/>
    <a href="mailto:{hr_email}" style="color:#2563eb;">{hr_email}</a></p>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;"/>
    <p style="color:#94a3b8;font-size:12px;">
      This quote request was sent via ReloPass — the relocation management platform.
      Employee details are anonymised for GDPR compliance.
    </p>
  </div>
</body>
</html>
"""
    text_body = (
        f"Quote Request — {service_category} · {corridor}\n\n"
        f"Service: {service_category}\n"
        f"Corridor: {corridor}\n"
        f"Move date: {move_date_display}\n"
        f"Budget: {budget_display}\n"
        f"Requirements: {requirements_display}\n\n"
        f"Reply to: {hr_name} <{hr_email}>\n"
    )

    if not RESEND_API_KEY:
        log.info("[rfq] No RESEND_API_KEY — email body:\n%s", text_body)
        return

    try:
        resp = http_requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": EMAIL_FROM,
                "to": [vendor_email],
                "reply_to": hr_email,
                "subject": subject,
                "html": html_body,
                "text": text_body,
            },
            timeout=10,
        )
        if resp.ok:
            log.info("[rfq] Email sent to %s (status %s)", vendor_email, resp.status_code)
        else:
            log.warning("[rfq] Email failed: %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        log.error("[rfq] Email exception: %s", exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/api/hr/rfq-requests", status_code=201)
async def create_rfq(
    body: RfqCreateRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Create an RFQ row and fire an email to the vendor (background task).
    """
    company_id, hr_email, hr_name = _require_hr(user)

    # Fetch vendor
    with db.engine.begin() as conn:
        from sqlalchemy import text
        vendor_row = conn.execute(
            text("SELECT id, name, contact_email, corridors FROM vendors WHERE id = :id AND is_approved = true"),
            {"id": body.vendor_id},
        ).mappings().first()

    if not vendor_row:
        raise HTTPException(status_code=404, detail="Vendor not found")

    vendor = dict(vendor_row)
    vendor_corridors = vendor.get("corridors") or []
    corridor = vendor_corridors[0] if vendor_corridors else "—"

    # Fetch case destination for corridor context
    try:
        with db.engine.begin() as conn:
            from sqlalchemy import text as sql_text
            case_row = conn.execute(
                sql_text("SELECT destination_country, home_country FROM relocation_cases WHERE id = :id"),
                {"id": body.case_id},
            ).mappings().first()
        if case_row:
            origin = case_row.get("home_country") or "?"
            dest = case_row.get("destination_country") or "?"
            corridor = f"{origin} → {dest}"
    except Exception:
        pass  # fall back to vendor corridors value

    # Insert RFQ row
    rfq_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    immigration_context = _build_immigration_context(body)
    with db.engine.begin() as conn:
        from sqlalchemy import text as sql_text
        conn.execute(
            sql_text("""
                INSERT INTO rfq_requests
                  (id, case_id, vendor_id, org_id, service_category,
                   move_date, budget_range, special_requirements, immigration_context,
                   hr_user_id, hr_email, hr_name, status, created_at, updated_at)
                VALUES
                  (:id, :case_id, :vendor_id, :org_id, :service_category,
                   :move_date, :budget_range, :special_requirements,
                   CAST(:immigration_context AS jsonb),
                   :hr_user_id, :hr_email, :hr_name, 'sent', :now, :now)
            """),
            {
                "id": rfq_id,
                "case_id": body.case_id,
                "vendor_id": body.vendor_id,
                "org_id": company_id,
                "service_category": body.service_category,
                "move_date": body.move_date or None,
                "budget_range": body.budget_range or None,
                "special_requirements": body.special_requirements or None,
                "immigration_context": json.dumps(immigration_context) if immigration_context else None,
                "hr_user_id": str(user.get("id", "")),
                "hr_email": hr_email,
                "hr_name": hr_name,
                "now": now,
            },
        )

    # Send email in background
    background_tasks.add_task(
        _send_rfq_email,
        vendor_email=vendor["contact_email"],
        vendor_name=vendor["name"],
        service_category=body.service_category,
        corridor=corridor,
        move_date=body.move_date,
        budget_range=body.budget_range,
        special_requirements=body.special_requirements,
        hr_name=hr_name,
        hr_email=hr_email,
    )

    log.info("[rfq] Created rfq=%s for case=%s vendor=%s", rfq_id, body.case_id, body.vendor_id)
    return {
        "ok": True,
        "rfq_id": rfq_id,
        "vendor_name": vendor["name"],
        "status": "sent",
        "message": f"Quote request sent to {vendor['name']}",
    }


@router.get("/api/hr/rfq-requests")
async def list_rfqs(
    case_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return RFQs for a case (HR use, for AIQ-40-D pending list)."""
    company_id, _, _ = _require_hr(user)

    from sqlalchemy import text as sql_text
    conditions = ["r.org_id = :org_id"]
    params: Dict[str, Any] = {"org_id": company_id}

    if case_id:
        conditions.append("r.case_id = :case_id")
        params["case_id"] = case_id

    where = " AND ".join(conditions)
    sql = f"""
        SELECT r.id, r.case_id, r.vendor_id, r.service_category,
               r.move_date, r.budget_range, r.special_requirements,
               r.hr_email, r.hr_name, r.status, r.created_at, r.updated_at,
               v.name AS vendor_name, v.email AS vendor_email
        FROM rfq_requests r
        LEFT JOIN vendors v ON v.id = r.vendor_id
        WHERE {where}
        ORDER BY r.created_at DESC
    """
    with db.engine.begin() as conn:
        rows = conn.execute(sql_text(sql), params).mappings().all()

    rfqs = []
    for row in rows:
        d = dict(row)
        for ts in ("created_at", "updated_at", "move_date"):
            v = d.get(ts)
            if hasattr(v, "isoformat"):
                d[ts] = v.isoformat()
        rfqs.append(d)

    return {"rfqs": rfqs, "total": len(rfqs)}


@router.patch("/api/hr/rfq-requests/{rfq_id}")
async def update_rfq_status(
    rfq_id: str,
    body: RfqStatusUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    HR updates RFQ status and optionally records quote details.

    Transitions:
      sent → quote_received  : HR enters amount, currency, deadline, deliverable
      quote_received → accepted : logs case_event; vendor task visible in timeline
      any → cancelled
    """
    company_id, hr_email, hr_name = _require_hr(user)

    allowed = {"quote_received", "accepted", "cancelled"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {allowed}")

    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc).isoformat()

    # Build dynamic SET clause
    set_parts = ["status = :status", "updated_at = :now"]
    params: Dict[str, Any] = {"id": rfq_id, "status": body.status, "now": now, "org_id": company_id}

    if body.quote_amount is not None:
        set_parts.append("quote_amount = :quote_amount")
        params["quote_amount"] = body.quote_amount
    if body.quote_currency:
        set_parts.append("quote_currency = :quote_currency")
        params["quote_currency"] = body.quote_currency
    if body.quote_deadline:
        set_parts.append("quote_deadline = :quote_deadline")
        params["quote_deadline"] = body.quote_deadline
    if body.quote_deliverable:
        set_parts.append("quote_deliverable = :quote_deliverable")
        params["quote_deliverable"] = body.quote_deliverable

    set_sql = ", ".join(set_parts)

    with db.engine.begin() as conn:
        result = conn.execute(
            sql_text(f"""
                UPDATE rfq_requests
                SET {set_sql}
                WHERE id = :id AND org_id = :org_id
                RETURNING id, case_id, status, vendor_id,
                          quote_amount, quote_currency, quote_deadline, quote_deliverable,
                          service_category
            """),
            params,
        ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="RFQ not found")

    row = dict(result)

    # On acceptance: log a case_event so the activity log shows it
    if body.status == "accepted":
        try:
            vendor_name = ""
            with db.engine.begin() as conn:
                v = conn.execute(
                    sql_text("SELECT name FROM vendors WHERE id = :id"),
                    {"id": row.get("vendor_id")},
                ).mappings().first()
                vendor_name = (v or {}).get("name", "vendor")

            amount_str = ""
            if row.get("quote_amount"):
                currency = row.get("quote_currency") or "EUR"
                amount_str = f" · {currency} {row['quote_amount']:,.0f}"

            description = (
                f"Quote accepted: {vendor_name} — {row.get('service_category', '')}"
                f"{amount_str}"
            )
            if row.get("quote_deadline"):
                description += f" · Due {row['quote_deadline']}"

            event_id = str(uuid.uuid4())
            with db.engine.begin() as conn:
                conn.execute(
                    sql_text("""
                        INSERT INTO case_events
                          (id, case_id, event_type, description, created_at, actor_principal_id)
                        VALUES
                          (:id, :case_id, 'rfq_accepted', :description, :now, :actor)
                    """),
                    {
                        "id": event_id,
                        "case_id": row.get("case_id"),
                        "description": description,
                        "now": now,
                        "actor": hr_email,
                    },
                )
            log.info("[rfq] Case event logged for accepted rfq=%s case=%s", rfq_id, row.get("case_id"))
        except Exception as exc:
            log.warning("[rfq] Could not log case_event for acceptance: %s", exc)

    return {"ok": True, "rfq_id": rfq_id, "status": body.status}

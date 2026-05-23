"""
Provider portal endpoints — authenticated via provider JWT (magic link).

All routes here use Bearer = provider JWT, NOT a Supabase session token.
The JWT carries: provider_id, org_id, case_id, email, app_role=provider.

Routes:
  GET  /api/provider/tasks              — list tasks for this provider on their case
  PATCH /api/provider/tasks/{task_id}   — update status / note / billable amount
  GET  /api/provider/case-summary       — case budget cap + task financials
  PATCH /api/provider/profile           — provider updates display_name / company_name
                                          (marks onboarded_at on first call)

Notification logic (AIQ-4-F):
  After each provider PATCH /tasks/{id}, a notification email is sent to HR
  with 30-second debounce. The debounce table (provider_task_notification_queue)
  is checked before each send — if a notification was sent within the last 30s
  for this task, we skip. Uses Resend (RESEND_API_KEY) or logs in dev mode.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...services.provider_jwt import verify_provider_token
from ...services.supabase_client import get_supabase_admin_client
from ...services.events_tracker import track as track_event

log = logging.getLogger(__name__)

router = APIRouter(tags=["provider-portal"])

_NOTIFY_DEBOUNCE_SECONDS = 30

# ---------------------------------------------------------------------------
# Auth dependency — validate provider JWT from Bearer header
# ---------------------------------------------------------------------------

def _require_provider_jwt(
    authorization: str = Depends(
        lambda authorization: authorization  # filled in via Header dep below
    ),
) -> Dict[str, Any]:
    raise NotImplementedError("Use require_provider_jwt")


from fastapi import Header


def require_provider_jwt(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """
    Validate Bearer provider JWT. Returns decoded claims dict.
    Raises HTTP 401 if missing or invalid.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Provider Bearer token required.")
    token = authorization[7:]
    try:
        claims = verify_provider_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc
    return claims


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProviderTaskDetail(BaseModel):
    id: str
    case_id: str
    title: str
    description: Optional[str] = None
    status: str
    due_date: Optional[str] = None
    provider_note: Optional[str] = None
    billable_amount: Optional[float] = None
    hr_notes: Optional[str] = None
    created_at: str
    updated_at: str


class ProviderTasksResponse(BaseModel):
    tasks: List[ProviderTaskDetail]
    provider_name: Optional[str] = None
    case_id: str


class PatchProviderTaskBody(BaseModel):
    status: Optional[str] = None
    provider_note: Optional[str] = None
    billable_amount: Optional[float] = None


class CaseSummaryResponse(BaseModel):
    case_id: str
    budget_cap: Optional[float] = None
    currency: str = "EUR"
    tasks_total: int
    tasks_completed: int
    total_billable: Optional[float] = None


class PatchProfileBody(BaseModel):
    display_name: Optional[str] = None
    company_name: Optional[str] = None


class ProfileResponse(BaseModel):
    provider_id: str
    name: str
    display_name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    onboarded: bool


# ---------------------------------------------------------------------------
# Email helper (AIQ-4-F)
# ---------------------------------------------------------------------------

def _send_hr_notification(
    *,
    hr_email: str,
    provider_name: str,
    task_title: str,
    old_status: str,
    new_status: str,
    provider_note: Optional[str],
    case_id: str,
) -> None:
    """Send a task-status-update notification to HR via Resend (or log in dev mode)."""
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("EMAIL_FROM", "noreply@relopass.com")
    app_base = os.getenv("APP_BASE_URL", "https://app.relopass.com").rstrip("/")
    case_link = f"{app_base}/hr/command-center/cases/{case_id}"

    # Status labels
    status_label = {
        "pending": "Pending",
        "in_progress": "In Progress",
        "completed": "Completed",
        "blocked": "Blocked",
    }
    old_label = status_label.get(old_status, old_status)
    new_label = status_label.get(new_status, new_status)

    subject = f"[ReloPass] {provider_name} updated a task: {task_title}"
    plain = f"""{provider_name} has updated a task on your case.

Task:   {task_title}
Status: {old_label} → {new_label}
{f'Note:   {provider_note}' if provider_note else ''}

View the case coordination panel:
{case_link}

— The ReloPass Team
"""
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1a1a1a;max-width:600px;margin:0 auto;padding:32px 16px;">
  <img src="https://app.relopass.com/logo.png" alt="ReloPass" style="height:32px;margin-bottom:32px;">
  <h2 style="font-size:18px;font-weight:600;margin:0 0 8px;">Provider task update</h2>
  <p style="margin:0 0 20px;color:#555;line-height:1.6;">
    <strong>{provider_name}</strong> has updated a task on your case.
  </p>
  <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
    <tr><td style="padding:8px;background:#f8fafc;font-size:13px;color:#6b7280;width:80px;">Task</td>
        <td style="padding:8px;font-size:14px;font-weight:500;">{task_title}</td></tr>
    <tr><td style="padding:8px;background:#f8fafc;font-size:13px;color:#6b7280;">Status</td>
        <td style="padding:8px;font-size:14px;">
          <span style="text-decoration:line-through;color:#94a3b8;">{old_label}</span>
          &nbsp;→&nbsp;
          <strong style="color:#0b2b43;">{new_label}</strong>
        </td></tr>
    {f'<tr><td style="padding:8px;background:#f8fafc;font-size:13px;color:#6b7280;">Note</td><td style="padding:8px;font-size:14px;color:#374151;">{provider_note}</td></tr>' if provider_note else ''}
  </table>
  <a href="{case_link}"
     style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;
            padding:12px 24px;border-radius:8px;font-weight:600;font-size:14px;">
    Open coordination panel
  </a>
  <p style="margin:24px 0 0;font-size:12px;color:#888;">
    This notification was sent automatically by ReloPass. To change your notification preferences,
    visit your account settings.
  </p>
</body>
</html>"""

    if resend_key:
        resp = http_requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": from_addr, "to": [hr_email], "subject": subject,
                  "text": plain, "html": html},
            timeout=10,
        )
        if resp.ok:
            log.info("HR notification sent to %s for task update (%s→%s)", hr_email, old_status, new_status)
        else:
            log.error("Resend delivery failed: %s %s", resp.status_code, resp.text[:200])
    else:
        log.info(
            "PROVIDER TASK UPDATE NOTIFICATION (no RESEND_API_KEY): to=%s task=%s %s→%s",
            hr_email, task_title, old_status, new_status,
        )


def _maybe_notify_hr(
    *,
    task_id: str,
    org_id: str,
    case_id: str,
    provider_id: str,
    provider_name: str,
    task_title: str,
    old_status: str,
    new_status: str,
    provider_note: Optional[str],
    supa: Any,
) -> None:
    """
    Send HR notification with 30-second debounce.
    Upserts into provider_task_notification_queue; skips if sent within debounce window.
    """
    if old_status == new_status:
        return  # no status change, nothing to notify

    now = datetime.now(timezone.utc)
    debounce_cutoff = (now - timedelta(seconds=_NOTIFY_DEBOUNCE_SECONDS)).isoformat()

    # Check if we already notified recently for this task
    recent = (
        supa.table("provider_task_notification_queue")
        .select("task_id, last_notified_at")
        .eq("task_id", task_id)
        .gte("last_notified_at", debounce_cutoff)
        .limit(1)
        .execute()
    ).data or []

    if recent:
        # Update the queue record with latest status (last state wins when debounce expires)
        supa.table("provider_task_notification_queue").update({
            "last_status": new_status,
            "provider_note": provider_note,
            "last_triggered_at": now.isoformat(),
        }).eq("task_id", task_id).execute()
        log.debug("Skipping HR notification for task %s (within debounce window)", task_id)
        return

    # Outside debounce window — find HR reviewer email for this case
    # Look up cases table for the HR reviewer
    hr_email = _find_hr_email_for_case(case_id, org_id, supa)
    if not hr_email:
        log.warning("No HR email found for case %s, skipping notification", case_id)
        return

    # Upsert queue record and send
    supa.table("provider_task_notification_queue").upsert({
        "task_id": task_id,
        "org_id": org_id,
        "case_id": case_id,
        "provider_id": provider_id,
        "last_status": new_status,
        "provider_note": provider_note,
        "last_triggered_at": now.isoformat(),
        "last_notified_at": now.isoformat(),
    }).execute()

    _send_hr_notification(
        hr_email=hr_email,
        provider_name=provider_name,
        task_title=task_title,
        old_status=old_status,
        new_status=new_status,
        provider_note=provider_note,
        case_id=case_id,
    )


def _find_hr_email_for_case(case_id: str, org_id: str, supa: Any) -> Optional[str]:
    """
    Find the HR user's email for a given case.
    Strategy: look up case_assignments for created_by, then get their profile email.
    Falls back to org admin email.
    """
    # Try case_assignments table
    try:
        ca_rows = (
            supa.table("case_assignments")
            .select("created_by")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        ).data or []
        if ca_rows:
            created_by = ca_rows[0].get("created_by")
            if created_by:
                profile_rows = (
                    supa.table("profiles")
                    .select("email")
                    .eq("id", created_by)
                    .limit(1)
                    .execute()
                ).data or []
                if profile_rows and profile_rows[0].get("email"):
                    return str(profile_rows[0]["email"])
    except Exception:
        pass

    # Fallback: first HR/Admin profile in this org
    try:
        fallback = (
            supa.table("profiles")
            .select("email")
            .eq("company_id", org_id)
            .in_("role", ["HR", "ADMIN"])
            .limit(1)
            .execute()
        ).data or []
        if fallback and fallback[0].get("email"):
            return str(fallback[0]["email"])
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/provider/tasks", response_model=ProviderTasksResponse)
def get_provider_tasks(
    claims: Dict[str, Any] = Depends(require_provider_jwt),
) -> ProviderTasksResponse:
    """List all tasks assigned to this provider for their case."""
    provider_id = claims["provider_id"]
    case_id = claims["case_id"]
    supa = get_supabase_admin_client()

    tasks = (
        supa.table("provider_tasks")
        .select("id,case_id,title,description,status,due_date,provider_note,billable_amount,notes,created_at,updated_at")
        .eq("provider_id", provider_id)
        .eq("case_id", case_id)
        .order("created_at")
        .execute()
    ).data or []

    # Get provider display name
    prov = (
        supa.table("providers")
        .select("name,display_name")
        .eq("id", provider_id)
        .limit(1)
        .execute()
    ).data or []
    prov_name = (prov[0].get("display_name") or prov[0].get("name")) if prov else None

    return ProviderTasksResponse(
        tasks=[
            ProviderTaskDetail(
                id=str(t["id"]),
                case_id=str(t["case_id"]),
                title=t.get("title", ""),
                description=t.get("description"),
                status=t.get("status", "pending"),
                due_date=str(t["due_date"]) if t.get("due_date") else None,
                provider_note=t.get("provider_note"),
                billable_amount=float(t["billable_amount"]) if t.get("billable_amount") is not None else None,
                hr_notes=t.get("notes"),
                created_at=str(t.get("created_at", "")),
                updated_at=str(t.get("updated_at", "")),
            )
            for t in tasks
        ],
        provider_name=prov_name,
        case_id=case_id,
    )


@router.patch("/api/provider/tasks/{task_id}", response_model=ProviderTaskDetail)
def patch_provider_task(
    task_id: str,
    body: PatchProviderTaskBody,
    claims: Dict[str, Any] = Depends(require_provider_jwt),
) -> ProviderTaskDetail:
    """Provider updates task status, note, or billable amount. Triggers HR notification."""
    provider_id = claims["provider_id"]
    org_id = claims["org_id"]
    case_id = claims["case_id"]
    supa = get_supabase_admin_client()

    # Fetch current task (scoped to this provider)
    rows = (
        supa.table("provider_tasks")
        .select("*")
        .eq("id", task_id)
        .eq("provider_id", provider_id)
        .eq("case_id", case_id)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found.")
    task = rows[0]

    valid_statuses = {"pending", "in_progress", "completed", "blocked"}
    if body.status and body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(valid_statuses)}.")

    old_status = task.get("status", "pending")
    now_iso = datetime.now(timezone.utc).isoformat()
    updates: Dict[str, Any] = {"updated_at": now_iso}
    if body.status is not None:
        updates["status"] = body.status
    if body.provider_note is not None:
        updates["provider_note"] = body.provider_note
    if body.billable_amount is not None:
        updates["billable_amount"] = body.billable_amount

    supa.table("provider_tasks").update(updates).eq("id", task_id).execute()
    new_status = updates.get("status", old_status)

    # Trigger HR notification (AIQ-4-F) if status changed
    if body.status and body.status != old_status:
        prov_rows = (
            supa.table("providers").select("name,display_name").eq("id", provider_id).limit(1).execute()
        ).data or []
        prov_name = (prov_rows[0].get("display_name") or prov_rows[0].get("name")) if prov_rows else "Provider"

        try:
            _maybe_notify_hr(
                task_id=task_id,
                org_id=org_id,
                case_id=case_id,
                provider_id=provider_id,
                provider_name=prov_name,
                task_title=task.get("title", ""),
                old_status=old_status,
                new_status=new_status,
                provider_note=body.provider_note,
                supa=supa,
            )
        except Exception as exc:
            log.error("Notification error (non-fatal): %s", exc)

    # Emit structured event when the supplier changes task status
    if body.status and body.status != old_status:
        _PROVIDER_STATUS_TO_EVENT = {
            "in_progress": "assignment.supplier_accepted",
            "completed":   "assignment.completed",
            "blocked":     "assignment.disputed",
        }
        evt = _PROVIDER_STATUS_TO_EVENT.get(new_status)
        if evt:
            track_event(
                evt,
                entity_type="provider_task",
                entity_id=task_id,
                company_id=org_id,
                properties={
                    "case_id":      case_id,
                    "provider_id":  provider_id,
                    "old_status":   old_status,
                    "new_status":   new_status,
                    "reason_code":  body.provider_note or None,
                },
                source="api",
            )

    merged = {**task, **updates}
    return ProviderTaskDetail(
        id=str(merged["id"]),
        case_id=str(merged["case_id"]),
        title=merged.get("title", ""),
        description=merged.get("description"),
        status=merged.get("status", "pending"),
        due_date=str(merged["due_date"]) if merged.get("due_date") else None,
        provider_note=merged.get("provider_note"),
        billable_amount=float(merged["billable_amount"]) if merged.get("billable_amount") is not None else None,
        hr_notes=merged.get("notes"),
        created_at=str(merged.get("created_at", "")),
        updated_at=str(merged.get("updated_at", "")),
    )


@router.get("/api/provider/case-summary", response_model=CaseSummaryResponse)
def get_case_summary(
    claims: Dict[str, Any] = Depends(require_provider_jwt),
) -> CaseSummaryResponse:
    """Return case budget cap and task financial summary for this provider."""
    provider_id = claims["provider_id"]
    case_id = claims["case_id"]
    supa = get_supabase_admin_client()

    # Get tasks for total / completed counts + billable sum
    tasks = (
        supa.table("provider_tasks")
        .select("status,billable_amount")
        .eq("provider_id", provider_id)
        .eq("case_id", case_id)
        .execute()
    ).data or []

    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    total_billable: Optional[float] = None
    amounts = [float(t["billable_amount"]) for t in tasks if t.get("billable_amount") is not None]
    if amounts:
        total_billable = sum(amounts)

    # Try to get budget cap from case_assignments or cases table
    budget_cap: Optional[float] = None
    try:
        ca_rows = (
            supa.table("case_assignments")
            .select("budget_limit")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        ).data or []
        if ca_rows and ca_rows[0].get("budget_limit") is not None:
            budget_cap = float(ca_rows[0]["budget_limit"])
    except Exception:
        pass

    return CaseSummaryResponse(
        case_id=case_id,
        budget_cap=budget_cap,
        currency="EUR",
        tasks_total=total,
        tasks_completed=completed,
        total_billable=total_billable,
    )


@router.patch("/api/provider/profile", response_model=ProfileResponse)
def update_provider_profile(
    body: PatchProfileBody,
    claims: Dict[str, Any] = Depends(require_provider_jwt),
) -> ProfileResponse:
    """Provider updates display_name / company_name. Marks onboarded_at on first save."""
    provider_id = claims["provider_id"]
    supa = get_supabase_admin_client()

    rows = (
        supa.table("providers")
        .select("id,name,email,display_name,company_name,onboarded_at")
        .eq("id", provider_id)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Provider not found.")
    current = rows[0]

    updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.company_name is not None:
        updates["company_name"] = body.company_name
    if not current.get("onboarded_at"):
        updates["onboarded_at"] = datetime.now(timezone.utc).isoformat()

    supa.table("providers").update(updates).eq("id", provider_id).execute()
    merged = {**current, **updates}

    return ProfileResponse(
        provider_id=str(merged["id"]),
        name=merged.get("name", ""),
        display_name=merged.get("display_name"),
        company_name=merged.get("company_name"),
        email=merged.get("email"),
        onboarded=bool(merged.get("onboarded_at")),
    )

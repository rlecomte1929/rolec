"""
Personio hire-event webhook + on-demand poll  (AIQ-33-C)

Routes
------
POST /api/integrations/personio/webhook
    Receives Personio hire / employee-updated events, validates the
    HMAC-SHA256 signature, and creates draft relocation cases for any
    employee with relocation_required = true.  Acknowledges in < 200 ms
    by handing off to a BackgroundTask.

POST /api/integrations/personio/poll
    HR-admin-only manual trigger; also the target for the Supabase cron
    Edge Function (personio-hire-sync).  Runs asynchronously and returns
    a job reference immediately.

Design
------
- Idempotent: employee_id = "personio:<id>" is checked before INSERT.
- Rate-limit safe: 200 req/min Personio limit respected via delay + retry.
- Non-blocking: webhook returns 200 before any DB work starts.
- Token decryption: AES-256-GCM via hris_token_crypto.  Key from env.
- Logging: all errors go to hris_sync_log with a human-readable message.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests as http_requests
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from ..auth_deps import require_admin_or_hr
from ..services.hris_token_crypto import decrypt_token
from ...services.supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

router = APIRouter(tags=["integrations-personio"])

_PERSONIO_API_BASE = "https://api.personio.de/v1"
_RATE_LIMIT_DELAY = 0.4   # seconds between paginated Personio calls


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, header: str, secret: str) -> bool:
    """Return True if the X-Personio-Signature header is valid for *body*."""
    # Personio sends either "sha256=<hex>" or just "<hex>"
    sig = header.lower().lstrip("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def _get_attr(attributes: Dict[str, Any], key: str) -> Optional[str]:
    """Extract a scalar value from Personio's {value: ...} attribute wrapper."""
    v = attributes.get(key)
    if v is None:
        return None
    if isinstance(v, dict):
        inner = v.get("value")
        return str(inner) if inner is not None else None
    return str(v)


def _is_relocation_required(employee: Dict[str, Any]) -> bool:
    """Return True when the Personio employee is flagged for relocation."""
    attrs = employee.get("attributes", {})
    val = _get_attr(attrs, "relocation_required")
    if val is not None:
        return val.lower() in ("true", "yes", "1")
    # Fallback: any non-empty relocation_status counts
    status = _get_attr(attrs, "relocation_status")
    return bool(status and status.strip())


def _extract_fields(employee: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a Personio employee record into ReloPass-friendly fields."""
    attrs = employee.get("attributes", {})
    a = lambda k: _get_attr(attrs, k)   # noqa: E731
    return {
        "personio_id":        str(employee.get("id", "")),
        "first_name":         a("first_name") or "",
        "last_name":          a("last_name") or "",
        "email":              a("email") or "",
        "start_date":         a("hire_date") or a("start_date"),
        "nationality":        a("nationality"),
        "destination_office": a("office"),
        "home_country":       a("home_address_country") or a("nationality") or "",
        "host_country":       a("office_country") or a("work_country") or "",
    }


def _default_hr_user(supabase: Any, org_id: str) -> Optional[str]:
    """Return the first HR user for *org_id*, or None."""
    resp = (
        supabase.table("users")
        .select("id")
        .eq("company", org_id)
        .eq("role", "hr")
        .limit(1)
        .execute()
    )
    return str(resp.data[0]["id"]) if resp.data else None


def _create_draft_case(
    supabase: Any,
    fields: Dict[str, Any],
    hr_user_id: str,
    org_id: str,
) -> Optional[str]:
    """
    Insert a draft relocation case for *fields*.

    Returns the new case UUID, or None if a case already exists
    (idempotency guard on employee_id = "personio:<id>").
    """
    pid = fields["personio_id"]
    employee_id_key = f"personio:{pid}"

    existing = (
        supabase.table("relocation_cases")
        .select("id")
        .eq("employee_id", employee_id_key)
        .eq("company_id", org_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        log.info("Case already exists for Personio employee %s — skipping", pid)
        return None

    now = datetime.now(timezone.utc).isoformat()
    full_name = f"{fields['first_name']} {fields['last_name']}".strip()
    case_id = str(uuid.uuid4())

    insert_resp = supabase.table("relocation_cases").insert({
        "id":                 case_id,
        "hr_user_id":         hr_user_id,
        "company_id":         org_id,
        "employee_id":        employee_id_key,
        "status":             "draft",
        "profile_json":       json.dumps({
            "full_name":          full_name,
            "email":              fields["email"],
            "start_date":         fields.get("start_date"),
            "nationality":        fields.get("nationality"),
            "destination_office": fields.get("destination_office"),
            "source":             "personio_sync",
            "personio_id":        pid,
        }),
        "host_country":       fields.get("host_country") or "",
        "home_country":       fields.get("home_country") or "",
        "expected_start_date": fields.get("start_date"),
        "compliance_flag":    False,
        "created_at":         now,
        "updated_at":         now,
    }).execute()

    if insert_resp.data:
        log.info("Created draft case %s for Personio employee %s (%s)", case_id, pid, full_name)
        return case_id

    log.error("INSERT failed for Personio employee %s", pid)
    return None


def _fetch_personio_employees(
    access_token: str,
    api_base: str,
    updated_since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Page through Personio GET /v1/company/employees.

    Respects the 200 req/min rate limit with a brief inter-page delay
    and a 60-second back-off on 429 responses.
    """
    headers = {
        "Authorization":       f"Bearer {access_token}",
        "Accept":              "application/json",
        "X-Personio-Partner-ID": "ReloPass",
    }
    employees: List[Dict[str, Any]] = []
    page = 0

    while True:
        params: Dict[str, Any] = {"limit": 200, "offset": page * 200}
        if updated_since:
            params["updated_since"] = updated_since

        try:
            resp = http_requests.get(
                f"{api_base}/company/employees",
                headers=headers,
                params=params,
                timeout=15,
            )
        except http_requests.RequestException as exc:
            log.error("Personio API request error: %s", exc)
            break

        if resp.status_code == 429:
            log.warning("Personio rate-limit hit — backing off 60 s")
            time.sleep(60)
            continue   # retry same page

        if not resp.ok:
            log.error("Personio employees API %s: %s", resp.status_code, resp.text[:200])
            break

        batch = resp.json().get("data", [])
        employees.extend(batch)

        if len(batch) < 200:
            break   # last page
        page += 1
        time.sleep(_RATE_LIMIT_DELAY)

    return employees


def _run_poll(connection: Dict[str, Any], supabase: Any, sync_type: str = "poll") -> Dict[str, Any]:
    """
    Core polling logic: fetch employees since last_sync_at, create draft cases.

    Called from the background task (on-demand) and the cron Edge Function
    (via the /poll endpoint with service-role credentials).
    """
    conn_id  = connection["id"]
    org_id   = connection["org_id"]
    api_base = connection.get("api_base_url") or _PERSONIO_API_BASE
    last_sync = connection.get("last_sync_at")

    # Open sync log entry
    log_id = str(uuid.uuid4())
    supabase.table("hris_sync_log").insert({
        "id":           log_id,
        "connection_id": conn_id,
        "org_id":       org_id,
        "sync_type":    sync_type,
        "status":       "running",
        "started_at":   datetime.now(timezone.utc).isoformat(),
    }).execute()

    # Decrypt token
    try:
        access_token = decrypt_token(connection["access_token"])
    except Exception as exc:
        log.error("Token decryption failed for connection %s: %s", conn_id, exc)
        supabase.table("hris_sync_log").update({
            "status":       "failed",
            "error_count":  1,
            "errors_json":  [{"error": "token_decryption_failed", "detail": str(exc)}],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", log_id).execute()
        return {"status": "failed", "error": "token_decryption_failed"}

    employees = _fetch_personio_employees(access_token, api_base, updated_since=last_sync)
    relocating = [e for e in employees if _is_relocation_required(e)]

    hr_user_id = _default_hr_user(supabase, org_id) or "system"
    cases_created = 0
    errors: List[Dict[str, Any]] = []

    for emp in relocating:
        fields = _extract_fields(emp)
        try:
            cid = _create_draft_case(supabase, fields, hr_user_id, org_id)
            if cid:
                cases_created += 1
        except Exception as exc:
            log.error("Case creation failed for Personio employee %s: %s", fields.get("personio_id"), exc)
            errors.append({"personio_id": fields.get("personio_id"), "error": str(exc)})

    now = datetime.now(timezone.utc).isoformat()
    status = "completed" if not errors else ("partial" if cases_created else "failed")

    supabase.table("hris_sync_log").update({
        "status":          status,
        "new_hires_found": len(relocating),
        "cases_created":   cases_created,
        "error_count":     len(errors),
        "errors_json":     errors or None,
        "completed_at":    now,
    }).eq("id", log_id).execute()

    supabase.table("hris_connections").update({
        "last_sync_at": now,
        "last_error":   errors[0]["error"] if errors else None,
    }).eq("id", conn_id).execute()

    return {
        "status":          status,
        "new_hires_found": len(relocating),
        "cases_created":   cases_created,
        "error_count":     len(errors),
    }


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def _bg_webhook_event(payload: Dict[str, Any]) -> None:
    """Process a single Personio webhook event (background task)."""
    supabase = get_supabase_admin_client()
    event_type = payload.get("event", "unknown")
    employee = payload.get("data", payload)

    if not _is_relocation_required(employee):
        log.debug("Webhook event '%s': no relocation flag — skipping", event_type)
        return

    fields = _extract_fields(employee)
    if not fields["personio_id"]:
        log.warning("Webhook event '%s': could not extract personio_id", event_type)
        return

    # Find an active Personio connection (MVP: first match)
    conn_resp = (
        supabase.table("hris_connections")
        .select("id, org_id, last_sync_at, api_base_url")
        .eq("provider", "personio")
        .eq("status", "connected")
        .limit(1)
        .execute()
    )
    if not conn_resp.data:
        log.warning("Webhook: no active Personio connection found")
        return

    conn = conn_resp.data[0]
    org_id = conn["org_id"]
    hr_user_id = _default_hr_user(supabase, org_id) or "system"

    try:
        case_id = _create_draft_case(supabase, fields, hr_user_id, org_id)
        supabase.table("hris_sync_log").insert({
            "id":           str(uuid.uuid4()),
            "connection_id": conn["id"],
            "org_id":       org_id,
            "sync_type":    "webhook",
            "status":       "completed",
            "new_hires_found": 1,
            "cases_created":   1 if case_id else 0,
            "error_count":     0,
            "started_at":   datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        if case_id:
            log.info("Webhook: created draft case %s from Personio event '%s'", case_id, event_type)
    except Exception as exc:
        log.error("Webhook: case creation failed for employee %s: %s", fields.get("personio_id"), exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/api/integrations/personio/webhook",
    status_code=200,
    summary="Personio hire-event webhook receiver",
)
async def personio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_personio_signature: Optional[str] = Header(None, alias="X-Personio-Signature"),
) -> Dict[str, Any]:
    """
    Receive and validate a Personio webhook event.

    Signature validation requires PERSONIO_WEBHOOK_SECRET env var.
    Processing is fire-and-forget (BackgroundTask) — always returns 200
    within milliseconds to avoid Personio retry storms.
    """
    body = await request.body()

    secret = os.getenv("PERSONIO_WEBHOOK_SECRET", "")
    if secret:
        if not x_personio_signature:
            raise HTTPException(status_code=401, detail="Missing X-Personio-Signature header")
        if not _verify_signature(body, x_personio_signature, secret):
            log.warning("Personio webhook: invalid HMAC signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    background_tasks.add_task(_bg_webhook_event, payload)
    return {"ok": True, "message": "Webhook received"}


@router.post(
    "/api/integrations/personio/poll",
    summary="Manually trigger a Personio new-hire poll",
)
async def personio_poll(
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Trigger an immediate Personio employee poll for the caller's org.

    Runs asynchronously; returns a job_id for reference.
    The Supabase cron Edge Function (personio-hire-sync) hits this endpoint
    with service-role credentials every 15 minutes.
    """
    supabase = get_supabase_admin_client()
    org_id = user.get("company") or user.get("company_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Could not resolve org_id for this user")

    conn_resp = (
        supabase.table("hris_connections")
        .select("*")
        .eq("provider", "personio")
        .eq("org_id", org_id)
        .eq("status", "connected")
        .limit(1)
        .execute()
    )
    connection = (conn_resp.data or [None])[0]
    if not connection:
        raise HTTPException(status_code=404, detail="No active Personio connection for this org")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(_run_poll, connection, supabase, "poll")
    return {"ok": True, "job_id": job_id, "message": "Poll started in background"}

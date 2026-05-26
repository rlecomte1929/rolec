"""
Personio integration settings routes  (AIQ-33-B follow-up)

The 5 supporting API routes that were missing after AIQ-33-B's OAuth flow:

GET    /api/integrations/personio/status
POST   /api/integrations/personio/connect     ← client_id + client_secret → bearer token
DELETE /api/integrations/personio/disconnect
POST   /api/integrations/personio/sync        ← alias for the existing /poll logic
GET    /api/integrations/personio/sync-log
GET    /api/integrations/personio/field-mappings
PUT    /api/integrations/personio/field-mappings

Personio auth: POST https://api.personio.de/v1/auth
  body  : {"client_id": "...", "client_secret": "..."}
  returns: {"success": true, "data": {"token": "<bearer>"}}

The bearer token is AES-256-GCM encrypted via hris_token_crypto before storage
in hris_connections.access_token.  On connect we validate the credentials live
by fetching a token, then store the encrypted result.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests as http_requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ..auth_deps import require_admin_or_hr
from ..services.hris_token_crypto import decrypt_token, encrypt_token
from ..services.supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

router = APIRouter(tags=["integrations-personio"])

_PERSONIO_API_BASE = "https://api.personio.de/v1"
_REQUEST_TIMEOUT   = 15

_DEFAULT_FIELD_MAPPINGS: Dict[str, str] = {
    "first_name":          "first_name",
    "last_name":           "last_name",
    "email":               "email",
    "hire_date":           "start_date",
    "nationality":         "nationality",
    "office":              "destination_office",
    "home_address_country": "home_country",
    "office_country":      "host_country",
    "relocation_required": "relocation_required",
    "relocation_status":   "relocation_status",
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    client_id:     str
    client_secret: str


class FieldMappingsUpdate(BaseModel):
    mappings: Dict[str, str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_connection(supabase: Any, org_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table("hris_connections")
        .select("*")
        .eq("provider", "personio")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _fetch_personio_token(client_id: str, client_secret: str) -> Optional[str]:
    """Exchange client_id + client_secret for a Personio bearer token."""
    try:
        resp = http_requests.post(
            f"{_PERSONIO_API_BASE}/auth",
            json={"client_id": client_id, "client_secret": client_secret},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.ok:
            data = resp.json()
            return data.get("data", {}).get("token")
        log.warning("[personio] auth failed: %s %s", resp.status_code, resp.text[:200])
    except http_requests.RequestException as exc:
        log.error("[personio] auth request error: %s", exc)
    return None


def _test_token(token: str) -> bool:
    """Return True if the token is still valid (light employees call)."""
    try:
        resp = http_requests.get(
            f"{_PERSONIO_API_BASE}/company/employees",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"limit": 1},
            timeout=_REQUEST_TIMEOUT,
        )
        return resp.ok
    except http_requests.RequestException:
        return False


# ---------------------------------------------------------------------------
# Background sync (delegates to existing poll logic)
# ---------------------------------------------------------------------------

def _run_sync_bg(connection: Dict[str, Any], supabase: Any) -> None:
    """Re-import the existing _run_poll from the webhook router and execute it."""
    from .integrations_personio_webhook import _run_poll
    _run_poll(connection, supabase, sync_type="manual")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/api/integrations/personio/status",
    summary="Personio connection status",
)
async def personio_status(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    org_id   = user.get("company") or user.get("company_id")
    supabase = get_supabase_admin_client()
    conn     = _get_connection(supabase, org_id)

    if not conn:
        return {"connected": False, "status": "not_configured"}

    return {
        "connected":    conn["status"] == "connected",
        "status":       conn["status"],
        "api_base_url": conn.get("api_base_url") or _PERSONIO_API_BASE,
        "last_sync_at": conn.get("last_sync_at"),
        "last_error":   conn.get("last_error"),
    }


@router.post(
    "/api/integrations/personio/connect",
    summary="Connect Personio via client credentials",
)
async def personio_connect(
    body: ConnectRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Exchange client_id + client_secret for a bearer token; store encrypted."""
    org_id = user.get("company") or user.get("company_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Could not resolve org_id for this user")

    token = _fetch_personio_token(body.client_id, body.client_secret)
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Personio credentials are invalid or the auth endpoint could not be reached",
        )

    encrypted = encrypt_token(token)
    now       = datetime.now(timezone.utc).isoformat()
    supabase  = get_supabase_admin_client()
    conn      = _get_connection(supabase, org_id)

    if conn:
        supabase.table("hris_connections").update({
            "access_token": encrypted,
            "status":       "connected",
            "last_error":   None,
            "updated_at":   now,
        }).eq("id", conn["id"]).execute()
        conn_id = conn["id"]
    else:
        conn_id = str(uuid.uuid4())
        supabase.table("hris_connections").insert({
            "id":           conn_id,
            "org_id":       org_id,
            "provider":     "personio",
            "access_token": encrypted,
            "api_base_url": _PERSONIO_API_BASE,
            "status":       "connected",
            "created_at":   now,
            "updated_at":   now,
        }).execute()

    log.info("Personio connected via client credentials: org=%s", org_id)
    return {"ok": True, "connection_id": conn_id, "status": "connected"}


@router.delete(
    "/api/integrations/personio/disconnect",
    summary="Disconnect Personio integration",
)
async def personio_disconnect(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    org_id   = user.get("company") or user.get("company_id")
    supabase = get_supabase_admin_client()
    conn     = _get_connection(supabase, org_id)

    if not conn:
        raise HTTPException(status_code=404, detail="No Personio connection found")

    supabase.table("hris_connections").update({
        "status":       "disconnected",
        "access_token": None,
        "last_error":   None,
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }).eq("id", conn["id"]).execute()

    log.info("Personio disconnected: org=%s", org_id)
    return {"ok": True, "status": "disconnected"}


@router.post(
    "/api/integrations/personio/sync",
    summary="Trigger manual Personio sync",
)
async def personio_sync(
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    org_id   = user.get("company") or user.get("company_id")
    supabase = get_supabase_admin_client()
    conn     = _get_connection(supabase, org_id)

    if not conn or conn["status"] != "connected":
        raise HTTPException(status_code=404, detail="No active Personio connection found")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(_run_sync_bg, conn, supabase)
    return {"ok": True, "job_id": job_id, "message": "Sync started in background"}


@router.get(
    "/api/integrations/personio/sync-log",
    summary="Personio sync log",
)
async def personio_sync_log(
    limit: int = 20,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    org_id   = user.get("company") or user.get("company_id")
    supabase = get_supabase_admin_client()
    conn     = _get_connection(supabase, org_id)

    if not conn:
        return {"entries": []}

    resp = (
        supabase.table("hris_sync_log")
        .select("*")
        .eq("connection_id", conn["id"])
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"entries": resp.data or []}


@router.get(
    "/api/integrations/personio/field-mappings",
    summary="Get Personio field mappings",
)
async def personio_get_field_mappings(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    org_id   = user.get("company") or user.get("company_id")
    supabase = get_supabase_admin_client()
    conn     = _get_connection(supabase, org_id)

    if not conn:
        return {"mappings": _DEFAULT_FIELD_MAPPINGS}

    stored = conn.get("field_mappings")
    if stored:
        try:
            return {"mappings": json.loads(stored) if isinstance(stored, str) else stored}
        except (json.JSONDecodeError, TypeError):
            pass

    return {"mappings": _DEFAULT_FIELD_MAPPINGS}


@router.put(
    "/api/integrations/personio/field-mappings",
    summary="Update Personio field mappings",
)
async def personio_update_field_mappings(
    body: FieldMappingsUpdate,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    org_id   = user.get("company") or user.get("company_id")
    supabase = get_supabase_admin_client()
    conn     = _get_connection(supabase, org_id)

    if not conn:
        raise HTTPException(status_code=404, detail="No Personio connection found")

    supabase.table("hris_connections").update({
        "field_mappings": json.dumps(body.mappings),
        "updated_at":     datetime.now(timezone.utc).isoformat(),
    }).eq("id", conn["id"]).execute()

    return {"ok": True, "mappings": body.mappings}

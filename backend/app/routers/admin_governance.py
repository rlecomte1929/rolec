"""
Governance console (admin-only): admin-allowlist management + a global audit-trail
viewer.

Security-critical: the backend reaches these tables via the service role (RLS
bypass), so EVERY guardrail lives here in app code — `validate_grant` /
`validate_revoke` are pure + unit-tested. Every grant/revoke is audit-logged.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..auth_deps import require_admin
from ...database import db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-governance"])

ADMIN_DOMAIN = "@relopass.com"


def _missing_table(exc: Exception) -> bool:
    blob = str(getattr(exc, "orig", exc)).lower()
    return "42p01" in blob or "does not exist" in blob or "no such table" in blob


# ── allowlist guards (pure — the ONLY protection; service role bypasses RLS) ──


def validate_grant(email: str) -> Optional[str]:
    e = (email or "").strip().lower()
    if not e:
        return "email is required"
    if not e.endswith(ADMIN_DOMAIN):
        return f"admin emails must end with {ADMIN_DOMAIN}"
    return None


def validate_revoke(email: str, caller_email: str, admin_count: int) -> Optional[str]:
    e = (email or "").strip().lower()
    if admin_count <= 1:
        return "cannot revoke the last admin"
    if e == (caller_email or "").strip().lower():
        return "you cannot revoke your own admin access"
    return None


class GrantBody(BaseModel):
    email: str


@router.get("/allowlist")
def list_allowlist(_admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return {"items": db.list_admin_allowlist()}


@router.post("/allowlist")
def grant_admin(body: GrantBody, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    email = (body.email or "").strip().lower()
    err = validate_grant(email)
    if err:
        raise HTTPException(status_code=422, detail=err)
    actor = str(admin.get("id") or "")
    db.add_admin_allowlist(email, actor)
    user_id = db.resolve_user_id_by_email(email)
    if user_id:
        db.set_admin_allowlist_user_id(email, user_id)
    try:
        db.log_audit(
            actor_user_id=actor, action_type="admin_allowlist_grant",
            target_type="admin_allowlist", target_id=email,
            reason="granted from the governance console", metadata={"email": email, "user_id": user_id},
        )
    except Exception:  # audit is best-effort, never block the action
        log.warning("audit: admin grant %s", email)
    return {"ok": True, "email": email, "user_id": user_id}


@router.delete("/allowlist/{email}")
def revoke_admin(email: str, admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    email_norm = (email or "").strip().lower()
    caller = (admin.get("email") or "").strip().lower()
    err = validate_revoke(email_norm, caller, db.count_admin_allowlist())
    if err:
        raise HTTPException(status_code=409, detail=err)
    if not db.remove_admin_allowlist(email_norm):
        raise HTTPException(status_code=404, detail="not on the allowlist")
    actor = str(admin.get("id") or "")
    try:
        db.log_audit(
            actor_user_id=actor, action_type="admin_allowlist_revoke",
            target_type="admin_allowlist", target_id=email_norm,
            reason="revoked from the governance console", metadata={"email": email_norm},
        )
    except Exception:
        log.warning("audit: admin revoke %s", email_norm)
    return {"ok": True, "email": email_norm}


# ── audit-trail viewer (global, read-only) ───────────────────────────────────


def _audit_where(
    entity_type: Optional[str], action_type: Optional[str], event: Optional[str],
    actor_id: Optional[str], date_from: Optional[str], date_to: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    """Pure filter builder → (WHERE sql, params). Unit-tested."""
    clauses: List[str] = []
    params: Dict[str, Any] = {}
    if entity_type:
        clauses.append("al.entity_type = :entity_type"); params["entity_type"] = entity_type
    if action_type:
        clauses.append("al.action_type = :action_type"); params["action_type"] = action_type
    if event:
        clauses.append("al.new_value_json->>'event' = :event"); params["event"] = event
    if actor_id:
        clauses.append("al.actor_id = :actor_id"); params["actor_id"] = actor_id
    if date_from:
        clauses.append("al.created_at >= :date_from"); params["date_from"] = date_from
    if date_to:
        clauses.append("al.created_at <= :date_to"); params["date_to"] = date_to
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params


@router.get("/audit-logs")
def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    where_sql, params = _audit_where(entity_type, action_type, event, actor_id, date_from, date_to)
    params.update({"limit": limit, "offset": offset})
    try:
        with db.engine.connect() as conn:
            total = conn.execute(text(f"SELECT count(*) AS n FROM public.audit_logs al{where_sql}"), params).scalar() or 0
            rows = conn.execute(
                text(
                    f"""
                    SELECT al.id, al.entity_type, al.entity_id, al.action_type,
                           al.new_value_json->>'event' AS event,
                           al.actor_type, al.actor_id, ap.full_name AS actor_name, al.created_at
                    FROM public.audit_logs al
                    LEFT JOIN public.profiles ap ON ap.id = al.actor_id
                    {where_sql}
                    ORDER BY al.created_at DESC, al.id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()
    except (ProgrammingError, OperationalError) as exc:
        if _missing_table(exc):
            return {"items": [], "total": 0, "limit": limit, "offset": offset, "table_ready": False}
        raise
    return {"items": [dict(r) for r in rows], "total": int(total), "limit": limit, "offset": offset, "table_ready": True}

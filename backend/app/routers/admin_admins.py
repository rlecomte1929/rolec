"""Admin lifecycle management (Task 7 — A-03).

GET  /api/admin/admins         → list all admin allowlist entries
POST /api/admin/admins         → add a new admin by email (audited)
PATCH /api/admin/admins/{email} → enable/disable an admin (audited)

All routes require admin. Guards: cannot disable yourself → 400.
Dual-registered in both backend/main.py and backend/app/main.py.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Generator

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..services.admin_audit import record_admin_event

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin-admins"])


def _get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class AddAdminBody(BaseModel):
    email: str = Field(..., min_length=1)


class PatchAdminBody(BaseModel):
    enabled: bool


@router.get("/admins")
def list_admins(
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    rows = db.execute(
        text("SELECT email, enabled, added_by_user_id, created_at FROM admin_allowlist ORDER BY created_at DESC")
    ).fetchall()
    items = [
        {
            "email": r[0],
            "enabled": bool(r[1]),
            "added_by_user_id": r[2],
            "created_at": r[3],
        }
        for r in rows
    ]
    return {"items": items}


@router.post("/admins", status_code=201)
def add_admin(
    body: AddAdminBody,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    actor_id = str(user.get("id") or user.get("user_id") or "unknown")
    now = datetime.utcnow().isoformat()
    db.execute(
        text(
            "INSERT INTO admin_allowlist (email, enabled, added_by_user_id, created_at) "
            "VALUES (:email, 1, :added_by, :created_at) "
            "ON CONFLICT(email) DO UPDATE SET enabled = 1, added_by_user_id = excluded.added_by_user_id"
        ),
        {"email": email, "added_by": actor_id, "created_at": now},
    )
    record_admin_event(
        db,
        actor_id=actor_id,
        event="admin_added",
        entity="admin_allowlist",
        detail={"email": email},
    )
    return {"email": email, "enabled": True, "added_by_user_id": actor_id, "created_at": now}


@router.patch("/admins/{email}")
def patch_admin(
    email: str,
    body: PatchAdminBody,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    email_norm = email.strip().lower()
    actor_id = str(user.get("id") or user.get("user_id") or "unknown")
    actor_email = str(user.get("email") or "")

    # Guard: cannot disable yourself — fail closed when identity is ambiguous
    if not body.enabled:
        if not actor_email:
            # Attempt 1: actor_id is itself an email (legacy identifiers)
            if "@" in actor_id:
                actor_email = actor_id.lower()
            else:
                # Attempt 2: look up email from users table by actor id
                try:
                    row = db.execute(
                        text("SELECT email FROM users WHERE id = :id LIMIT 1"),
                        {"id": actor_id},
                    ).fetchone()
                    if row and row[0]:
                        actor_email = str(row[0]).strip().lower()
                except Exception:
                    pass  # table absent (SQLite tests) or actor not found
        # Fail closed: if identity is still unknown, reject rather than allow a silent bypass
        if not actor_email:
            raise HTTPException(
                status_code=400,
                detail="Cannot verify actor identity; disable rejected for safety",
            )
        if actor_email.lower() == email_norm:
            raise HTTPException(status_code=400, detail="Cannot disable your own admin account")

    result = db.execute(
        text("UPDATE admin_allowlist SET enabled = :enabled WHERE email = :email"),
        {"enabled": 1 if body.enabled else 0, "email": email_norm},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Admin not found")

    event = "admin_enabled" if body.enabled else "admin_disabled"
    record_admin_event(
        db,
        actor_id=actor_id,
        event=event,
        entity="admin_allowlist",
        detail={"email": email_norm, "enabled": body.enabled},
    )
    return {"email": email_norm, "enabled": body.enabled}

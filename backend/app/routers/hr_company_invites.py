"""[AIQ-2094 ST2] An HR user raises a colleague invite into their OWN company.

AIQ-2090 (PR #1989) removed the previous route into an existing company workspace:
`POST /api/auth/register` called `find_or_create_company_by_name`, a `LOWER(TRIM(name))`
match, so typing a customer's company name on an unauthenticated form linked the new
account into their tenant. Signup now always creates its own company — safe, but a
colleague of an existing HR user lands in a separate workspace.

This is the RAISE half of the replacement. It grants nothing: the invite lands
`pending_admin`, a ReloPass admin approves it (ST3), and only then can the colleague
accept (ST4). There is no domain matching anywhere in this design — the decision on
2026-08-30 was that every colleague passes an admin review.

THE INVARIANT: the tenant an invite grants is derived from the CALLER's own profile and
never from the request payload. `InviteBody` therefore has no `company_id` field at all —
an extra key in the body is ignored by pydantic rather than read, which is the point.
Reading it in order to reject it would still be reading it.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth_deps import require_admin_or_hr
from ..db import SessionLocal
from ...database import db

log = logging.getLogger(__name__)

router = APIRouter(tags=["hr-company-invites"])

# Statuses in which an invite still occupies its (company, email) slot. Mirrors the
# partial unique index uq_hr_company_invites_live_per_email in 20261126000000.
_LIVE_STATUSES = ("pending_admin", "approved")


def _get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _caller_company_id(user: Dict[str, Any] = Depends(require_admin_or_hr)) -> str:
    """The company the caller actually belongs to. The ONLY source of the invite's tenant.

    Resolution order copies `hr_catalog._caller_company_id` (AIQ-862): `hr_users` first,
    because legacy text HR ids (e.g. `seed-hr-testingapril`) have a NULL
    `profiles.company_id` but a valid `hr_users` row, and a profiles-only lookup would
    403 them. Unlike `auth_deps.get_org_id_for_hr_user`, which returns "" when nothing
    resolves, this raises: an invite with no tenant must never be written.

    This is a FastAPI dependency so tests can override it. The real resolution path is
    exercised by ST5's adversarial suite.
    """
    uid = user.get("id")
    company_id = (
        (db.get_hr_company_id(uid) if uid else None)
        or (db.get_profile_record(uid) or {}).get("company_id")
        or user.get("company")
    )
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — an invite needs a tenant.",
        )
    return str(company_id)


class InviteBody(BaseModel):
    """Deliberately carries ONLY the colleague's email.

    There is no `company_id` here and there must never be one: the tenant comes from
    `_caller_company_id`. A client that sends one is ignored, which is what
    `test_a_body_supplied_company_id_is_ignored` pins.
    """

    email: str = Field(..., min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, v: str) -> str:
        v = (v or "").strip()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("A valid email address is required.")
        return v


def _row_to_item(row: Any) -> Dict[str, Any]:
    m = row._mapping
    return {
        "id": m.get("id"),
        "invited_email": m.get("invited_email"),
        "status": m.get("status"),
        "invited_by_profile_id": m.get("invited_by_profile_id"),
        "created_at": str(m.get("created_at")) if m.get("created_at") is not None else None,
        "approved_at": str(m.get("approved_at")) if m.get("approved_at") is not None else None,
        "rejected_reason": m.get("rejected_reason"),
    }


@router.post("/api/hr/company/invites", status_code=201)
def issue_invite(
    body: InviteBody,
    session: Session = Depends(_get_db),
    company_id: str = Depends(_caller_company_id),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Raise an invite for a colleague, into the caller's own company, as `pending_admin`.

    Grants nothing. No token is minted and no email is sent here — ST3 does that on
    approval, which is why `token_hash` and `expires_at` stay NULL until then.
    """
    invite_id = str(uuid.uuid4())
    inviter = str(user.get("id") or "")

    try:
        # SAVEPOINT, not a bare transaction. session.rollback() here would discard
        # everything else the caller's transaction had done; begin_nested() unwinds only
        # the failed INSERT and leaves the surrounding transaction usable.
        with session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO hr_company_invites "
                    "  (id, company_id, invited_email, invited_by_profile_id, status) "
                    "VALUES (:id, :company_id, :email, :inviter, 'pending_admin')"
                ),
                # company_id is bound as a plain str: psycopg2 sends it as an untyped literal
                # which Postgres coerces into the uuid column, and SQLite stores it as
                # text. Do NOT write `:company_id::uuid` — that bind-adjacent cast breaks
                # the driver.
                {"id": invite_id, "company_id": company_id, "email": body.email,
                 "inviter": inviter},
            )
    except IntegrityError:
        # uq_hr_company_invites_live_per_email: one live invite per (company, lower(email)).
        # Surfaced as 409 — letting this escape would be a 500 on an ordinary double-click.
        # The savepoint above has already unwound the failed INSERT.
        raise HTTPException(
            status_code=409,
            detail="That colleague already has an invite awaiting review for this company.",
        )

    log.info(
        "hr_company_invite issued id=%s company_id=%s by=%s", invite_id, company_id, inviter
    )
    return {
        "id": invite_id,
        "invited_email": body.email,
        "status": "pending_admin",
        "message": "Invite raised. A ReloPass admin reviews it before your colleague gets access.",
    }


@router.get("/api/hr/company/invites")
def list_invites(
    session: Session = Depends(_get_db),
    company_id: str = Depends(_caller_company_id),
    # Transitively guarded already — _caller_company_id depends on require_admin_or_hr —
    # but declared explicitly so the guard (and a reader) can see it without tracing the
    # dependency chain. scripts/check_route_auth.py does not follow indirection.
    _user: Dict[str, Any] = Depends(require_admin_or_hr),
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Every invite for the caller's own company. Scoped in SQL, never in the caller."""
    sql = (
        "SELECT id, invited_email, status, invited_by_profile_id, created_at, "
        "       approved_at, rejected_reason "
        "FROM hr_company_invites WHERE company_id = :company_id"
    )
    params: Dict[str, Any] = {"company_id": company_id}
    if status:
        sql += " AND status = :status"
        params["status"] = status
    sql += " ORDER BY created_at DESC"

    rows = session.execute(text(sql), params).fetchall()
    return {"items": [_row_to_item(r) for r in rows], "count": len(rows)}

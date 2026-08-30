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
from datetime import datetime, timedelta, timezone
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
                # company_id is bound as a plain str: psycopg2 sends it as an untyped
                # literal which Postgres coerces into the uuid column, and SQLite stores
                # it as text. Verified through SQLAlchemy against prod — both str and
                # uuid.UUID round-trip correctly, so no cast is needed here at all.
                # If one ever is, use the CAST(:param AS type) form: the double-colon
                # suffix form binds a truncated name and leaves a literal placeholder in
                # the SQL, which Postgres rejects and SQLite silently masks. See
                # backend/tests/test_jsonb_bind_cast.py.
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


# ─────────────────────────────────────────────────────────────────────────────
# [AIQ-2094 ST3] The admin review gate.
#
# Decision, 2026-08-30: the admin keeps control of who in a company can use the
# system. ST2 lets an HR user RAISE an invite; nothing reaches the colleague until
# an admin acts here, and ST4 honours `approved` and nothing else.
#
# Two invariants carry this stage:
#   1. Only `pending_admin` may transition. Every guard is expressed in the UPDATE's
#      own WHERE clause, so the check and the write are ONE atomic statement — a
#      read-then-write would let two concurrent approvals both pass the read.
#      A replay is 409 and mutates nothing; otherwise it would mint a SECOND live
#      token for an invite that may since have been accepted or revoked.
#   2. The raw accept token is returned to the admin exactly once and never stored.
#      Only sha256 is persisted, so a database leak yields no working invite links.
#      Same convention as corridor_attestation_requests.link_token_hash.
# ─────────────────────────────────────────────────────────────────────────────
import hashlib  # noqa: E402
import secrets  # noqa: E402

from ..auth_deps import require_admin  # noqa: E402
from ..services.admin_audit import record_admin_event  # noqa: E402

# How long an approved invite stays acceptable. ST4 refuses an expired one and
# flips it to 'expired'.
_INVITE_TTL_DAYS = 14


class RejectBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


def _admin_row(session: Session, invite_id: str) -> Any:
    return session.execute(
        text("SELECT id, company_id, invited_email, status FROM hr_company_invites "
             "WHERE id = :id"),
        {"id": invite_id},
    ).fetchone()


@router.get("/api/admin/company-invites")
def admin_list_company_invites(
    session: Session = Depends(_get_db),
    _user: Dict[str, Any] = Depends(require_admin),
    status: str = "pending_admin",
) -> Dict[str, Any]:
    """The review queue: pending invites across ALL companies, newest first.

    Deliberately not tenant-scoped — this is the ReloPass admin's cross-customer
    queue, and `require_admin` is the boundary. Defaults to `pending_admin` so the
    queue shows work to do rather than history.
    """
    sql = ("SELECT id, company_id, invited_email, status, invited_by_profile_id, "
           "       created_at, approved_at, rejected_reason "
           "FROM hr_company_invites")
    params: Dict[str, Any] = {}
    if status and status != "all":
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " ORDER BY created_at DESC"

    rows = session.execute(text(sql), params).fetchall()
    items = []
    for r in rows:
        item = _row_to_item(r)
        item["company_id"] = r._mapping.get("company_id")
        items.append(item)
    return {"items": items, "count": len(items)}


@router.post("/api/admin/company-invites/{invite_id}/approve")
def admin_approve_company_invite(
    invite_id: str,
    session: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Approve a pending invite and mint its accept token.

    The token is returned here ONCE. Only its sha256 is stored.
    """
    row = _admin_row(session, invite_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Invite not found.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=_INVITE_TTL_DAYS)
    admin_id = str(user.get("id") or "")

    # The status guard lives in the WHERE clause, so check-and-write is atomic.
    result = session.execute(
        text("UPDATE hr_company_invites "
             "SET status = 'approved', approved_by_admin_id = :admin, "
             "    approved_at = :now, token_hash = :hash, expires_at = :expires, "
             "    updated_at = :now "
             "WHERE id = :id AND status = 'pending_admin'"),
        {"admin": admin_id, "now": datetime.now(timezone.utc).isoformat(),
         "hash": token_hash, "expires": expires_at.isoformat(), "id": invite_id},
    )
    if result.rowcount == 0:
        # Row exists (checked above) but was not pending — a replay or a race.
        raise HTTPException(
            status_code=409,
            detail=f"This invite is '{row._mapping.get('status')}', not awaiting review.",
        )

    record_admin_event(
        session, actor_id=admin_id, event="company_invite.approve",
        entity="hr_company_invites", entity_id=invite_id,
        detail={"company_id": str(row._mapping.get("company_id")),
                "invited_email": row._mapping.get("invited_email")},
    )
    log.info("company_invite approved id=%s by=%s", invite_id, admin_id)
    return {
        "id": invite_id,
        "status": "approved",
        # Shown to the admin once. Never persisted, never retrievable again.
        "accept_token": raw_token,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/api/admin/company-invites/{invite_id}/reject")
def admin_reject_company_invite(
    invite_id: str,
    body: Optional[RejectBody] = None,
    session: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Reject a pending invite. No token is ever minted for it.

    Rejecting frees the (company, email) slot: ST1's unique index is partial over
    live statuses only, so the colleague can be re-invited later.
    """
    row = _admin_row(session, invite_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Invite not found.")

    admin_id = str(user.get("id") or "")
    reason = (body.reason if body else None) or None

    result = session.execute(
        text("UPDATE hr_company_invites "
             "SET status = 'rejected', rejected_reason = :reason, "
             "    approved_by_admin_id = :admin, updated_at = :now "
             "WHERE id = :id AND status = 'pending_admin'"),
        {"reason": reason, "admin": admin_id,
         "now": datetime.now(timezone.utc).isoformat(), "id": invite_id},
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=409,
            detail=f"This invite is '{row._mapping.get('status')}', not awaiting review.",
        )

    record_admin_event(
        session, actor_id=admin_id, event="company_invite.reject",
        entity="hr_company_invites", entity_id=invite_id,
        detail={"company_id": str(row._mapping.get("company_id")), "reason": reason},
    )
    log.info("company_invite rejected id=%s by=%s", invite_id, admin_id)
    return {"id": invite_id, "status": "rejected", "rejected_reason": reason}

"""
Single canonical path for HR/Admin assignment creation (contact + case row + invites).
Does not create auth users or touch signup tables.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

log = logging.getLogger(__name__)

from ...identity_normalize import email_normalized_from_identifier, normalize_invite_key
from ...identity_observability import identity_event

from .assignment_mobility_link_service import ensure_mobility_case_link_for_assignment
from .employee_case_person_service import ensure_employee_case_person_for_assignment
from .passport_case_document_sync_service import ensure_passport_case_document_for_assignment

if TYPE_CHECKING:
    from ...database import Database


@dataclass(frozen=True)
class UnifiedAssignmentCreationResult:
    assignment_id: str
    case_id: str
    employee_contact_id: Optional[str]
    stored_identifier: str
    invite_token: Optional[str]
    employee_user_id: Optional[str]


def _link_contact_post_create(
    db: "Database",
    assignment_id: str,
    *,
    request_id: Optional[str] = None,
) -> None:
    """Deferred: link employee_contact → auth user after the assignment row exists.

    B3-fix: this call was previously inline in create_assignment_with_contact_and_invites
    and could hang (waiting for a DB lock or a slow pooler connection) inside the
    20-second synchronous window, causing 503 timeouts.  Running it here — after the
    assignment row is committed and control has returned to the caller — keeps it
    safely out of the critical path.
    """
    try:
        from sqlalchemy import text as _text  # local import to avoid circular at module level

        with db.engine.connect() as conn:
            row = conn.execute(
                _text(
                    "SELECT employee_contact_id, employee_user_id "
                    "FROM case_assignments WHERE id = :aid LIMIT 1"
                ),
                {"aid": assignment_id},
            ).fetchone()
        if not row:
            return
        m = row._mapping if hasattr(row, "_mapping") else dict(row)
        ecid = (str(m.get("employee_contact_id") or "")).strip()
        euid = (str(m.get("employee_user_id") or "")).strip()
        if ecid and euid:
            db.link_employee_contact_to_auth_user(ecid, euid, request_id=request_id)
            log.info(
                "link_contact_post_create done assignment_id=%s ecid=%s request_id=%s",
                assignment_id,
                ecid[:8],
                request_id,
            )
    except Exception as exc:
        log.warning(
            "link_contact_post_create failed assignment_id=%s: %s",
            assignment_id,
            exc,
        )


def run_assignment_post_creation_hooks(
    db: "Database",
    assignment_id: str,
    *,
    request_id: Optional[str] = None,
) -> None:
    """Run the idempotent ensure_* hooks that previously ran inline.

    Each is wrapped in try/except so a slow or failing hook never blocks the
    next one. Callers that defer the hooks (via
    create_assignment_with_contact_and_invites(..., defer_post_creation_hooks=True))
    should dispatch this to a background thread so the assignment response
    isn't held by Supabase RTT for the mobility/case-person/passport sync.

    Also runs _link_contact_post_create (B3-fix) which was previously inline
    and could cause 20-second hangs when a DB lock delayed the pooler connection.
    """
    # B3-fix: link employee_contact → auth user in background, not on critical path
    _link_contact_post_create(db, assignment_id, request_id=request_id)
    try:
        ensure_mobility_case_link_for_assignment(db, assignment_id, request_id=request_id)
    except Exception as exc:
        log.warning(
            "ensure_mobility_case_link_for_assignment failed assignment_id=%s: %s",
            assignment_id,
            exc,
        )
    try:
        ensure_employee_case_person_for_assignment(db, assignment_id, request_id=request_id)
    except Exception as exc:
        log.warning(
            "ensure_employee_case_person_for_assignment failed assignment_id=%s: %s",
            assignment_id,
            exc,
        )
    try:
        ensure_passport_case_document_for_assignment(db, assignment_id, request_id=request_id)
    except Exception as exc:
        log.warning(
            "ensure_passport_case_document_for_assignment failed assignment_id=%s: %s",
            assignment_id,
            exc,
        )


def create_assignment_with_contact_and_invites(
    db: "Database",
    *,
    company_id: str,
    hr_user_id: str,
    case_id: str,
    employee_identifier_raw: str,
    employee_first_name: Optional[str],
    employee_last_name: Optional[str],
    employee_user_id: Optional[str],
    assignment_status: str,
    request_id: Optional[str],
    assignment_id: Optional[str] = None,
    observability_channel: Optional[str] = None,
    defer_post_creation_hooks: bool = False,
) -> UnifiedAssignmentCreationResult:
    """
    Canonical steps:
    1) Normalize identifier (and derive normalized email when applicable).
    2) Resolve employee contact by company + normalized email, else company + invite key.
    3) Create contact if missing (no auth).
    4) Optionally link contact to an existing auth user (idempotent).
    5) Create case_assignment row.
    6) Ensure pending legacy + claim invites when there is no employee_user_id.

    Sentinel `admin-created` skips contact + invites (placeholder assignment).
    """
    raw = (employee_identifier_raw or "").strip()
    cid = (company_id or "").strip()

    if raw == "admin-created":
        stored_identifier = "admin-created"
        employee_contact_id: Optional[str] = None
        invite_token: Optional[str] = None
        aid = assignment_id or str(uuid.uuid4())
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr_user_id,
            employee_user_id=employee_user_id,
            employee_identifier=stored_identifier,
            status=assignment_status,
            request_id=request_id,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
            employee_contact_id=None,
        )
        identity_event(
            "identity.assign.created",
            channel=observability_channel or "unspecified",
            variant="admin_placeholder",
            request_id=request_id,
            company_id=cid,
            assignment_id=aid,
            pre_linked_auth_user=bool(employee_user_id),
        )
        if not defer_post_creation_hooks:
            run_assignment_post_creation_hooks(db, aid, request_id=request_id)
        return UnifiedAssignmentCreationResult(
            assignment_id=aid,
            case_id=case_id,
            employee_contact_id=None,
            stored_identifier=stored_identifier,
            invite_token=None,
            employee_user_id=employee_user_id,
        )

    stored_identifier = normalize_invite_key(raw)
    if not stored_identifier:
        raise ValueError("Employee identifier is required")

    if not cid:
        raise ValueError("company_id is required for employee contact resolution")

    employee_contact_id = db.resolve_or_create_employee_contact(
        cid,
        raw,
        first_name=employee_first_name,
        last_name=employee_last_name,
        request_id=request_id,
    )
    # B3-fix: skip the inline link when defer_post_creation_hooks=True so this
    # potentially-slow DB write doesn't block the critical-path 20 s window.
    # _link_contact_post_create() in run_assignment_post_creation_hooks handles it.
    if employee_user_id and not defer_post_creation_hooks:
        db.link_employee_contact_to_auth_user(
            employee_contact_id, employee_user_id, request_id=request_id
        )

    aid = assignment_id or str(uuid.uuid4())
    pending_mode = "pending_claim" if not employee_user_id else None
    db.create_assignment(
        assignment_id=aid,
        case_id=case_id,
        hr_user_id=hr_user_id,
        employee_user_id=employee_user_id,
        employee_identifier=stored_identifier,
        status=assignment_status,
        request_id=request_id,
        employee_first_name=employee_first_name,
        employee_last_name=employee_last_name,
        employee_contact_id=employee_contact_id,
        employee_link_mode=pending_mode,
    )

    invite_token: Optional[str] = None
    if not employee_user_id:
        en = email_normalized_from_identifier(raw)
        try:
            invite_token = db.ensure_pending_assignment_invites(
                aid,
                case_id,
                hr_user_id,
                employee_contact_id,
                stored_identifier,
                en,
                request_id=request_id,
            )
        except Exception as exc:
            log.warning("ensure_pending_assignment_invites failed assignment_id=%s: %s", aid, exc)
            invite_token = None

    identity_event(
        "identity.assign.created",
        channel=observability_channel or "unspecified",
        request_id=request_id,
        company_id=cid,
        assignment_id=aid,
        employee_contact_id=employee_contact_id,
        has_pending_invite=bool(invite_token),
        pre_linked_auth_user=bool(employee_user_id),
    )

    if not defer_post_creation_hooks:
        run_assignment_post_creation_hooks(db, aid, request_id=request_id)

    return UnifiedAssignmentCreationResult(
        assignment_id=aid,
        case_id=case_id,
        employee_contact_id=employee_contact_id,
        stored_identifier=stored_identifier,
        invite_token=invite_token,
        employee_user_id=employee_user_id,
    )

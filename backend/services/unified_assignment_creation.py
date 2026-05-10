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

from ..identity_normalize import email_normalized_from_identifier, normalize_invite_key
from ..identity_observability import identity_event

from .assignment_mobility_link_service import ensure_mobility_case_link_for_assignment
from .employee_case_person_service import ensure_employee_case_person_for_assignment
from .passport_case_document_sync_service import ensure_passport_case_document_for_assignment

if TYPE_CHECKING:
    from ..database import Database


@dataclass(frozen=True)
class UnifiedAssignmentCreationResult:
    assignment_id: str
    case_id: str
    employee_contact_id: Optional[str]
    stored_identifier: str
    invite_token: Optional[str]
    employee_user_id: Optional[str]


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
        try:
            ensure_mobility_case_link_for_assignment(db, aid, request_id=request_id)
        except Exception as exc:
            log.warning("ensure_mobility_case_link_for_assignment failed assignment_id=%s: %s", aid, exc)
        try:
            ensure_employee_case_person_for_assignment(db, aid, request_id=request_id)
        except Exception as exc:
            log.warning("ensure_employee_case_person_for_assignment failed assignment_id=%s: %s", aid, exc)
        try:
            ensure_passport_case_document_for_assignment(db, aid, request_id=request_id)
        except Exception as exc:
            log.warning("ensure_passport_case_document_for_assignment failed assignment_id=%s: %s", aid, exc)
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
    if employee_user_id:
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

    try:
        ensure_mobility_case_link_for_assignment(db, aid, request_id=request_id)
    except Exception as exc:
        log.warning("ensure_mobility_case_link_for_assignment failed assignment_id=%s: %s", aid, exc)
    try:
        ensure_employee_case_person_for_assignment(db, aid, request_id=request_id)
    except Exception as exc:
        log.warning("ensure_employee_case_person_for_assignment failed assignment_id=%s: %s", aid, exc)
    try:
        ensure_passport_case_document_for_assignment(db, aid, request_id=request_id)
    except Exception as exc:
        log.warning("ensure_passport_case_document_for_assignment failed assignment_id=%s: %s", aid, exc)

    return UnifiedAssignmentCreationResult(
        assignment_id=aid,
        case_id=case_id,
        employee_contact_id=employee_contact_id,
        stored_identifier=stored_identifier,
        invite_token=invite_token,
        employee_user_id=employee_user_id,
    )

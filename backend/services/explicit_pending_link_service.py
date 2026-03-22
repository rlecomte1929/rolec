"""
Explicit link path for pending_claim assignments shown on the employee hub.

Stricter than POST .../claim: the assignment must be pending_claim, tied to an employee_contact
already linked to the auth user, pass company alignment (same rules as assignment overview), and
pass claim-invite gates. Manual UUID claim remains on the generic claim endpoint.

Idempotent: if already linked to the same user, returns success without duplicate writes.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..identity_observability import identity_event, principal_fingerprint

if TYPE_CHECKING:
    from ..database import Database

log = logging.getLogger(__name__)

# Evaluation outcomes (internal; main.py maps to HTTP + IdentityErrorCode)
PENDING_LINK_ALREADY_LINKED = "already_linked"
PENDING_LINK_ELIGIBLE = "eligible"
PENDING_LINK_NOT_FOUND = "not_found"
PENDING_LINK_OTHER_OWNER = "other_owner"
PENDING_LINK_NOT_PENDING = "not_pending"
PENDING_LINK_NO_CONTACT = "no_contact"
PENDING_LINK_CONTACT_NOT_LINKED = "contact_not_linked"
PENDING_LINK_IDENTITY_MISMATCH = "identity_mismatch"
PENDING_LINK_COMPANY_MISMATCH = "company_mismatch"
PENDING_LINK_INVITE_REVOKED = "invite_revoked"
PENDING_LINK_EXTRA_VERIFICATION = "extra_verification"


def _invite_blocks_explicit_pending_link(statuses: List[str]) -> Optional[str]:
    """
    Align with employee_assignment_overview._claim_summary invite UX.
    Returns None if link may proceed, else 'revoked' or 'extra_verification'.
    """
    if not statuses:
        return None
    if "pending" in statuses:
        return None
    if "claimed" in statuses:
        return None
    if all(x == "revoked" for x in statuses):
        return "revoked"
    return "extra_verification"


def evaluate_pending_explicit_link_eligibility(
    db: "Database",
    *,
    auth_user_id: str,
    assignment_id: str,
    user_identifiers: List[str],
    request_id: Optional[str] = None,
) -> str:
    uid = (auth_user_id or "").strip()
    aid = (assignment_id or "").strip()
    if not uid or not aid:
        return PENDING_LINK_NOT_FOUND

    asn = db.get_assignment_by_id(aid, request_id=request_id)
    if not asn:
        return PENDING_LINK_NOT_FOUND

    emp_uid = (str(asn.get("employee_user_id") or "")).strip()
    if emp_uid == uid:
        return PENDING_LINK_ALREADY_LINKED
    if emp_uid:
        return PENDING_LINK_OTHER_OWNER

    mode = (str(asn.get("employee_link_mode") or "")).strip().lower()
    if mode != "pending_claim":
        return PENDING_LINK_NOT_PENDING

    ecid = (str(asn.get("employee_contact_id") or "")).strip()
    if not ecid:
        return PENDING_LINK_NO_CONTACT

    ec = db.get_employee_contact_by_id(ecid, request_id=request_id)
    if not ec:
        return PENDING_LINK_NO_CONTACT

    linked = (str(ec.get("linked_auth_user_id") or "")).strip()
    if linked != uid:
        return PENDING_LINK_CONTACT_NOT_LINKED

    if not db.assignment_identity_matches_user_identifiers(asn, user_identifiers, request_id=request_id):
        return PENDING_LINK_IDENTITY_MISMATCH

    case_id = (str(asn.get("case_id") or asn.get("canonical_case_id") or "")).strip()
    ec_comp = (str(ec.get("company_id") or "")).strip()
    rc_comp = ""
    if case_id:
        rc = db.get_relocation_case(case_id)
        if rc:
            rc_comp = (str(rc.get("company_id") or "")).strip()
    if rc_comp and ec_comp and rc_comp != ec_comp:
        return PENDING_LINK_COMPANY_MISMATCH

    st = db.list_assignment_claim_invite_statuses(aid)
    block = _invite_blocks_explicit_pending_link(st)
    if block == "revoked":
        return PENDING_LINK_INVITE_REVOKED
    if block == "extra_verification":
        return PENDING_LINK_EXTRA_VERIFICATION

    return PENDING_LINK_ELIGIBLE


def finalize_assignment_claim_attach(
    db: "Database",
    *,
    assignment_id: str,
    employee_user_id: str,
    assignment: Dict[str, Any],
    request_id: Optional[str] = None,
    identity_event_name: str,
    identity_outcome: str,
    claim_req_id: str = "",
    principal_email: Optional[str] = None,
    principal_username: Optional[str] = None,
    case_event_payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Attach employee, mark invites claimed, ensure participant, emit case event + identity telemetry."""
    case_id = (assignment.get("case_id") or assignment.get("canonical_case_id") or "").strip()
    db.attach_employee_to_assignment(assignment_id, employee_user_id, request_id=request_id)
    db.mark_invites_claimed(
        assignment.get("employee_identifier") or "",
        claimed_by_user_id=employee_user_id,
        assignment_id=assignment_id,
    )
    now_iso = datetime.utcnow().isoformat()
    if case_id:
        try:
            db.ensure_case_participant(
                case_id=case_id,
                person_id=employee_user_id,
                role="relocatee",
                joined_at=now_iso,
                request_id=request_id,
            )
        except Exception as exc:
            log.warning(
                "ensure_case_participant skipped assignment_id=%s case_id=%s error=%s",
                assignment_id,
                case_id,
                str(exc),
            )
    try:
        if case_id:
            db.insert_case_event(
                case_id=case_id,
                assignment_id=assignment_id,
                actor_principal_id=employee_user_id,
                event_type="assignment.claimed",
                payload=case_event_payload or {},
                request_id=request_id,
            )
    except Exception as exc:
        log.warning(
            "insert_case_event skipped assignment_id=%s case_id=%s error=%s",
            assignment_id,
            case_id,
            str(exc),
        )
    identity_event(
        identity_event_name,
        outcome=identity_outcome,
        request_id=claim_req_id or None,
        assignment_id=assignment_id,
        auth_user_id=employee_user_id,
        principal_fingerprint=principal_fingerprint(principal_email, principal_username),
    )


def execute_pending_explicit_link(
    db: "Database",
    *,
    auth_user_id: str,
    assignment_id: str,
    user_identifiers: List[str],
    request_id: Optional[str] = None,
    claim_req_id: str = "",
    principal_email: Optional[str] = None,
    principal_username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate eligibility and attach when eligible. Returns API dict:
    { success, assignmentId, alreadyLinked }.
    """
    aid = (assignment_id or "").strip()
    uid = (auth_user_id or "").strip()
    outcome = evaluate_pending_explicit_link_eligibility(
        db,
        auth_user_id=uid,
        assignment_id=aid,
        user_identifiers=user_identifiers,
        request_id=request_id,
    )
    if outcome == PENDING_LINK_ALREADY_LINKED:
        identity_event(
            "identity.claim.pending_explicit",
            outcome="idempotent_already_linked",
            request_id=claim_req_id or None,
            assignment_id=aid,
            auth_user_id=uid,
            principal_fingerprint=principal_fingerprint(principal_email, principal_username),
        )
        return {"success": True, "assignmentId": aid, "alreadyLinked": True}

    if outcome != PENDING_LINK_ELIGIBLE:
        return {"success": False, "reason": outcome, "assignmentId": aid}

    asn = db.get_assignment_by_id(aid, request_id=request_id) or {}
    finalize_assignment_claim_attach(
        db,
        assignment_id=aid,
        employee_user_id=uid,
        assignment=asn,
        request_id=request_id,
        identity_event_name="identity.claim.pending_explicit",
        identity_outcome="attached",
        claim_req_id=claim_req_id,
        principal_email=principal_email,
        principal_username=principal_username,
        case_event_payload={"path": "explicit_pending_link"},
    )
    return {"success": True, "assignmentId": aid, "alreadyLinked": False}

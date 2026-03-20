"""
Canonical auto-claim / link path for employees after login, signup, or loading employee routes.

Idempotent: safe to call repeatedly. Company isolation via employee_contact rows; legacy rows match
normalized identifier only. Revoked-only claim invites block auto-attach for that assignment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from ..identity_normalize import normalize_invite_key
from ..identity_observability import identity_event, principal_fingerprint

if TYPE_CHECKING:
    from ..database import Database

log = logging.getLogger(__name__)


@dataclass
class ClaimLinkResult:
    linked_contact_ids: List[str] = field(default_factory=list)
    newly_attached_assignment_ids: List[str] = field(default_factory=list)
    skipped_contacts_linked_to_other_user: int = 0
    skipped_assignments_linked_to_other_user: int = 0
    skipped_revoked_invites: int = 0
    skipped_already_linked_same_user: int = 0

    def to_api_dict(self) -> Dict[str, Any]:
        """Shape for PostSignupReconciliation / login reconciliation."""
        n_new = len(self.newly_attached_assignment_ids)
        headline: Optional[str] = None
        message: Optional[str] = None
        if n_new > 0:
            headline = "We found relocation case(s) associated with your email"
            message = (
                f"We linked {n_new} relocation assignment(s) to your account. "
                "Open **My case** to continue your intake."
            )
        elif self.linked_contact_ids and not self.newly_attached_assignment_ids:
            headline = "Your profile is connected"
            message = (
                "Your account is linked to your company contact record. "
                "When HR assigns a relocation to you, it will appear here automatically."
            )
        return {
            "linkedContactIds": list(self.linked_contact_ids),
            "attachedAssignmentIds": list(self.newly_attached_assignment_ids),
            "skippedContactsLinkedToOtherUser": self.skipped_contacts_linked_to_other_user,
            "skippedAssignmentsLinkedToOtherUser": self.skipped_assignments_linked_to_other_user,
            "skippedRevokedInvites": self.skipped_revoked_invites,
            "skippedAlreadyLinkedSameUser": self.skipped_already_linked_same_user,
            "headline": headline,
            "message": message,
        }


def _principal_identifiers(email: Optional[str], username: Optional[str]) -> Set[str]:
    out: Set[str] = set()
    for raw in (email, username):
        if raw and str(raw).strip():
            out.add(normalize_invite_key(str(raw)))
    return {x for x in out if x}


def _collect_employee_contacts(db: "Database", idents: Set[str], request_id: Optional[str]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    # Email-shaped keys → signup-style match (email_normalized + invite_key)
    for ident in idents:
        if "@" in ident:
            for row in db.list_employee_contacts_matching_signup_email(ident, request_id=request_id):
                rid = (row.get("id") or "").strip()
                if rid:
                    by_id[rid] = row
    # Username (and any invite_key exact match)
    for ident in idents:
        for row in db.list_employee_contacts_by_invite_key(ident, request_id=request_id):
            rid = (row.get("id") or "").strip()
            if rid:
                by_id[rid] = row
    return list(by_id.values())


def _try_attach_assignment(
    db: "Database",
    *,
    user_id: str,
    assignment: Dict[str, Any],
    mark_identifier: str,
    request_id: Optional[str],
    emit_side_effects: bool,
    result: ClaimLinkResult,
) -> None:
    aid = (assignment.get("id") or "").strip()
    if not aid:
        return

    fresh = db.get_assignment_by_id(aid, request_id=request_id) or {}
    current = (fresh.get("employee_user_id") or "").strip()
    if current == user_id:
        result.skipped_already_linked_same_user += 1
        identity_event(
            "identity.reconcile.attach_skipped",
            reason="idempotent_same_user",
            request_id=request_id,
            assignment_id=aid,
            auth_user_id=user_id,
        )
        return
    if current and current != user_id:
        result.skipped_assignments_linked_to_other_user += 1
        log.info(
            "claim_link skip assignment %s owned by other user",
            aid[:8],
        )
        identity_event(
            "identity.reconcile.attach_skipped",
            reason="other_owner",
            request_id=request_id,
            assignment_id=aid,
            auth_user_id=user_id,
        )
        return

    if db.is_assignment_auto_claim_blocked_by_revoked_invites(aid):
        result.skipped_revoked_invites += 1
        log.info("claim_link skip assignment %s revoked invites only", aid[:8])
        identity_event(
            "identity.reconcile.attach_skipped",
            reason="revoked_invites_only",
            request_id=request_id,
            assignment_id=aid,
            auth_user_id=user_id,
        )
        return

    db.attach_employee_to_assignment(aid, user_id, request_id=request_id)
    db.mark_invites_claimed(
        mark_identifier,
        claimed_by_user_id=user_id,
        assignment_id=aid,
    )
    if aid not in result.newly_attached_assignment_ids:
        result.newly_attached_assignment_ids.append(aid)

    if emit_side_effects:
        case_id = fresh.get("case_id") or assignment.get("case_id") or ""
        now_iso = datetime.utcnow().isoformat()
        try:
            db.ensure_case_participant(
                case_id=case_id,
                person_id=user_id,
                role="relocatee",
                joined_at=now_iso,
                request_id=request_id,
            )
        except Exception as exc:
            log.warning("ensure_case_participant claim_link assignment_id=%s error=%s", aid, exc)
        try:
            db.insert_case_event(
                case_id=case_id,
                assignment_id=aid,
                actor_principal_id=user_id,
                event_type="assignment.claimed",
                payload={},
                request_id=request_id,
            )
        except Exception as exc:
            log.warning("insert_case_event claim_link assignment_id=%s error=%s", aid, exc)


def reconcile_pending_assignment_claims(
    db: "Database",
    *,
    user_id: str,
    email: Optional[str],
    username: Optional[str],
    role: str,
    request_id: Optional[str] = None,
    emit_side_effects: bool = True,
) -> ClaimLinkResult:
    """
    Discover pending assignments for this principal, link contacts, attach assignments, mark invites.
    """
    r = (role or "").strip().upper()
    if r not in ("EMPLOYEE", "EMPLOYEE_USER"):
        identity_event(
            "identity.reconcile.complete",
            request_id=request_id,
            auth_user_id=user_id,
            outcome="skipped_non_employee_role",
            role=r,
        )
        return ClaimLinkResult()

    idents = _principal_identifiers(email, username)
    if not idents:
        identity_event(
            "identity.reconcile.complete",
            request_id=request_id,
            auth_user_id=user_id,
            outcome="skipped_no_principal_identifiers",
            contacts_matched=0,
            linked_contacts=0,
            new_attachments=0,
        )
        return ClaimLinkResult()

    result = ClaimLinkResult()
    contacts = _collect_employee_contacts(db, idents, request_id)

    for c in contacts:
        cid = (c.get("id") or "").strip()
        if not cid:
            continue
        lu = (c.get("linked_auth_user_id") or "").strip()
        if lu and lu != user_id:
            result.skipped_contacts_linked_to_other_user += 1
            continue
        db.link_employee_contact_to_auth_user(cid, user_id, request_id=request_id)
        if cid not in result.linked_contact_ids:
            result.linked_contact_ids.append(cid)

        for asn in db.list_unassigned_assignments_for_employee_contact(cid, request_id=request_id):
            ident = (asn.get("employee_identifier") or "").strip() or next(iter(idents), "")
            _try_attach_assignment(
                db,
                user_id=user_id,
                assignment=asn,
                mark_identifier=ident,
                request_id=request_id,
                emit_side_effects=emit_side_effects,
                result=result,
            )

    legacy_list = db.list_unassigned_assignments_legacy_for_identifiers(
        list(idents), request_id=request_id
    )
    processed: Set[str] = set(result.newly_attached_assignment_ids)
    for asn in legacy_list:
        aid = (asn.get("id") or "").strip()
        if aid in processed:
            continue
        ident = (asn.get("employee_identifier") or "").strip() or next(iter(idents), "")
        before = result.newly_attached_assignment_ids.copy()
        _try_attach_assignment(
            db,
            user_id=user_id,
            assignment=asn,
            mark_identifier=ident,
            request_id=request_id,
            emit_side_effects=emit_side_effects,
            result=result,
        )
        if result.newly_attached_assignment_ids != before:
            processed.add(aid)

    identity_event(
        "identity.reconcile.complete",
        request_id=request_id,
        auth_user_id=user_id,
        principal_fingerprint=principal_fingerprint(email, username),
        contacts_matched=len(contacts),
        linked_contacts=len(result.linked_contact_ids),
        new_attachments=len(result.newly_attached_assignment_ids),
        skipped_contact_other_user=result.skipped_contacts_linked_to_other_user,
        skipped_assignments_other_user=result.skipped_assignments_linked_to_other_user,
        skipped_revoked_invites=result.skipped_revoked_invites,
        skipped_already_linked_same_user=result.skipped_already_linked_same_user,
        attached_assignment_ids=list(result.newly_attached_assignment_ids),
    )

    return result


def reconcile_employee_signup_after_register(
    db: "Database",
    *,
    user_id: str,
    email: Optional[str],
    username: Optional[str] = None,
    role: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Backward-compatible wrapper for tests/scripts; prefer `reconcile_pending_assignment_claims` in new code."""
    res = reconcile_pending_assignment_claims(
        db,
        user_id=user_id,
        email=email,
        username=username,
        role=role,
        request_id=request_id,
        emit_side_effects=True,
    )
    d = res.to_api_dict()
    # Legacy keys expected by main.py PostSignupReconciliation
    return {
        "linkedContactIds": d["linkedContactIds"],
        "attachedAssignmentIds": d["attachedAssignmentIds"],
        "skippedContactsLinkedToOtherUser": d["skippedContactsLinkedToOtherUser"],
        "skippedAssignmentsLinkedToOtherUser": d.get("skippedAssignmentsLinkedToOtherUser", 0),
        "skippedRevokedInvites": d.get("skippedRevokedInvites", 0),
        "skippedAlreadyLinkedSameUser": d.get("skippedAlreadyLinkedSameUser", 0),
        "headline": d.get("headline"),
        "message": d["message"],
    }

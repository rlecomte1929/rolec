"""Counsel attestation — admin endpoints + tokenized public reviewer endpoints.

An admin asks an external legal firm to review one corridor's legal-compliance checklist
over a shareable link. The firm signs. The signature is durable, immutable proof.

THE TWO-KEY RULE, which is the whole security model of this file:

    The public token path can ONLY write to corridor_attestation_items and
    corridor_attestation_signatures. It never touches requirement_items.
    Flipping a requirement to attestation_status='attested' is a SEPARATE, authenticated,
    admin-only action (`POST /api/admin/attestations/{id}/promote`).

So an external reviewer — or anyone who steals their link — cannot change what ReloPass
serves. They can only record an opinion. A human admin turns that opinion into a served
claim, and only after checking that the signature still matches the checklist that was
signed. Nothing in this file machine-writes 'attested'; grep for it and you will find
exactly one assignment, inside the promote handler, behind `require_admin`.

THE PII BOUNDARY. The public handlers return `AttestationPublicViewDTO` and nothing else.
That DTO is a whitelist of corridor-legal fields — no case, employee, company, or contact
data, not even the reviewer's own email echoed back. `_public_view()` is the single place
that builds it. Widening it, or returning a raw dict from a public handler, breaks the
guarantee `test_attestation_pii_boundary` exists to hold.

ENUMERATION. Every public miss — unknown token, expired token, wrong-status request,
malformed token — returns the SAME 404 with the same body. A 403 would confirm "this token
exists but you may not use it", which is a free oracle for anyone walking the space.

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md 405 rule).
"""
# NOTE: deliberately NO `from __future__ import annotations` here.
# It would turn every annotation into a string, and the @limiter.limit decorator wraps
# these handlers so FastAPI resolves those strings against slowapi's module globals rather
# than this one — where `AttestationDecisionIn` does not exist. The result is a
# PydanticUndefinedAnnotation at import time, i.e. the whole app fails to boot. Keep the
# annotations as real objects.
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ...rate_limit import limiter
from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import (
    CorridorAttestationItem,
    CorridorAttestationRequest,
    CorridorAttestationSignature,
    RequirementItem,
)
from ..schemas import (
    AttestationAdminDTO,
    AttestationChecklistItemDTO,
    AttestationCreatedDTO,
    AttestationCaseCreateIn,
    AttestationCreateIn,
    AttestationDecisionIn,
    AttestationPromoteResultDTO,
    AttestationPublicViewDTO,
    AttestationSignatureDTO,
    AttestationSignIn,
)
# The canonical case-id boundary (AIQ-1704) and the real serving selection. Both live
# outside this module on purpose: ATT-3.2 must attest what the case is ACTUALLY SERVED,
# and re-deriving that here would create a second answer to "what does this case need",
# which is the bug class the requirements engine exists to end. `cases_read.py` is the
# in-tree precedent for an app/ router reaching `database.db` for the resolver.
from ...database import db as main_db
from ..services.requirements_builder import compute_case_requirements
from ..services.attestation_tokens import (
    DEFAULT_TOKEN_TTL_DAYS,
    content_hash,
    hash_token,
    is_well_formed,
    mint_token,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/admin/attestations", tags=["attestation-admin"])
public_router = APIRouter(prefix="/api/public/attestations", tags=["attestation-public"])

#: Pillars that are operational rather than legal. `requirement_items` has no legal/
#: operational flag — only `pillar` — so counsel scope is derived by excluding these.
#: An admin can always override by passing explicit `requirement_item_ids`.
OPERATIONAL_PILLARS = {"HOUSING", "TIMELINE"}

#: Statuses during which a reviewer may still act on the link.
OPEN_STATUSES = {"sent", "in_review", "changes_requested"}

DISCLAIMER_VERSION = "v1"
DISCLAIMER_TEXT = (
    "By signing, I confirm that I am a qualified legal professional acting in my "
    "professional capacity and have reviewed the legal-compliance requirements listed for "
    "this relocation corridor. I attest that, to the best of my professional knowledge, "
    "the requirements marked approved accurately reflect the applicable law as of the date "
    "of signing. This attestation concerns the general legal requirements of the corridor "
    "only and is not legal advice in respect of any individual relocating person or case. "
    "ReloPass may rely on and retain this attestation as evidence of professional review."
)

#: One body for every public miss. See ENUMERATION in the module docstring.
_NOT_FOUND = "Attestation link not found or no longer valid."


def _db() -> Session:
    return SessionLocal()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Treat a naive timestamp as UTC.

    SQLite hands back naive datetimes where Postgres returns tz-aware ones. Comparing the
    two raises TypeError, which would surface as a 500 on the expiry check — the one branch
    that must never fail open.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _first_citation_url(item: RequirementItem) -> Optional[str]:
    """Best-effort source URL from citations_json, which holds ids or objects by era."""
    try:
        cites = json.loads(item.citations_json or "[]")
    except (ValueError, TypeError):
        return None
    for c in cites:
        if isinstance(c, dict):
            url = c.get("url") or c.get("source_url")
            if url:
                return str(url)
        elif isinstance(c, str) and c.startswith("http"):
            return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Shared projection
# ─────────────────────────────────────────────────────────────────────────────
def _checklist_dto(row: CorridorAttestationItem, req_item: Optional[RequirementItem]) -> AttestationChecklistItemDTO:
    """Project one envelope row for display.

    Reads the CLAIM from the snapshot, never from the live catalog row: counsel must see
    what was sent, even if an admin edited the requirement afterwards. `validity` and
    `confidence` come from the live row because they are display metadata, not the claim.
    """
    return AttestationChecklistItemDTO(
        id=str(row.id),
        title=row.item_title,
        claim=row.claim_snapshot,
        source_url=row.source_url_snapshot,
        evidence=row.evidence_snapshot,
        pillar=getattr(req_item, "pillar", None),
        validity=getattr(req_item, "timing", None),
        confidence=getattr(req_item, "verification_status", None),
        decision=row.decision or "pending",
        reviewer_comment=row.reviewer_comment,
        proposed_amendment=row.proposed_amendment,
    )


def _load_items(db: Session, request_id: str) -> List[AttestationChecklistItemDTO]:
    rows = (
        db.query(CorridorAttestationItem)
        .filter(CorridorAttestationItem.request_id == request_id)
        .order_by(CorridorAttestationItem.item_title)
        .all()
    )
    if not rows:
        return []
    req_items = {
        r.id: r
        for r in db.query(RequirementItem)
        .filter(RequirementItem.id.in_([row.requirement_item_id for row in rows]))
        .all()
    }
    return [_checklist_dto(row, req_items.get(row.requirement_item_id)) for row in rows]


def _signature_dto(sig: Optional[CorridorAttestationSignature]) -> Optional[AttestationSignatureDTO]:
    if sig is None:
        return None
    return AttestationSignatureDTO(
        id=str(sig.id),
        signer_name=sig.signer_name,
        signer_org=sig.signer_org,
        signer_credential=sig.signer_credential,
        signature_method=sig.signature_method,
        signed_content_hash=sig.signed_content_hash,
        disclaimer_version=sig.disclaimer_version,
        signed_at=sig.signed_at,
        supersedes_signature_id=sig.supersedes_signature_id,
    )


def _latest_signature(db: Session, request_id: str) -> Optional[CorridorAttestationSignature]:
    return (
        db.query(CorridorAttestationSignature)
        .filter(CorridorAttestationSignature.request_id == request_id)
        .order_by(CorridorAttestationSignature.signed_at.desc())
        .first()
    )


def _admin_dto(db: Session, req: CorridorAttestationRequest, *, with_items: bool = True) -> AttestationAdminDTO:
    items = _load_items(db, req.id) if with_items else []
    return AttestationAdminDTO(
        id=str(req.id),
        country_code=req.country_code,
        purpose=req.purpose,
        scope=req.scope,
        title=req.title,
        status=req.status,
        requested_by=req.requested_by,
        reviewer_org=req.reviewer_org,
        reviewer_name=req.reviewer_name,
        reviewer_email=req.reviewer_email,
        reviewer_credential=req.reviewer_credential,
        content_snapshot_hash=req.content_snapshot_hash,
        disclaimer_version=req.disclaimer_version,
        token_expires_at=req.token_expires_at,
        sent_at=req.sent_at,
        completed_at=req.completed_at,
        created_at=req.created_at,
        item_count=len(items) if with_items else (
            db.query(CorridorAttestationItem).filter(CorridorAttestationItem.request_id == req.id).count()
        ),
        items=items,
        signature=_signature_dto(_latest_signature(db, req.id)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — authenticated, admin-only
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.post("", response_model=AttestationCreatedDTO, status_code=status.HTTP_201_CREATED)
def create_attestation(
    body: AttestationCreateIn,
    request: Request,
    user: Dict[str, Any] = Depends(require_admin),
) -> AttestationCreatedDTO:
    """Snapshot a corridor's legal checklist and mint a one-time reviewer link."""
    with _db() as db:
        # Which review_status values counsel is shown.
        #
        # Default: `approved` only — the served corpus, and what every request has asked
        # for to date. Asking counsel about a row no reader can reach would waste the
        # scarcest resource this feature spends.
        #
        # `advance_review_status=True`: also `pending`. The two go together deliberately.
        # A request whose promotion is allowed to advance review_status is exactly the one
        # whose job is to move unpublished rows INTO the served corpus, so it has to show
        # counsel the unpublished rows. Widening the snapshot without the flag would put
        # unreachable rows in front of a lawyer; setting the flag without widening would
        # leave nothing for it to advance.
        review_statuses = ("approved", "pending") if body.advance_review_status else ("approved",)
        q = db.query(RequirementItem).filter(
            RequirementItem.country_code == body.country_code,
            RequirementItem.purpose == body.purpose,
            RequirementItem.review_status.in_(review_statuses),
        )
        if body.requirement_item_ids:
            q = q.filter(RequirementItem.id.in_(body.requirement_item_ids))
        candidates = q.all()

        # Only filter by pillar when the admin did NOT name items explicitly — an explicit
        # list is a deliberate scope decision and must not be silently trimmed.
        if not body.requirement_item_ids:
            candidates = [c for c in candidates if (c.pillar or "").upper() not in OPERATIONAL_PILLARS]

        if not candidates:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No approved in-scope requirements for {body.country_code}/{body.purpose}. "
                    "Nothing to attest — check the corridor key and that items are approved."
                ),
            )

        snapshot_items = [
            {
                "requirement_item_id": c.id,
                "title": c.title,
                "claim": c.description,
                "source_url": _first_citation_url(c),
                "evidence": c.description,
            }
            for c in candidates
        ]
        snapshot_hash = content_hash(snapshot_items)

        raw_token, token_digest = mint_token()
        ttl = body.ttl_days or DEFAULT_TOKEN_TTL_DAYS
        req = CorridorAttestationRequest(
            id=str(uuid.uuid4()),
            country_code=body.country_code,
            purpose=body.purpose,
            scope="legal",
            title=body.title or f"{body.country_code} — legal compliance attestation",
            status="draft",
            requested_by=str(user.get("email") or user.get("id") or "admin"),
            reviewer_org=body.reviewer_org,
            reviewer_name=body.reviewer_name,
            reviewer_email=body.reviewer_email,
            reviewer_credential=body.reviewer_credential,
            link_token_hash=token_digest,
            token_expires_at=_now() + timedelta(days=ttl),
            content_snapshot_hash=snapshot_hash,
            content_snapshot_json=snapshot_items,
            disclaimer_version=DISCLAIMER_VERSION,
            # Recorded intent only. Nothing reads either field until ATT-2.4 — see the
            # TODO in _apply_promotion. An out-of-vocabulary promotion_policy is refused
            # by the database CHECK rather than stored.
            promotion_policy=body.promotion_policy,
            advance_review_status=body.advance_review_status,
        )
        db.add(req)
        db.flush()

        for snap, cand in zip(snapshot_items, candidates):
            db.add(CorridorAttestationItem(
                id=str(uuid.uuid4()),
                request_id=req.id,
                requirement_item_id=cand.id,
                item_title=snap["title"],
                claim_snapshot=snap["claim"],
                source_url_snapshot=snap["source_url"],
                evidence_snapshot=snap["evidence"],
                decision="pending",
            ))
        db.commit()
        db.refresh(req)

        base = str(request.base_url).rstrip("/")
        return AttestationCreatedDTO(
            request=_admin_dto(db, req),
            review_token=raw_token,
            review_url=f"{base}/attest/{raw_token}",
            token_expires_at=req.token_expires_at,
        )


@admin_router.post("/case", response_model=AttestationCreatedDTO, status_code=status.HTTP_201_CREATED)
def create_case_attestation(
    body: AttestationCaseCreateIn,
    request: Request,
    user: Dict[str, Any] = Depends(require_admin),
) -> AttestationCreatedDTO:
    """Snapshot ONE CASE's served requirements and mint a reviewer link.

    The corridor path (`POST ""`) asks "has counsel signed off on Ireland?". This asks
    "has counsel signed off on THIS person's move?" — which is the question a customer
    actually pays for.

    **The served set is not re-derived here.** `compute_case_requirements` is the same
    function that builds the employee's roadmap, so counsel is shown exactly the rows the
    case is served — no more, and never a second opinion about what this case needs. This
    module only decides which of those rows are in LEGAL scope and projects them into the
    envelope.

    **PII boundary.** A case carries employee and company data; none of it may reach
    counsel. The snapshot is built from the CATALOG rows (`requirement_items`) that the
    serving call selected — title, description, citation URL — exactly as the corridor path
    builds it, so the two envelopes are structurally identical and neither can carry case
    data. `case_id` is written to the request row only; it never enters
    `corridor_attestation_items`, the snapshot JSON, or `AttestationPublicViewDTO`.
    """
    ids = main_db.resolve_case_ids(body.case_id)
    if ids is None:
        # Fail closed. `resolve_case_ids` accepts all three id forms, so None means the id
        # maps to no assignment at all — a 404, never a silent empty attestation.
        raise HTTPException(status_code=404, detail="Case not found")
    canonical = ids.canonical_case_id

    # `corridor_attestation_requests.case_id` is `uuid` (migration 20261121000000) while
    # `wizard_cases.id` is `character varying`. Measured in production 2026-08-22: 7 of
    # 1,840 case ids are not uuid-shaped — six demo/seed rows plus a literal "undefined"
    # a frontend once persisted. Writing one of those straight into the uuid column raises
    # a psycopg2 DataError out of the endpoint: a 500 whose DETAIL renders the whole
    # failing row. Refuse at the boundary instead; the column type stays the authority.
    try:
        uuid.UUID(str(canonical))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Case '{canonical}' has a non-UUID id and cannot be attested. "
                "Case-scoped attestation requires a uuid case id."
            ),
        )

    try:
        served = compute_case_requirements(canonical)
    except ValueError:
        # The resolver found an assignment but no wizard_cases row backs it.
        raise HTTPException(status_code=404, detail="Case not found")

    if not served.covered:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No requirement catalog coverage for destination '{served.destCountry}'. "
                "There is nothing to attest — this is a catalog gap, not an empty case."
            ),
        )

    # Legal scope, same rule as the corridor path: operational pillars are not what counsel
    # is being asked about.
    served_ids = [
        r.id for r in served.requirements
        if (r.pillar or "").upper() not in OPERATIONAL_PILLARS
    ]
    if not served_ids:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Case {canonical} is served no in-scope legal requirements. "
                "Nothing to attest."
            ),
        )

    with _db() as db:
        # Re-read the catalog rows the serving call selected, and build the envelope from
        # THOSE — identical construction to create_attestation, so a case envelope and a
        # corridor envelope are byte-comparable and the whitelist is enforced once.
        candidates = (
            db.query(RequirementItem).filter(RequirementItem.id.in_(served_ids)).all()
        )
        if not candidates:
            raise HTTPException(
                status_code=422,
                detail=f"Case {canonical} resolved requirements that no longer exist in the catalog.",
            )

        snapshot_items = [
            {
                "requirement_item_id": c.id,
                "title": c.title,
                "claim": c.description,
                "source_url": _first_citation_url(c),
                "evidence": c.description,
            }
            for c in candidates
        ]
        snapshot_hash = content_hash(snapshot_items)

        raw_token, token_digest = mint_token()
        ttl = body.ttl_days or DEFAULT_TOKEN_TTL_DAYS
        # country_code/purpose come from the catalog rows the case resolved to, not from the
        # case record — the envelope describes the corridor being attested, and a case field
        # copied in here would be the first crack in the PII boundary.
        corridor_key = candidates[0].country_code or served.destCountry
        purpose_key = candidates[0].purpose or served.purpose

        req = CorridorAttestationRequest(
            id=str(uuid.uuid4()),
            country_code=corridor_key,
            purpose=purpose_key,
            scope="case",
            case_id=str(canonical),
            title=body.title or f"{corridor_key} — case legal compliance attestation",
            status="draft",
            requested_by=str(user.get("email") or user.get("id") or "admin"),
            reviewer_org=body.reviewer_org,
            reviewer_name=body.reviewer_name,
            reviewer_email=body.reviewer_email,
            reviewer_credential=body.reviewer_credential,
            link_token_hash=token_digest,
            token_expires_at=_now() + timedelta(days=ttl),
            content_snapshot_hash=snapshot_hash,
            content_snapshot_json=snapshot_items,
            disclaimer_version=DISCLAIMER_VERSION,
        )
        db.add(req)
        db.flush()

        for snap, cand in zip(snapshot_items, candidates):
            db.add(CorridorAttestationItem(
                id=str(uuid.uuid4()),
                request_id=req.id,
                requirement_item_id=cand.id,
                item_title=snap["title"],
                claim_snapshot=snap["claim"],
                source_url_snapshot=snap["source_url"],
                evidence_snapshot=snap["evidence"],
                decision="pending",
            ))
        db.commit()
        db.refresh(req)

        base = str(request.base_url).rstrip("/")
        return AttestationCreatedDTO(
            request=_admin_dto(db, req),
            review_token=raw_token,
            review_url=f"{base}/attest/{raw_token}",
            token_expires_at=req.token_expires_at,
        )


@admin_router.get("", response_model=List[AttestationAdminDTO])
def list_attestations(user: Dict[str, Any] = Depends(require_admin)) -> List[AttestationAdminDTO]:
    with _db() as db:
        rows = (
            db.query(CorridorAttestationRequest)
            .order_by(CorridorAttestationRequest.created_at.desc())
            .all()
        )
        return [_admin_dto(db, r, with_items=False) for r in rows]


@admin_router.get("/{request_id}", response_model=AttestationAdminDTO)
def get_attestation(request_id: str, user: Dict[str, Any] = Depends(require_admin)) -> AttestationAdminDTO:
    with _db() as db:
        req = db.get(CorridorAttestationRequest, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="Attestation request not found")
        return _admin_dto(db, req)


@admin_router.post("/{request_id}/send", response_model=AttestationAdminDTO)
def send_attestation(request_id: str, user: Dict[str, Any] = Depends(require_admin)) -> AttestationAdminDTO:
    """Open the link for review. Only a draft can be sent."""
    with _db() as db:
        req = db.get(CorridorAttestationRequest, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="Attestation request not found")
        if req.status != "draft":
            raise HTTPException(status_code=409, detail=f"Cannot send a request in status '{req.status}'")
        req.status = "sent"
        req.sent_at = _now()
        db.commit()
        db.refresh(req)
        return _admin_dto(db, req)


def _apply_promotion(
    db: Session,
    req: CorridorAttestationRequest,
    *,
    actor: str,
    advance_review_status: bool = False,
) -> AttestationPromoteResultDTO:
    """THE SECOND KEY — the only place in the codebase that writes attestation_status='attested'.

    Extracted from `promote_attestation` so that ATT-2.4 can reach the SAME gates from the
    signing path when `promotion_policy='auto_on_sign'`. The point of sharing the function
    rather than copying it is that the three gates below cannot then drift apart: a second
    implementation that forgot the hash check would publish a signature that no longer
    describes the content, which is precisely the lie this feature exists to prevent.

    Three gates, all of them load-bearing:
      * the request must be `signed` — an unsigned opinion promotes nothing;
      * the signature's `signed_content_hash` must still equal the request's
        `content_snapshot_hash` — otherwise the checklist moved after signing and the
        signature no longer describes what we would be publishing;
      * only items the reviewer actually marked `approved` are promoted. `amended` and
        `rejected` are reported back as skipped, never quietly upgraded.

    Never touches `verification_status` — that is the other, orthogonal axis.

    `req` is already loaded; the 404 for an unknown id stays with the caller, because a
    request that does not exist is a routing concern rather than a promotion one.

    **`actor` and `advance_review_status` are accepted but deliberately UNUSED here.** They
    are the seam ATT-2.4 needs, added now so that wiring them is a change to this function's
    body rather than to its signature and every call site. `attested_by` continues to come
    from the reviewer/firm, NOT from `actor`: who published an attestation is not who gave
    it, and overwriting the firm with the admin's email would misattribute counsel's opinion.
    """
    if req.status != "signed":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot promote a request in status '{req.status}' — it must be signed first.",
        )

    sig = _latest_signature(db, req.id)
    if sig is None:
        raise HTTPException(status_code=409, detail="Request is marked signed but carries no signature row.")
    if sig.signed_content_hash != req.content_snapshot_hash:
        raise HTTPException(
            status_code=409,
            detail=(
                "The checklist changed after it was signed — the signature no longer covers "
                "the current content. Issue a new attestation request."
            ),
        )

    rows = db.query(CorridorAttestationItem).filter(
        CorridorAttestationItem.request_id == req.id
    ).all()
    approved = [r for r in rows if (r.decision or "") == "approved"]
    skipped = [str(r.requirement_item_id) for r in rows if (r.decision or "") != "approved"]

    firm = req.reviewer_org or sig.signer_org or sig.signer_name
    stamped = _now()
    promoted: List[str] = []
    for row in approved:
        item = db.get(RequirementItem, row.requirement_item_id)
        if item is None:
            continue
        item.attestation_status = "attested"
        item.attested_at = stamped
        item.attested_by = firm
        item.latest_attestation_request_id = str(req.id)

        # [ATT-2.4] THE LINE THAT PUBLISHES. `requirements_builder` serves `approved`
        # rows only, so this is the moment a requirement becomes visible to a mover.
        # Gated three ways and none of them are decoration: the request must have opted
        # in at creation (`advance_review_status`), every gate above must have passed
        # (signed, hash still matching, this item marked `approved` by the reviewer), and
        # the caller decides — the admin endpoint passes False, exactly as before.
        #
        # `reviewed_by` is the ACTOR (who caused publication); `attested_by` stays the
        # FIRM (whose legal opinion it is). Those are different questions and collapsing
        # them would misattribute counsel's opinion — see the ATT-2.3 note.
        if advance_review_status and (item.review_status or "") != "approved":
            item.review_status = "approved"
            item.reviewed_by = actor
            item.reviewed_at = stamped

        promoted.append(str(item.id))

    # Assert the arithmetic before committing: a silent short-write here would report
    # more corridor coverage than we actually hold, which is the one lie this feature
    # exists to prevent.
    if len(promoted) != len(approved):
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                f"Refusing to commit a partial promote: {len(approved)} items approved but "
                f"{len(promoted)} resolved. No rows changed."
            ),
        )

    db.commit()
    return AttestationPromoteResultDTO(
        request_id=str(req.id),
        promoted_item_ids=promoted,
        promoted_count=len(promoted),
        attested_by=firm,
        skipped_not_approved=skipped,
    )


@admin_router.post("/{request_id}/promote", response_model=AttestationPromoteResultDTO)
def promote_attestation(request_id: str, user: Dict[str, Any] = Depends(require_admin)) -> AttestationPromoteResultDTO:
    """Admin-triggered promotion — the authenticated half of the two-key rule.

    All the gates live in `_apply_promotion`; this endpoint resolves the id, supplies the
    actor, and keeps `advance_review_status=False`, which is exactly what it did before the
    logic was extracted.
    """
    with _db() as db:
        req = db.get(CorridorAttestationRequest, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="Attestation request not found")
        return _apply_promotion(
            db,
            req,
            actor=str(user.get("email") or user.get("id") or "admin"),
            advance_review_status=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC — no auth, token-scoped, rate-limited
# ─────────────────────────────────────────────────────────────────────────────
def _resolve(db: Session, token: str, *, require_open: bool) -> CorridorAttestationRequest:
    """Token → request, or 404. Every failure mode returns the SAME 404.

    Shape-check first so junk costs no database round trip, then look up by hash. A draft
    (never sent) is deliberately treated as not-found too: the link is not live until an
    admin sends it.
    """
    if not is_well_formed(token):
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    req = (
        db.query(CorridorAttestationRequest)
        .filter(CorridorAttestationRequest.link_token_hash == hash_token(token))
        .first()
    )
    if req is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    expires = _aware(req.token_expires_at)
    if expires is not None and expires <= _now():
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    if req.status in {"draft", "revoked", "superseded"}:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    if require_open and req.status not in OPEN_STATUSES:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    return req


def _public_view(db: Session, req: CorridorAttestationRequest) -> AttestationPublicViewDTO:
    """The ONLY builder of the public payload. The PII boundary lives here."""
    sig = _latest_signature(db, req.id)
    return AttestationPublicViewDTO(
        corridor_label=req.country_code,
        purpose=req.purpose,
        scope=req.scope,
        status=req.status,
        title=req.title,
        disclaimer_version=req.disclaimer_version or DISCLAIMER_VERSION,
        disclaimer_text=DISCLAIMER_TEXT,
        content_hash=req.content_snapshot_hash,
        expires_at=req.token_expires_at,
        items=_load_items(db, req.id),
        signed_at=sig.signed_at if sig else None,
    )


@public_router.get("/{token}", response_model=AttestationPublicViewDTO)
@limiter.limit("60/hour;600/day")
def public_get_attestation(token: str, request: Request) -> AttestationPublicViewDTO:
    with _db() as db:
        req = _resolve(db, token, require_open=False)
        return _public_view(db, req)


@public_router.post("/{token}/items/{item_id}", response_model=AttestationPublicViewDTO)
@limiter.limit("240/hour;2000/day")
def public_decide_item(
    token: str, item_id: str, body: AttestationDecisionIn, request: Request
) -> AttestationPublicViewDTO:
    """Record one item decision. Writes ONLY to corridor_attestation_items."""
    with _db() as db:
        req = _resolve(db, token, require_open=True)

        row = (
            db.query(CorridorAttestationItem)
            .filter(
                CorridorAttestationItem.id == item_id,
                # Scope to THIS request, or a reviewer could decide another firm's items
                # by guessing an id — the token authorises one envelope, not the table.
                CorridorAttestationItem.request_id == req.id,
            )
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail=_NOT_FOUND)

        row.decision = body.decision
        row.reviewer_comment = body.reviewer_comment
        row.proposed_amendment = body.proposed_amendment
        row.decided_at = _now()

        siblings = db.query(CorridorAttestationItem).filter(
            CorridorAttestationItem.request_id == req.id
        ).all()
        pushback = any((s.decision or "") in {"amended", "rejected"} for s in siblings)
        req.status = "changes_requested" if pushback else "in_review"
        req.updated_at = _now()

        db.commit()
        db.refresh(req)
        return _public_view(db, req)


def _maybe_auto_promote(
    db: Session, req: CorridorAttestationRequest, body: AttestationSignIn
) -> None:
    """[ATT-2.4] Let a valid, credentialed signature publish — when the request asked for it.

    This is the only place a signature reaches `requirement_items`, and it exists so the
    two-key rule can be waived DELIBERATELY, at creation time, on the record — never by
    default and never by an admin forgetting to click promote.

    Four conditions, all required:
      * `promotion_policy == 'auto_on_sign'` — recorded when the request was created
        (ATT-2.2). The default is `'manual'`, so every existing request is unaffected.
      * the signer supplied a `signer_credential`. An attestation is worth what the
        signer's standing is worth; an anonymous typed name may be RECORDED, but it may
        not publish. The signature is still stored either way — refusing to auto-publish
        is not refusing the review.
      * every gate inside `_apply_promotion` passes. Reused, never reimplemented: a second
        copy that forgot the content-hash check would publish a signature that no longer
        describes the content, which is the exact lie this feature exists to prevent.
      * the reviewer marked the item `approved`. `amended`/`rejected` are skipped there.

    Failure is swallowed ON PURPOSE, and logged. The realistic failure is the
    partial-write guard (a catalog row deleted between snapshot and signature), which is
    an internal inconsistency the REVIEWER cannot act on — and they are already finished:
    their signature is committed. Raising at them would report failure for an act that
    succeeded, while leaving them unable to retry (status `signed` is not in
    OPEN_STATUSES). Swallowing leaves the request `signed` and un-attested — the manual
    path, recoverable by an admin — and can only ever publish LESS than intended, never
    more. Silent it is not: it logs at ERROR with the request id.
    """
    if (req.promotion_policy or "manual") != "auto_on_sign":
        return

    credential = (body.signer_credential or "").strip()
    if not credential:
        logger.warning(
            "attestation auto_on_sign: request %s signed without a credential — signature "
            "recorded, NOT auto-promoted; an admin must promote it deliberately.",
            req.id,
        )
        return

    try:
        result = _apply_promotion(
            db,
            req,
            actor=f"auto:{body.signer_name}",
            advance_review_status=bool(req.advance_review_status),
        )
    except HTTPException as exc:
        db.rollback()
        logger.error(
            "attestation auto_on_sign: promotion FAILED for request %s (%s: %s). The "
            "signature is committed and the request stays 'signed' but un-attested — "
            "promote it manually via POST /api/admin/attestations/%s/promote once the "
            "cause is resolved.",
            req.id, exc.status_code, exc.detail, req.id,
        )
        return
    except Exception:
        # Belt and braces for the ATT-2.2 lesson: a raw DBAPI error must not escape into
        # the reviewer's response, where its DETAIL would render the failing row.
        db.rollback()
        logger.exception(
            "attestation auto_on_sign: unexpected error promoting request %s. Signature "
            "committed; request left 'signed' and un-attested.", req.id,
        )
        return

    logger.info(
        "attestation auto_on_sign: request %s promoted %d item(s), advance_review_status=%s",
        req.id, result.promoted_count, bool(req.advance_review_status),
    )


@public_router.post("/{token}/sign", response_model=AttestationPublicViewDTO)
@limiter.limit("20/hour;100/day")
def public_sign(token: str, body: AttestationSignIn, request: Request) -> AttestationPublicViewDTO:
    """Sign the attestation. INSERTs one immutable signature row.

    Explicitly does NOT touch requirement_items — see the two-key rule at the top. A
    signature records what counsel concluded; publishing it is the admin's separate act.
    """
    with _db() as db:
        req = _resolve(db, token, require_open=True)

        if not body.agreed_to_disclaimer:
            raise HTTPException(status_code=422, detail="The disclaimer must be explicitly agreed to.")

        rows = db.query(CorridorAttestationItem).filter(
            CorridorAttestationItem.request_id == req.id
        ).all()
        undecided = [r.item_title for r in rows if (r.decision or "pending") == "pending"]
        if undecided:
            raise HTTPException(
                status_code=422,
                detail=f"Every item must be decided before signing. Still pending: {sorted(undecided)}",
            )

        # The checklist must not have moved under the reviewer. Compare what they were
        # shown against what we stored; a mismatch means they would be signing something
        # they never read.
        if body.content_hash != req.content_snapshot_hash:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The checklist changed since this link was opened. Reload the page and "
                    "review the current version before signing."
                ),
            )

        frozen = {
            "corridor": req.country_code,
            "purpose": req.purpose,
            "scope": req.scope,
            "content_snapshot": req.content_snapshot_json,
            "decisions": [
                {
                    "requirement_item_id": str(r.requirement_item_id),
                    "title": r.item_title,
                    "decision": r.decision,
                    "reviewer_comment": r.reviewer_comment,
                    "proposed_amendment": r.proposed_amendment,
                }
                for r in sorted(rows, key=lambda r: str(r.requirement_item_id))
            ],
        }

        db.add(CorridorAttestationSignature(
            id=str(uuid.uuid4()),
            request_id=req.id,
            signer_name=body.signer_name,
            signer_email=body.signer_email,
            signer_org=body.signer_org,
            signer_credential=body.signer_credential,
            signature_method=body.signature_method or "typed_name",
            signed_content_hash=req.content_snapshot_hash,
            signed_payload_json=frozen,
            disclaimer_version=req.disclaimer_version or DISCLAIMER_VERSION,
            disclaimer_text=DISCLAIMER_TEXT,
            signed_ip=(request.client.host if request.client else None),
            signed_user_agent=request.headers.get("user-agent"),
        ))
        req.status = "signed"
        req.completed_at = _now()
        req.updated_at = _now()

        # Commit the signature BEFORE attempting any promotion, deliberately.
        #
        # A signature is counsel's own act and the table is append-only ("no code path
        # updates or deletes a signature"). `_apply_promotion` calls db.rollback() on its
        # partial-write guard — inside one transaction that would destroy the signature
        # too, and the reviewer could not re-sign to recover it: status is now `signed`,
        # which is not in OPEN_STATUSES, so `_resolve(require_open=True)` 404s them. They
        # would be left with no signature, no path forward, and a lost legal review.
        #
        # Committing first means a failed promotion rolls back ONLY the promotion. The
        # request stays `signed` and un-attested, which is precisely the manual path — the
        # conservative state, recoverable by an admin calling /promote. Nothing is
        # over-published by a failure; that is the direction this has to fail in.
        db.commit()
        db.refresh(req)

        _maybe_auto_promote(db, req, body)

        db.refresh(req)
        return _public_view(db, req)

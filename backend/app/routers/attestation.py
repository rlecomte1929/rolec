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
    AttestationCreateIn,
    AttestationDecisionIn,
    AttestationPromoteResultDTO,
    AttestationPublicViewDTO,
    AttestationSignatureDTO,
    AttestationSignIn,
)
from ..services.attestation_tokens import (
    DEFAULT_TOKEN_TTL_DAYS,
    content_hash,
    hash_token,
    is_well_formed,
    mint_token,
)

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
        q = db.query(RequirementItem).filter(
            RequirementItem.country_code == body.country_code,
            RequirementItem.purpose == body.purpose,
            RequirementItem.review_status == "approved",
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
        # TODO [ATT-2.4]: when `advance_review_status` is True, advance the item's
        # review_status here (pending -> approved), stamping `actor` as the reviewer.
        # Left unwired on purpose: advancing review_status PUBLISHES a requirement to
        # movers (requirements_builder serves approved rows only), so it is a behaviour
        # change that belongs in its own reviewable PR, not in this refactor.
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
        db.commit()
        db.refresh(req)
        return _public_view(db, req)

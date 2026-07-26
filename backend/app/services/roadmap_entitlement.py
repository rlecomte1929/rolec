"""Server-side roadmap paywall — the ONE place access to a paid roadmap is decided.

Replaces the client-trusted localStorage unlock (`frontend/src/utils/paymentStatus.ts`,
"TEST PHASE ONLY") with a server check: hiding a button in React is not a paywall
(spec §10). This is the enforcement half; the frontend rewire is a separate step.

Behind the `RELOPASS_ROADMAP_PAYWALL_ENABLED` kill switch (default OFF). While off,
`assert_roadmap_access` is a pure no-op — wiring it into the roadmap endpoints changes
nothing until an operator deliberately flips the flag AFTER payments are live. This is
load-bearing: every case is `access_tier='free'` today and nothing flips it to paid yet,
so enforcing the gate without the flag would lock EVERY employee out of their own roadmap.

Entitlement lives on `relocation_cases.access_tier` (the canonical case). The roadmap URL
`case_id` resolves there directly for ~95% of assignments; otherwise via the assignment's
`canonical_case_id`.

Fail-open policy (AIQ-1699 refined this). A lookup can come back empty for two very
different reasons, and they must NOT be treated the same:

  * the entitlement store could not be consulted at all — a DB error, or the Phase-1
    payment migration not yet applied so the column is absent. That says nothing about
    the case, so access is GRANTED. A paywall must never lock a legitimate user out over
    an outage.
  * the store WAS consulted and no case matches this id. That is a resolved answer: the
    id is not entitled, so access is DENIED. Previously this also granted access, which
    handed the €800 roadmap out free to any id the resolver couldn't reach.

`EntitlementLookup.available` carries that distinction; `resolve_entitlement` (which
flattens both to None) is kept only for callers that don't gate on the result.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, NamedTuple, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..db import SessionLocal
from .pii_masker import safe_log_text

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}
# Tiers that unlock the roadmap. 'free' does not.
PAID_TIERS = frozenset({"roadmap", "essentials"})


def roadmap_paywall_enabled() -> bool:
    return os.getenv("RELOPASS_ROADMAP_PAYWALL_ENABLED", "false").strip().lower() in _TRUTHY


class EntitlementLookup(NamedTuple):
    """Outcome of one entitlement lookup.

    `available` is about the STORE, not the case: False means we could not consult it
    (DB error / un-migrated column), so the answer is unknown and callers must fail
    OPEN. True with `row is None` is a real answer — no case matches this id — and
    callers gating access may fail CLOSED on it.
    """

    row: Optional[Dict[str, Any]]
    available: bool


def lookup_entitlement(case_id: str) -> EntitlementLookup:
    """Resolve {'access_tier', 'payment_status'} for a roadmap URL case_id.

    Direct `relocation_cases.id` match first (the common case), then via a `case_assignments`
    row — matched on the assignment's OWN id, its canonical_case_id, OR its case_id — to the
    linked relocation_cases row. The assignment-id match is load-bearing: the employee roadmap
    URL (and the checkout success_url) key on `case_assignments.id`, so without it those cases
    are unresolvable and the paywall is bypassed for exactly the roadmap URL testers land on.
    Never report "no such case" for a case we can reach through any of these ids.
    """
    cid = (case_id or "").strip()
    if not cid:
        # An empty id is a resolved answer, not an outage: there is no such case.
        return EntitlementLookup(None, True)
    try:
        with SessionLocal() as db:
            row = db.execute(
                text(
                    "SELECT access_tier, payment_status FROM relocation_cases WHERE id::text = :cid\n"
                    "UNION ALL\n"
                    "SELECT rc.access_tier, rc.payment_status FROM case_assignments ca\n"
                    "  JOIN relocation_cases rc ON rc.id::text = ca.canonical_case_id::text\n"
                    " WHERE (ca.id::text = :cid OR ca.canonical_case_id::text = :cid OR ca.case_id::text = :cid)\n"
                    "LIMIT 1"
                ),
                {"cid": cid},
            ).mappings().first()
    except SQLAlchemyError:
        # e.g. the Phase-1 migration isn't applied yet → access_tier column absent.
        # The store is unreachable, so we know nothing about this case: fail open.
        logger.warning("roadmap_entitlement: tier lookup failed for case %s (fail-open)",
                       safe_log_text(cid))
        return EntitlementLookup(None, False)
    return EntitlementLookup(dict(row) if row else None, True)


def resolve_entitlement(case_id: str) -> Optional[Dict[str, Any]]:
    """The entitlement row, or None when there isn't one OR the store was unreachable.

    Kept for callers that only want the row. Anything gating ACCESS must use
    `lookup_entitlement` instead — flattening both cases to None is precisely the
    fail-open AIQ-1699 closed.
    """
    return lookup_entitlement(case_id).row


def unlocked_from_lookup(found: EntitlementLookup) -> bool:
    """The single roadmap-access decision, shared by the enforcement gate and the
    status endpoint so the two can never disagree about the same case."""
    if not roadmap_paywall_enabled():
        return True
    if not found.available:
        return True  # store unreachable — never lock a user out over an outage
    if found.row is None:
        return False  # resolved: no such case → not entitled
    return (found.row.get("access_tier") or "free") in PAID_TIERS


def is_roadmap_unlocked(case_id: str) -> bool:
    """True if the roadmap may be served: paywall off, store unreachable, or paid tier."""
    if not roadmap_paywall_enabled():
        return True  # short-circuit BEFORE any DB lookup — the flag-off path costs nothing
    return unlocked_from_lookup(lookup_entitlement(case_id))


def assert_roadmap_access(case_id: str) -> None:
    """Raise 402 when the paywall is on and this case has not paid. No-op otherwise.
    Call AFTER the visibility check, before serving any roadmap content."""
    if is_roadmap_unlocked(case_id):
        return
    raise HTTPException(
        status_code=402,
        detail={
            "error": "roadmap_locked",
            "message": "This roadmap requires purchase.",
            "access_tier": "free",
        },
    )

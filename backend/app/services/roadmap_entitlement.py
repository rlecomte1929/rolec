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
`canonical_case_id`. Resolution FAILS OPEN — if the tier can't be determined (unknown case,
or the Phase-1 payment migration not yet applied so the column is absent), access is
GRANTED, never denied. A paywall must never wrongly block a legitimate user; the worst case
pre-launch is a free view, not a lockout.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

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


def resolve_entitlement(case_id: str) -> Optional[Dict[str, Any]]:
    """Return {'access_tier', 'payment_status'} for a roadmap URL case_id, or None if it
    can't be resolved (unknown case, or the payment columns don't exist yet). None means
    "fail open" to every caller — never a denial.

    Direct `relocation_cases.id` match first (the common case), then via the assignment's
    canonical_case_id for the legacy tail where the URL id is a wizard/other case id.
    """
    cid = (case_id or "").strip()
    if not cid:
        return None
    try:
        with SessionLocal() as db:
            row = db.execute(
                text(
                    "SELECT access_tier, payment_status FROM relocation_cases WHERE id::text = :cid\n"
                    "UNION ALL\n"
                    "SELECT rc.access_tier, rc.payment_status FROM case_assignments ca\n"
                    "  JOIN relocation_cases rc ON rc.id::text = ca.canonical_case_id::text\n"
                    " WHERE (ca.canonical_case_id::text = :cid OR ca.case_id::text = :cid)\n"
                    "LIMIT 1"
                ),
                {"cid": cid},
            ).mappings().first()
    except SQLAlchemyError:
        # e.g. the Phase-1 migration isn't applied yet → access_tier column absent.
        # Fail open: do not block a roadmap on an infrastructure gap.
        logger.warning("roadmap_entitlement: tier lookup failed for case %s (fail-open)",
                       safe_log_text(cid))
        return None
    return dict(row) if row else None


def is_roadmap_unlocked(case_id: str) -> bool:
    """True if the roadmap may be served. Unlocked when the paywall is off, when the tier
    can't be resolved (fail-open), or when the case has a paid tier."""
    if not roadmap_paywall_enabled():
        return True
    ent = resolve_entitlement(case_id)
    if ent is None:
        return True  # fail-open
    return (ent.get("access_tier") or "free") in PAID_TIERS


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

"""Stripe fulfilment brain — the ONE place a payment changes entitlement.

Portable-webhook spec §3 ("one brain, two mouths"): all business logic lives here;
the transport (Path A FastAPI route, or the Path B Audos relay forwarding into the
same route) is the only thing that varies. Both paths verify the Stripe signature
themselves and then call this function with a VERIFIED event — never an unverified one.

The four load-bearing guarantees, all exercised by the spec §8 test plan:

  1. Idempotent. The very first thing we do is INSERT the event id into `stripe_events`
     with `ON CONFLICT DO NOTHING`, inside the same transaction as the tier flip. A
     Stripe retry, or the same event arriving via both Path A and Path B, hits the
     primary key and short-circuits to {"status": "duplicate"} — no second tier flip.
  2. Never 5xx on a recognised-but-unfulfillable event. Unknown event type, missing
     `metadata.case_id`, or an unknown case all return {"status": "ignored"} + a 200 at
     the transport. A 5xx would put Stripe into an infinite retry storm.
  3. Only `checkout.session.completed` is acted on; everything else is ignored.
  4. Nothing raw is logged — the event carries customer data, so identifiers go through
     `safe_log_text()` before they touch a log line.

This is the ONLY place `relocation_cases.access_tier` is written.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text

from .pii_masker import safe_log_text

logger = logging.getLogger(__name__)

# The event we fulfil. Stripe sends many others (payment_intent.*, charge.*, …); those
# are acknowledged with a 200 and ignored so Stripe stops retrying them.
_FULFILLED_EVENT = "checkout.session.completed"

# tier (from checkout metadata) → (access_tier, payment_status). Both columns are
# CHECK-constrained (migration 20260719000001); an unrecognised tier is ignored rather
# than written, so a forged/garbage metadata value can never violate the constraint.
_TIER_MAP: Dict[str, Dict[str, str]] = {
    "roadmap": {"access_tier": "roadmap", "payment_status": "roadmap_paid"},
    "essentials": {"access_tier": "essentials", "payment_status": "essentials_paid"},
}


def _ignored(db, reason: str, **extra: Any) -> Dict[str, Any]:
    """Roll back and return an ignored result. Ignored events must not persist a
    partial write, and must return 200 at the transport so Stripe stops retrying."""
    db.rollback()
    logger.info("stripe_fulfillment: ignored (%s) %s", reason,
                " ".join(f"{k}={safe_log_text(str(v))}" for k, v in extra.items()))
    return {"status": "ignored", "reason": reason, **extra}


def fulfil_stripe_event(db, event: Dict[str, Any]) -> Dict[str, Any]:
    """Idempotently apply a VERIFIED Stripe event. Never called with an unverified event.

    Returns {"status": "applied"|"duplicate"|"ignored", ...}. The caller maps every one
    of these to HTTP 200 — only an invalid *signature* (handled upstream) is a 4xx.
    """
    event_id = (event.get("id") or "").strip()
    event_type = (event.get("type") or "").strip()

    if not event_id:
        # No id → cannot idempotency-guard it. Ignore rather than risk a double-apply.
        return _ignored(db, "missing_event_id", type=event_type)

    # (1) Idempotency FIRST, in this transaction. A duplicate (retry, or dual-path
    # delivery) conflicts on the PK and we do nothing else. Concurrent duplicates block
    # on the row lock until this tx commits, then see the conflict — so exactly one flip.
    inserted = db.execute(
        text("INSERT INTO stripe_events (event_id, type) VALUES (:eid, :etype) "
             "ON CONFLICT (event_id) DO NOTHING"),
        {"eid": event_id, "etype": event_type or "unknown"},
    )
    if inserted.rowcount == 0:
        db.rollback()
        logger.info("stripe_fulfillment: duplicate event %s", safe_log_text(event_id))
        return {"status": "duplicate", "event_id": event_id}

    # (3) Only checkout.session.completed is fulfilled; anything else is recorded + ignored.
    if event_type != _FULFILLED_EVENT:
        db.execute(text("UPDATE stripe_events SET status='ignored' WHERE event_id=:eid"),
                   {"eid": event_id})
        db.commit()
        logger.info("stripe_fulfillment: ignored event type %s", safe_log_text(event_type))
        return {"status": "ignored", "reason": "unhandled_event_type", "type": event_type}

    session = ((event.get("data") or {}).get("object")) or {}
    metadata = session.get("metadata") or {}
    case_id = (metadata.get("case_id") or "").strip()
    tier = (metadata.get("tier") or "").strip()

    # (2) Missing case_id → structured log, 200, no raise (spec §3.3 / test #5).
    if not case_id:
        return _ignored(db, "missing_case_id", event_id=event_id, tier=tier)

    tier_row = _TIER_MAP.get(tier)
    if tier_row is None:
        return _ignored(db, "unknown_tier", event_id=event_id, case_id=case_id, tier=tier)

    # (4) Flip the tier. Compare id AS TEXT so a malformed metadata.case_id can never
    # raise a uuid-cast error (which would 500 → retry storm) — it simply matches no row.
    updated = db.execute(
        text("""
            UPDATE relocation_cases
               SET access_tier = :access_tier,
                   payment_status = :payment_status,
                   stripe_session_id = :session_id,
                   stripe_payment_intent_id = :payment_intent,
                   paid_at = now(),
                   paid_amount_cents = :amount_cents,
                   paid_currency = :currency
             WHERE id::text = :case_id
        """),
        {
            "access_tier": tier_row["access_tier"],
            "payment_status": tier_row["payment_status"],
            "session_id": session.get("id"),
            "payment_intent": session.get("payment_intent"),
            "amount_cents": session.get("amount_total"),
            "currency": (session.get("currency") or "eur"),
            "case_id": case_id,
        },
    )
    if updated.rowcount == 0:
        # Unknown case — nothing to unlock. Record it and ignore (200), don't retry-storm.
        return _ignored(db, "unknown_case", event_id=event_id, case_id=case_id, tier=tier)

    # Record the resolved case on the idempotency row (default status 'applied' stands).
    db.execute(text("UPDATE stripe_events SET case_id=:cid WHERE event_id=:eid"),
               {"cid": case_id, "eid": event_id})
    db.commit()
    logger.info("stripe_fulfillment: applied %s → tier=%s (case %s)",
                safe_log_text(event_id), tier_row["access_tier"], safe_log_text(case_id))
    return {"status": "applied", "case_id": case_id, "tier": tier_row["access_tier"]}

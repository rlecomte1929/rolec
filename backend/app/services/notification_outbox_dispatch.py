"""[AIQ-1610] notification_outbox consumer.

The ``notification_outbox`` table (supabase/migrations/20260226150000_notification_outbox.sql)
is an email delivery queue: writers enqueue ``status='pending'`` rows (milestone reminders, and
``create_notification_with_preferences`` when the recipient wants email — e.g. a policy-exception
HR notification), but nothing ever sent them, so rows accumulated and no mail went out.

This is the missing consumer. It polls pending rows, delivers each via the shared Resend path
(``_resend_send`` — same provider/env as every other email in the app), and marks the row
terminal (``sent`` / ``failed``). It mirrors ``weekly_mobility_status`` and is driven by
``POST /api/crons/dispatch-outbox`` on a short schedule (.github/workflows/outbox-dispatch.yml).

Delivery uses the row's denormalised ``to_email``, so it is unaffected by the uuid-vs-legacy-text
``user_id`` mismatch that breaks the in-app ``/api/notifications`` read path (#1543).

Best-effort by construction: a single bad row never aborts the batch, and the function never raises.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import text

from ...database import db

log = logging.getLogger(__name__)

_DELIVERED = ("sent", "no_key")  # _resend_send outcomes that count as delivered


def _payload_dict(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def run_outbox_dispatch_cron(limit: int = 100) -> Dict[str, Any]:
    """Send pending ``notification_outbox`` rows via Resend and mark them terminal.

    Returns ``{pending, sent, logged, failed}``. Never raises — a delivery or DB error on one
    row is recorded on that row (``status='failed'``, ``last_error``) and the batch continues.
    """
    try:
        with db.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT id, to_email, type, payload FROM notification_outbox "
                        "WHERE status = 'pending' ORDER BY created_at LIMIT :limit"
                    ),
                    {"limit": limit},
                )
                .mappings()
                .all()
            )
    except Exception as exc:  # noqa: BLE001 — queue read must never break the caller/cron
        log.warning("outbox dispatch: could not read pending rows: %s", exc)
        return {"pending": 0, "sent": 0, "logged": 0, "failed": 0}

    # Shared Resend delivery path — same provider/env as every other email.
    from .assignment_invite_email import _resend_send

    sent = logged = failed = 0
    for row in rows:
        outbox_id = row["id"]
        to_email = (row.get("to_email") or "").strip()
        payload = _payload_dict(row.get("payload"))
        subject = payload.get("title") or "ReloPass notification"
        plain = payload.get("body") or ""

        status = "failed"
        last_error = None
        res_status = None
        if not to_email:
            last_error = "no recipient email"
        else:
            try:
                res = _resend_send(
                    to_email=to_email,
                    subject=subject,
                    plain=plain,
                    context="notification outbox",
                )
                res_status = str(res.get("status") or "error")
                if res_status in _DELIVERED:
                    status = "sent"
                else:
                    last_error = res_status
            except Exception as exc:  # noqa: BLE001 — one bad send never aborts the batch
                last_error = str(exc)[:500]
                log.warning("outbox dispatch: send failed for row %s: %s", outbox_id, exc)

        try:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE notification_outbox "
                        "SET status = :st, "
                        "    sent_at = CASE WHEN :st = 'sent' THEN now() ELSE sent_at END, "
                        "    last_error = :err "
                        "WHERE id = :id"
                    ),
                    {"st": status, "err": last_error, "id": outbox_id},
                )
        except Exception as exc:  # noqa: BLE001 — status write failure must not abort the batch
            log.warning("outbox dispatch: could not update row %s: %s", outbox_id, exc)

        if status == "sent":
            # A 'no_key' result (Resend unconfigured) is logged-not-sent, but we still mark the
            # row terminal so an unconfigured env doesn't wedge the queue on retries.
            if res_status == "no_key":
                logged += 1
            else:
                sent += 1
        else:
            failed += 1

    summary = {"pending": len(rows), "sent": sent, "logged": logged, "failed": failed}
    log.info("outbox dispatch: %s", summary)
    return summary


# ── Instant-fire ─────────────────────────────────────────────────────────────────────
# [AIQ-1610 follow-up] The scheduled GitHub-Actions cron is a safety-net, but GitHub throttles
# a 15-min schedule to ~every 2 hours, so relying on it alone meant an over-cap → HR email could
# sit pending for up to ~2h. `dispatch_outbox_soon` delivers a just-enqueued row within seconds by
# running the same consumer off the request path, in a small bounded thread pool (same fire-and-
# forget idiom as auth._dispatch_supabase_sync). The cron still sweeps anything this misses.
_instant_fire_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="outbox-instant-fire"
)


def _safe_dispatch(limit: int) -> None:
    try:
        run_outbox_dispatch_cron(limit=limit)
    except Exception:  # noqa: BLE001 — instant-fire is best-effort; never surface
        log.warning("outbox instant-fire dispatch failed (suppressed)", exc_info=True)


def dispatch_outbox_soon(limit: int = 25) -> None:
    """Best-effort INSTANT-FIRE of the outbox, off the caller's request path.

    Submits ``run_outbox_dispatch_cron`` to a small bounded pool so an enqueue-triggering request
    (e.g. an over-cap exception submit) returns immediately while the email goes out in seconds
    rather than on the throttled cron tick. Never raises; if the pool is saturated or shutting
    down the row simply waits for the scheduled cron (the safety-net). A modest ``limit`` keeps the
    inline burst bounded — any backlog is left to the cron.

    Note (accepted, best-effort): instant-fire and the cron can briefly overlap and, in a rare
    race, double-send one email. HR notifications are best-effort and a duplicate is harmless, so
    the queue is intentionally not hardened with row-level claiming here.
    """
    try:
        _instant_fire_executor.submit(_safe_dispatch, limit)
    except RuntimeError as exc:  # pool shutting down — fall back to the cron
        log.warning("outbox instant-fire not scheduled (%s); leaving for the cron", exc)

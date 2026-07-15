"""[AIQ-1526] Safety-net sweep: (re)notify HR about roadmaps stuck pending review.

The instant-fire notification (`_async_seed_and_generate_roadmap` -> `notify_hr_roadmap_pending`)
covers the normal path. But it fires *after* AI roadmap generation, and if that step **hangs**
(a raise is caught and the notify still fires — a hang is not), the notify line is never
reached: the plan is held, the employee is blocked, and HR was never told, with no retry.

This hourly sweep is that retry. It finds roadmaps that are held, never successfully notified,
and REAL, and runs the same idempotent `notify_hr_roadmap_pending` over them. A case already
notified is a no-op inside that function, so re-running the sweep never re-mails anyone.

"REAL" is load-bearing. E2E smoke tests create a case, submit it (writing a
`roadmap_review_status` row via the notify path), then purge the case — but there is no FK, so
the review row lingers as an orphan. A real pending roadmap always has milestones (the review
row is written only when `_ensure_default_milestones_for_case` just seeded > 0); an orphan has
none. So `EXISTS(milestones)` cleanly separates the two, and the sweep never wastes a send —
or worse, marks a ghost case `unreachable` — on E2E debris.

Never raises: a cron must stay green. One bad case is counted, not fatal to the rest.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)


def _main_db():
    from ....database import db  # type: ignore[import]

    return db


def _engine():
    return _main_db().engine


def _t(name: str) -> str:
    """Schema-qualified on Postgres, bare on SQLite (matches the other cron services)."""
    try:
        dialect = _engine().dialect.name
    except Exception:  # noqa: BLE001
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


def _pending_unnotified_case_ids(limit: int) -> List[str]:
    """Held + never-successfully-notified + REAL (has a roadmap). Oldest first.

    `notified_at IS NULL` is the retry signal: it's set only on a delivered send
    (sent/no_key), so a failed/errored/unreachable attempt is still picked up next hour.
    Fail-soft: any query error yields an empty list so the cron stays green.
    """
    q = f"""
        SELECT r.case_id
        FROM {_t('roadmap_review_status')} r
        WHERE r.released_to_user IS FALSE
          AND r.notified_at IS NULL
          AND EXISTS (
                SELECT 1 FROM {_t('case_milestones')} m
                WHERE m.case_id = r.case_id
              )
        ORDER BY r.updated_at ASC
        LIMIT :limit
    """
    try:
        with _engine().connect() as conn:
            rows = conn.execute(_sql_text(q), {"limit": limit}).mappings().all()
        return [str(row["case_id"]) for row in rows]
    except Exception as exc:  # noqa: BLE001
        log.error("roadmap review sweep: query failed: %s", exc)
        return []


def run_roadmap_review_notify_sweep(*, dry_run: bool = False, limit: int = 200) -> Dict[str, Any]:
    """(Re)notify HR for every roadmap stuck pending review with no delivered notification.

    Idempotent by construction: `notify_hr_roadmap_pending` is a no-op for an already-notified
    case, so this is safe to run as often as you like. Returns per-status tallies.
    """
    case_ids = _pending_unnotified_case_ids(limit)
    tally: Dict[str, int] = {}

    if case_ids:
        from .roadmap_review_notification import notify_hr_roadmap_pending

        for case_id in case_ids:
            try:
                outcome = notify_hr_roadmap_pending(case_id, dry_run=dry_run)
                status = str(outcome.get("status") or "error")
            except Exception as exc:  # noqa: BLE001 — one bad case must not stop the sweep
                log.error("roadmap review sweep: notify failed for %s: %s", case_id, exc)
                status = "error"
            tally[status] = tally.get(status, 0) + 1

    result = {
        "swept": len(case_ids),
        "sent": tally.get("sent", 0),
        "unreachable": tally.get("unreachable", 0),
        "failed": tally.get("failed", 0) + tally.get("error", 0),
        "already_notified": tally.get("already_notified", 0),
        "dry_run": dry_run,
    }
    log.info("roadmap review sweep: %s", result)
    return result

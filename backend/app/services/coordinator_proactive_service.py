"""AIQ-1414 Phase 3b — proactive Mobility Coordinator scan.

For each ACTIVE coordinator session, when new notify-worthy ``case_events`` have landed
since the session's ``last_event_cursor``, run ONE proactive coordinator turn. Delivery is
**in-session**: the update lands in ``recent_turns`` and shows in the Phase-4 chat panel on
next open (no new channel). The cursor is then advanced so the same events aren't
re-notified. Sessions whose case emitted a terminal event are ``close``d (this is the
session-close-on-completion lifecycle). Breaker-aware: a relocation already over its
monthly cap is skipped (the design's "pause proactive updates"). First scan of a session
(null cursor) initialises the cursor without notifying, so a backlog never floods.

Read-only on case data; each session is best-effort so one failure never aborts the scan.
Invoked by ``POST /api/crons/coordinator-proactive-scan`` (secret-gated), driven by a gated
GitHub Actions cron. Inert while ``RELOPASS_AI_COORDINATOR_ENABLED`` is OFF.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from . import coordinator_agent
from . import coordinator_session_store as store
from .coordinator_context_builder import coordinator_enabled

log = logging.getLogger(__name__)

# Event types that warrant a proactive heads-up (kept tight to stay inside the
# ~50-interaction/relocation cost budget). Free-form ``event_type`` today, so this is a
# forward-looking whitelist — the scan is a no-op until such events are emitted.
_NOTIFY_EVENT_TYPES = {
    "status_change",
    "completed",
    "milestone.completed",
    "milestone_completed",
    "requirement.status_changed",
    "document.approved",
}
_TERMINAL_EVENT_TYPES = {
    "case.completed",
    "case.closed",
    "case.withdrawn",
    "withdrawn",
    "archived",
    "assignment.archived",
}


def _get_db():
    from ...database import db as main_db

    return main_db


def _list_active_sessions(mdb: Any, limit: int) -> List[Dict[str, Any]]:
    with mdb.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT case_id, employee_id, last_event_cursor FROM ai_coordinator_sessions "
                "WHERE status = 'active' ORDER BY last_active_at ASC NULLS FIRST LIMIT :n"
            ),
            {"n": int(limit)},
        ).mappings().all()
    return [dict(r) for r in rows]


def _newest_at(events: List[Dict[str, Any]]) -> Optional[str]:
    best: Optional[str] = None
    for e in events:
        at = str(e.get("created_at") or "")
        if at and (best is None or at > best):
            best = at
    return best


def _summarize_events(events: List[Dict[str, Any]]) -> str:
    """A short, human-readable trigger the coordinator answers as a proactive update. The
    coordinator re-masks; details are already anonymised by the event spine."""
    lines = []
    for e in events[:6]:
        et = str(e.get("event_type") or "update").replace("_", " ").replace(".", " ")
        detail = (e.get("payload") or {}).get("detail") if isinstance(e.get("payload"), dict) else None
        lines.append(f"- {et}" + (f": {detail}" if detail else ""))
    return "New activity on this relocation:\n" + "\n".join(lines)


def _over_cap(case_id: str) -> bool:
    """True when this relocation is already over its monthly cap (pause proactive)."""
    try:
        from .ai_unit_economics import relocation_feature_spend_usd

        cap = coordinator_agent._monthly_cap_usd()
        if cap <= 0:
            return False
        return relocation_feature_spend_usd(
            str(case_id), feature_key=coordinator_agent.FEATURE_KEY
        ) >= cap
    except Exception:  # noqa: BLE001 — never block the scan on the meter
        return False


def run_coordinator_proactive_scan(
    *, db: Any = None, respond: Any = None, session_limit: int = 200
) -> Dict[str, Any]:
    """Scan active coordinator sessions and deliver in-session proactive updates. Returns a
    run summary. Inert (and cheap) while the feature flag is OFF."""
    if not coordinator_enabled(db=db):
        return {"ok": True, "enabled": False, "scanned": 0}

    mdb = db or _get_db()
    do_respond = respond or coordinator_agent.respond
    s = {"scanned": 0, "notified": 0, "closed": 0, "skipped": 0, "errors": 0}

    for sess in _list_active_sessions(mdb, session_limit):
        s["scanned"] += 1
        cid = sess.get("case_id")
        try:
            events = mdb.list_case_events(cid) or []

            # Terminal → close the session (session-close-on-completion lifecycle).
            if any(str(e.get("event_type")) in _TERMINAL_EVENT_TYPES for e in events):
                with mdb.engine.begin() as conn:
                    store.close_session(conn, cid)
                s["closed"] += 1
                continue

            cursor = sess.get("last_event_cursor")
            if not cursor:
                # First scan: initialise the cursor, don't notify on the backlog.
                newest = _newest_at(events)
                if newest:
                    with mdb.engine.begin() as conn:
                        store.set_event_cursor(conn, cid, newest)
                s["skipped"] += 1
                continue

            fresh = [e for e in events if str(e.get("created_at") or "") > str(cursor)]
            notify = [e for e in fresh if str(e.get("event_type")) in _NOTIFY_EVENT_TYPES]
            if not notify:
                s["skipped"] += 1
                continue

            if _over_cap(cid):  # breaker: pause proactive when over the monthly cap
                s["skipped"] += 1
                continue

            do_respond(cid, _summarize_events(notify), employee_id=sess.get("employee_id"), db=mdb)
            newest = _newest_at(fresh) or cursor
            with mdb.engine.begin() as conn:
                store.set_event_cursor(conn, cid, newest)
            s["notified"] += 1
        except Exception as exc:  # noqa: BLE001 — one bad case never aborts the scan
            s["errors"] += 1
            log.warning("coordinator proactive: case %s failed: %s", cid, exc)

    return {"ok": True, "enabled": True, **s}

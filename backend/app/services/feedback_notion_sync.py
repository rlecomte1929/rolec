"""feedback_notion_sync.py — close the loop between the Notion AI Work Queue and the
ReloPass Feedback console.

When a feedback item is dispatched, `feedback_status.dispatch_ref` holds its Notion task
URL. The task is then executed/completed IN NOTION (marked Done by the agent/human lane),
but nothing wrote that back — so the console kept showing dispatched items as `new`/
`dispatched` long after the fix shipped. This poller reads each dispatched-but-not-terminal
item's Notion Status and advances `feedback_status.dispatch_status` (and closes the triage
`status` on completion), so a finished item reads green ("Done ✓") in the ProgressStrip.

- Read-only against Notion: one GET per candidate via `notion_work_queue.get_task_meta`.
- The only writes are UPDATEs to `feedback_status` (never touches the ML feedback tables).
- `dry_run=True` reports exactly what WOULD change without writing — used for the one-time
  backlog reconciliation preview and safe to call anytime.
- Idempotent + forward-only: a row already matching its Notion status is skipped; terminal
  ReloPass states (done/dismissed/wont_fix) are not re-polled.

Invoked on a schedule (`.github/workflows/feedback-notion-sync.yml`) and on demand via
`POST /api/crons/feedback-notion-sync`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from ..db import SessionLocal
from . import notion_work_queue as nwq
from .admin_audit import record_admin_event

log = logging.getLogger(__name__)

# Notion Status → (dispatch_status, triage status | None, timestamp column | None).
# Forward-only. Unmapped Notion statuses (Ready for AI, Needs Decomposition, Parked) leave
# the row untouched (it stays "dispatched" — still in the active queue).
_STATUS_MAP: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {
    "Done": ("done", "closed", "done_at"),
    "AI in Progress": ("in_progress", None, "in_progress_at"),
    "Human Review": ("in_review", None, None),
    "Validation": ("in_review", None, None),
    "Blocked": ("verify_failed", None, None),
    "Rejected": ("wont_fix", "closed", None),
    # In this workspace a task is Archived when its work has shipped under a canonical /
    # dedup sibling (the dispatch + autopilot flows archive duplicates), so archived ==
    # handled/shipped → done (green), not dismissed.
    "Archived": ("done", "closed", "done_at"),
}

_TERMINAL = ("done", "dismissed", "wont_fix")


def _candidates(session: Any) -> List[Dict[str, Any]]:
    """Dispatched feedback items (have a Notion URL) not yet in a terminal ReloPass state."""
    rows = session.execute(text(
        "SELECT stream, source_id, dispatch_ref, dispatch_status "
        "FROM feedback_status "
        "WHERE dispatch_ref IS NOT NULL AND dispatch_ref LIKE 'http%' "
        "  AND (dispatch_status IS NULL OR dispatch_status NOT IN ('done','dismissed','wont_fix'))"
    )).fetchall()
    return [{"stream": r[0], "source_id": r[1], "dispatch_ref": r[2], "dispatch_status": r[3]}
            for r in rows]


def sync_dispatched_statuses(*, dry_run: bool = False, session: Any = None) -> Dict[str, Any]:
    """Poll Notion for each dispatched feedback item and advance feedback_status to match.

    Best-effort per item — a single Notion/row failure is logged and skipped, never raised.
    Returns a summary with the per-item change list (the dry-run preview)."""
    own = session is None
    session = session or SessionLocal()
    changes: List[Dict[str, Any]] = []
    checked = 0
    errors = 0
    try:
        for c in _candidates(session):
            page_id = nwq.page_id_from_ref(c["dispatch_ref"])
            if not page_id:
                continue
            checked += 1
            try:
                meta = nwq.get_task_meta(page_id)
            except Exception as exc:  # noqa: BLE001 — one unreachable page shouldn't stop the sweep
                errors += 1
                log.warning("notion-sync: get_task_meta failed for %s: %s", page_id, exc)
                continue
            notion_status = meta.get("status")
            mapped = _STATUS_MAP.get(notion_status or "")
            if not mapped:
                continue
            new_dispatch, new_triage, ts_col = mapped
            if new_dispatch == c["dispatch_status"]:
                continue  # already in sync
            changes.append({
                "stream": c["stream"], "source_id": c["source_id"], "aiq_id": meta.get("aiq_id"),
                "notion_status": notion_status, "from": c["dispatch_status"], "to": new_dispatch,
            })
            if dry_run:
                continue
            now = datetime.utcnow().isoformat()
            sets = ["dispatch_status = :ds", "updated_at = :now"]
            params: Dict[str, Any] = {"ds": new_dispatch, "now": now,
                                      "s": c["stream"], "id": c["source_id"]}
            if new_triage:
                sets.append("status = :st")
                params["st"] = new_triage
            if ts_col:
                sets.append(f"{ts_col} = COALESCE({ts_col}, :now)")
            session.execute(text(
                f"UPDATE feedback_status SET {', '.join(sets)} "
                "WHERE stream = :s AND source_id = :id"), params)
            # Audit is best-effort. A SAVEPOINT isolates it so an audit failure rolls
            # back only the audit — never the status UPDATE above — and never poisons the
            # outer transaction for the next item in the sweep.
            try:
                with session.begin_nested():
                    record_admin_event(
                        session, actor_id="notion-sync", event="feedback_status_synced",
                        entity="feedback_status", entity_id=c["source_id"],
                        detail={"stream": c["stream"], "notion_status": notion_status,
                                "from": c["dispatch_status"], "to": new_dispatch, "aiq": meta.get("aiq_id")},
                    )
            except Exception as exc:  # noqa: BLE001 — audit is best-effort, never blocks the sync
                log.warning("notion-sync: audit write failed for %s: %s", c["source_id"], exc)
        if not dry_run and own:
            session.commit()
    finally:
        if own:
            session.close()
    return {"dry_run": dry_run, "checked": checked, "changed": len(changes),
            "errors": errors, "changes": changes}

"""Advance feedback_status when the autopilot's CI funnel events arrive.
Join: feedback_status.notion_task_id (dashless-lower 32hex) prefix == event entity_id (16hex)."""
from __future__ import annotations
import logging, re
from datetime import datetime
from typing import Optional
from sqlalchemy import text

log = logging.getLogger(__name__)

# event_type -> (target dispatch_status, optional timestamp column)
_STATE_FOR_EVENT = {
    "autopilot.fix_attempted": ("in_progress", "in_progress_at"),
    "autopilot.merged":        ("in_review", None),
    "autopilot.canary_passed": ("deployed", "deployed_at"),
    "autopilot.task_done":     ("done", "done_at"),
    "autopilot.canary_failed": ("verify_failed", None),
    "autopilot.reverted":      ("verify_failed", None),
}


def advance_status_for_event(session, event_type: str, entity_id: Optional[str]) -> bool:
    m = _STATE_FOR_EVENT.get(event_type)
    if not m or not entity_id:
        return False
    state, ts_col = m
    eid = re.sub(r"[^0-9a-f]", "", entity_id.lower())[:16]
    if len(eid) < 16:
        return False
    now = datetime.utcnow().isoformat()
    set_ts = f", {ts_col} = :now" if ts_col else ""
    try:
        res = session.execute(text(
            f"UPDATE feedback_status SET dispatch_status = :st{set_ts}, updated_at = :now "
            "WHERE substr(notion_task_id, 1, 16) = :eid"),
            {"st": state, "now": now, "eid": eid})
        session.commit()
        return (res.rowcount or 0) > 0
    except Exception as exc:  # noqa: BLE001 — best-effort, funnel event already emitted
        log.warning("feedback_status bridge failed for %s/%s: %s", event_type, eid, exc)
        return False

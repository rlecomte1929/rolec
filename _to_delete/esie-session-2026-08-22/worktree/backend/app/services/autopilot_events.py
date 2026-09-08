"""autopilot_events.py — the funnel event vocabulary for the Feedback Autopilot.

One place to define the stage `event_type`s so every phase emits them consistently into
`public.events` (via events_tracker, source='scheduler'). The autopilot metrics dashboard
(Phase 4) reads these back to build the funnel (ingested → deduped → dispatched → fixed →
merged → verified/reverted → done) and to attribute cost per stage.

Additive in Phase 0 — the constants + `emit()` helper exist so Phase 1+ never invents
ad-hoc event names. `emit()` is fire-and-forget (never raises).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .events_tracker import track

ENTITY_TYPE = "autopilot_task"
SOURCE = "scheduler"

# Funnel stages (chronological). Keep these stable — the dashboard groups on them.
FEEDBACK_INGESTED = "autopilot.feedback_ingested"
FEEDBACK_DEDUPED = "autopilot.feedback_deduped"
TASK_DISPATCHED = "autopilot.task_dispatched"
FIX_ATTEMPTED = "autopilot.fix_attempted"
FIX_PR_OPENED = "autopilot.fix_pr_opened"
CI_PASSED = "autopilot.ci_passed"
MERGED = "autopilot.merged"
CANARY_PASSED = "autopilot.canary_passed"
CANARY_FAILED = "autopilot.canary_failed"
REVERTED = "autopilot.reverted"
TASK_DONE = "autopilot.task_done"
ESCALATED_TO_HUMAN = "autopilot.escalated_to_human"
RUN_STARTED = "autopilot.run_started"
RUN_HALTED = "autopilot.run_halted"   # gate/budget/backpressure pause — carries the reason

ALL_EVENTS = (
    FEEDBACK_INGESTED, FEEDBACK_DEDUPED, TASK_DISPATCHED, FIX_ATTEMPTED, FIX_PR_OPENED,
    CI_PASSED, MERGED, CANARY_PASSED, CANARY_FAILED, REVERTED, TASK_DONE,
    ESCALATED_TO_HUMAN, RUN_STARTED, RUN_HALTED,
)


def emit(
    event_type: str,
    *,
    entity_id: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    company_id: Optional[str] = None,
) -> None:
    """Record one autopilot funnel event. Fire-and-forget; `entity_id` is the AIQ id
    (or feedback fingerprint pre-dispatch); `properties` carries {tier, complexity, layer,
    model, tokens, cost_usd, fingerprint, cluster_size, reason, …}."""
    track(
        event_type,
        entity_type=ENTITY_TYPE,
        entity_id=entity_id,
        company_id=company_id,
        source=SOURCE,
        properties=properties or {},
    )

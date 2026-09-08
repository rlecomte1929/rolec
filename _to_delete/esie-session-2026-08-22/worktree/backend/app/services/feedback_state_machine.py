"""Validated state machine for the feedback pipeline's `dispatch_status` lane
(Task 6). Used by the admin `PATCH /feedback/{stream}/{item_id}/state` endpoint
to reject illegal manual transitions before they hit `feedback_status`.
"""
from __future__ import annotations

from typing import Dict, Optional, Set

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "new": {"triaged", "dismissed", "wont_fix"},
    "triaged": {"spec_drafted", "dismissed", "wont_fix"},
    "spec_drafted": {"dispatched", "dismissed", "wont_fix"},
    "dispatched": {"in_progress", "verify_failed", "dismissed"},
    "in_progress": {"in_review", "verify_failed"},
    "in_review": {"deployed", "verify_failed"},
    "deployed": {"done", "verify_failed"},
    "verify_failed": {"in_progress", "dismissed", "wont_fix"},
    "done": set(),
    "dismissed": set(),
    "wont_fix": set(),
}

_TS_COL = {
    "triaged": "triaged_at",
    "spec_drafted": "spec_drafted_at",
    "dispatched": "dispatched_at",
    "in_progress": "in_progress_at",
    "deployed": "deployed_at",
    "done": "done_at",
}


def validate_transition(current: Optional[str], target: str) -> bool:
    """True if `current` (None/absent treated as 'new') may transition to `target`."""
    return target in ALLOWED_TRANSITIONS.get(current or "new", set())


def timestamp_column(target: str) -> Optional[str]:
    """The `feedback_status` timestamp column to stamp for this target state, if any."""
    return _TS_COL.get(target)

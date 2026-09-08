"""In-process event dispatch for policy-gap re-detection (C2-06-FOLLOWUP).

The codebase has no general pub/sub bus — events_tracker.py is a fire-and-forget
analytics writer, not a subscriber registry. This module provides the minimal
dispatch the gap detector needs: the four case-lifecycle events that should
trigger re-detection, a subscribe/emit API with per-handler error isolation,
and a test-mode log so tests can assert handlers fired (validation criterion 6).

detect_and_persist is registered here for all four events. The *producer* call
sites (document parser, contradiction resolver, family-member intake, policy
publisher) call emit()/notify_*() at their touchpoints. Those producers land
with their own features (document parsing, C1-08 contradictions, etc.); this
module is the consumer + registration side. Producers should call:

    from backend.app.services.policy_gap_events import (
        emit, EVENT_DOCUMENT_PARSED, EVENT_CONTRADICTION_RESOLVED,
        EVENT_FAMILY_MEMBER_ADDED, notify_policy_published,
    )
    emit(EVENT_DOCUMENT_PARSED, case_id)          # single-case events
    notify_policy_published(employer_id)          # employer-wide fan-out
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable, Dict, List, Tuple

log = logging.getLogger(__name__)

EVENT_DOCUMENT_PARSED = "case.document.parsed"
EVENT_CONTRADICTION_RESOLVED = "case.contradiction.resolved"
EVENT_FAMILY_MEMBER_ADDED = "case.family_member.added"
EVENT_POLICY_PUBLISHED = "case.policy.published"

# The four events that trigger gap re-detection for a case.
GAP_REDETECTION_EVENTS: Tuple[str, ...] = (
    EVENT_DOCUMENT_PARSED,
    EVENT_CONTRADICTION_RESOLVED,
    EVENT_FAMILY_MEMBER_ADDED,
    EVENT_POLICY_PUBLISHED,
)

Handler = Callable[[uuid.UUID], object]

_subscribers: Dict[str, List[Handler]] = {}
_lock = threading.Lock()

_event_log: List[Tuple[str, str]] = []
_event_log_enabled = False


def subscribe(event_type: str, handler: Handler) -> None:
    with _lock:
        _subscribers.setdefault(event_type, []).append(handler)


def emit(event_type: str, case_id: uuid.UUID) -> None:
    """Dispatch a single-case event to all subscribers. Errors are isolated."""
    if _event_log_enabled:
        _event_log.append((event_type, str(case_id)))
    with _lock:
        handlers = list(_subscribers.get(event_type, ()))
    for handler in handlers:
        try:
            handler(case_id)
        except Exception:
            log.exception(
                "policy_gap_events: handler failed event=%s case=%s",
                event_type,
                case_id,
            )


def notify_policy_published(employer_id: uuid.UUID) -> int:
    """Fan a policy.published event out to every case under the employer.

    Returns the number of cases notified. Called by the policy publisher after
    a new policy version goes effective (new clauses → rerun every case).
    """
    from ..db import engine
    from .policy_gap_detector_adapter import case_ids_for_employer

    with engine.connect() as conn:
        case_ids = case_ids_for_employer(employer_id, conn)
    for cid in case_ids:
        emit(EVENT_POLICY_PUBLISHED, uuid.UUID(cid))
    return len(case_ids)


# ── Test helpers ──────────────────────────────────────────────────────────────


def enable_event_log() -> None:
    global _event_log_enabled
    _event_log_enabled = True
    _event_log.clear()


def drain_event_log() -> List[Tuple[str, str]]:
    out = list(_event_log)
    _event_log.clear()
    return out


def reset_subscribers() -> None:
    with _lock:
        _subscribers.clear()
    register_default_handlers()


# ── Registration ──────────────────────────────────────────────────────────────


def _redetect_handler(case_id: uuid.UUID) -> object:
    from .policy_gap_detector_adapter import detect_and_persist

    return detect_and_persist(case_id)


def register_default_handlers() -> None:
    """Subscribe detect_and_persist to the four re-detection events."""
    for event_type in GAP_REDETECTION_EVENTS:
        subscribe(event_type, _redetect_handler)


register_default_handlers()

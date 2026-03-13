"""
Observability Analytics Service — emit structured events for workflow, recommendations, and RFQ.
Events are logged and optionally persisted to analytics_events table.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# Canonical event names for observability
EVENT_CASE_CREATED = "case_created"
EVENT_SERVICES_SELECTED = "services_selected"
EVENT_SERVICES_ANSWERS_SAVED = "services_answers_saved"
EVENT_RECOMMENDATIONS_GENERATED = "recommendations_generated"
EVENT_SUPPLIER_VIEWED = "supplier_viewed"
EVENT_SUPPLIER_SELECTED = "supplier_selected"
EVENT_RFQ_CREATED = "rfq_created"
EVENT_QUOTE_RECEIVED = "quote_received"
EVENT_QUOTE_COMPARED = "quote_compared"
EVENT_QUOTE_ACCEPTED = "quote_accepted"


def emit_event(
    event_name: str,
    *,
    request_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    case_id: Optional[str] = None,
    canonical_case_id: Optional[str] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    duration_ms: Optional[float] = None,
    service_categories: Optional[list] = None,
    counts: Optional[Dict[str, int]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit a structured analytics event. Logs to backend and optionally persists to analytics_events.
    """
    payload: Dict[str, Any] = {
        "event": event_name,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    if request_id:
        payload["request_id"] = request_id
    if assignment_id:
        payload["assignment_id"] = assignment_id
    if case_id:
        payload["case_id"] = case_id
    if canonical_case_id:
        payload["canonical_case_id"] = canonical_case_id
    if user_id:
        payload["user_id"] = user_id
    if user_role:
        payload["user_role"] = user_role
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 2)
    if service_categories:
        payload["service_categories"] = service_categories
    if counts:
        payload["counts"] = counts
    if extra:
        payload["extra"] = extra

    log.info("analytics event=%s %s", event_name, json.dumps({k: v for k, v in payload.items() if k != "event"}))

    try:
        from ..database import db
        db.insert_analytics_event(event_name, payload)
    except Exception as e:
        log.debug("analytics_event persist failed (non-fatal): %s", e)

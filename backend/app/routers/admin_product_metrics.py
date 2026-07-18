"""Admin Product-metrics — the PostHog product events, mirrored to analytics_events.

Reads the same analytics_events table as admin_marketing_analytics.py, but for the
in-product funnel: case/policy/exception business events (mirrored server-side at
their handlers) plus the client UX funnel (wizard, estimate — mirrored via
POST /api/track). Admin-only. Surfaced by the "Product metrics" tab in the admin
Feedback section.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_admin
from ...database import db

router = APIRouter(prefix="/product-metrics", tags=["admin-product-metrics"])

# Every product event the admin dashboard aggregates, grouped for display.
WIZARD_EVENTS = ["wizard_step_completed", "wizard_completed"]
ESTIMATE_EVENTS = ["estimate_review_opened"]
CASE_EVENTS = ["case_created", "case_assigned"]
POLICY_EVENTS = ["policy_published"]
EXCEPTION_EVENTS = ["exception_request_submitted", "exception_request_decided"]

ALL_EVENTS = (
    WIZARD_EVENTS + ESTIMATE_EVENTS + CASE_EVENTS + POLICY_EVENTS + EXCEPTION_EVENTS
)


def _default_since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _rate(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100) if denominator else 0, 1)


@router.get("")
def product_metrics(
    days: int = Query(30, ge=1, le=90),
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    since = _default_since(days)
    counts = db.count_analytics_events_by_name(since=since)
    events = {name: counts.get(name, 0) for name in ALL_EVENTS}

    # Daily series: bucket raw events by date (no GROUP-BY-day helper exists, so
    # bucket in Python — same approach as the marketing funnel).
    daily_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {k: 0 for k in ALL_EVENTS})
    for name in ALL_EVENTS:
        for ev in db.list_analytics_events(event_name=name, since=since, limit=5000):
            day = str(ev.get("created_at", ""))[:10]
            if day:
                daily_map[day][name] += 1
    daily = [{"date": d, **daily_map[d]} for d in sorted(daily_map.keys())]

    return {
        "period_days": days,
        "since": since,
        "events": events,
        "rates": {
            # Of everyone who completed a wizard step, how many finished the wizard.
            "wizard_completion_pct": _rate(events["wizard_completed"], events["wizard_step_completed"]),
            # Of estimate reviews opened, how many led to an over-policy exception request.
            "exception_request_pct": _rate(events["exception_request_submitted"], events["estimate_review_opened"]),
            # Of exception requests submitted, how many HR has decided.
            "exception_decided_pct": _rate(events["exception_request_decided"], events["exception_request_submitted"]),
        },
        "daily": daily,
    }

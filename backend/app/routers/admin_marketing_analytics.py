"""Admin Marketing/Acquisition Analytics — pre-signup funnel.
Reads the same analytics_events table as admin_workflow_analytics.py.
Funnel: landing_page_view -> landing_cta_click -> lead_captured. Admin-only."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_admin
from ...database import db

router = APIRouter(prefix="/marketing-analytics", tags=["admin-marketing-analytics"])

FUNNEL_EVENTS = ["landing_page_view", "landing_cta_click", "lead_captured"]


def _default_since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@router.get("/funnel")
def marketing_funnel(
    days: int = Query(30, ge=1, le=90),
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    since = _default_since(days)
    counts = db.count_analytics_events_by_name(since=since)
    views = counts.get("landing_page_view", 0)
    clicks = counts.get("landing_cta_click", 0)
    captured = counts.get("lead_captured", 0)

    # Daily series for the trend chart: bucket raw events by date.
    daily_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {k: 0 for k in FUNNEL_EVENTS})
    for name in FUNNEL_EVENTS:
        for ev in db.list_analytics_events(event_name=name, since=since, limit=5000):
            day = str(ev.get("created_at", ""))[:10]
            if day:
                daily_map[day][name] += 1
    daily = [{"date": d, **daily_map[d]} for d in sorted(daily_map.keys())]

    return {
        "period_days": days,
        "since": since,
        "events": {"landing_page_view": views, "landing_cta_click": clicks, "lead_captured": captured},
        "rates": {
            "cta_rate_pct": round((clicks / views * 100) if views else 0, 1),
            "capture_rate_pct": round((captured / clicks * 100) if clicks else 0, 1),
        },
        "daily": daily,
    }

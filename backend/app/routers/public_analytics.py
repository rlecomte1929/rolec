"""Public, rate-limited marketing funnel event ingestion.
Writes an allow-listed marketing event into analytics_events so the admin
marketing dashboard can aggregate it. PostHog remains the product-analytics
sink; this path exists only to feed the server-side funnel."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ...rate_limit import limiter
from ..services.analytics_service import emit_event

router = APIRouter(tags=["public-analytics"])

# [AIQ-1783] Engagement events added for the paid-ad landing pages. Cold ad traffic
# converts too sparsely to read conversion alone, so scroll depth and dwell time are
# the only signals available early in a campaign.
ALLOWED_MARKETING_EVENTS = {
    "landing_page_view",
    "landing_cta_click",
    "landing_scroll_depth",
    "landing_time_on_page",
}


class TrackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: str = Field(..., max_length=100)
    properties: Optional[Dict[str, Any]] = None


@router.post("/api/public/track")
@limiter.limit("120/hour;1000/day")
def track_event(body: TrackIn, request: Request) -> Dict[str, Any]:
    if body.event not in ALLOWED_MARKETING_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event")
    props = body.properties or {}
    # Only scalar allow-listed keys — no free-text/PII from the public web.
    # [AIQ-1783] `depth` (scroll %) and `seconds` (dwell) are numeric-only engagement
    # measures; `page` distinguishes the two ad landing pages. Keep this an allow-list —
    # it exists so nothing free-text ever arrives here from an unauthenticated caller.
    safe = {
        k: props.get(k)
        for k in ("utm_source", "utm_campaign", "cta", "source", "page", "depth", "seconds")
    }
    emit_event(body.event, extra=safe)
    return {"ok": True}

"""Authenticated product-analytics event sink.

Mirrors a small allow-list of client-side UX events (the intake wizard funnel and
the estimate-review open) into analytics_events so the admin Product-metrics tab
can aggregate them server-side. PostHog remains the primary product-analytics
sink; this path exists only to feed the in-app admin dashboard.

Modelled on public_analytics.py (POST /api/public/track) but AUTHENTICATED and
scoped to logged-in product events. Strict event + key allow-lists keep any
free-text/PII out of the payload.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ...rate_limit import limiter
from ..auth_deps import get_current_user
from ..services.analytics_service import emit_event

router = APIRouter(tags=["product-analytics"])

# Client UX events the admin dashboard surfaces. Server-authoritative events
# (case_created, policy_published, exception_request_*) are mirrored directly at
# their handlers, not through this endpoint.
ALLOWED_PRODUCT_EVENTS = {
    "wizard_step_completed",
    "wizard_completed",
    "estimate_review_opened",
}

# PII-free scalar property keys we persist. Anything not listed is dropped — no
# names, emails, free text, or exact monetary values ever reach the sink.
ALLOWED_KEYS = (
    "case_id",
    "step_number",
    "step_name",
    "duration_seconds",
    "total_duration_seconds",
    "has_family",
    "household_size",
    "partner_needs_work_permit",
    "categories_count",
    "any_line_over_policy",
    "lines_over_policy_count",
    "lines_within_policy_count",
    "lines_no_cap_count",
    "lines_no_estimate_count",
    "hr_policy_caps_count",
)


class ProductTrackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: str = Field(..., max_length=100)
    properties: Optional[Dict[str, Any]] = None


@router.post("/api/track")
@limiter.limit("600/hour;5000/day")
def product_track(
    body: ProductTrackIn,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if body.event not in ALLOWED_PRODUCT_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event")
    props = body.properties or {}
    # Keep only allow-listed scalar keys with scalar values (defence in depth).
    safe = {
        k: props[k]
        for k in ALLOWED_KEYS
        if k in props and isinstance(props.get(k), (str, int, float, bool, type(None)))
    }
    case_id = safe.pop("case_id", None) if isinstance(safe.get("case_id"), str) else None
    emit_event(
        body.event,
        user_id=str(user.get("id")) if user.get("id") else None,
        case_id=case_id,
        extra=safe or None,
    )
    return {"ok": True}

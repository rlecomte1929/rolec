"""
Admin Workflow Analytics API — observability for user workflows, recommendations, supplier engagement, RFQ conversion.
Uses analytics_events table. Admin-only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...database import db


def _require_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    role = (user.get("role") or "").upper()
    if role == "ADMIN":
        return user
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() == "ADMIN":
        return user
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return user
    raise HTTPException(status_code=403, detail="Admin only")


router = APIRouter(prefix="/workflow", tags=["admin-workflow-analytics"])


def _default_since(days: int = 30) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@router.get("/overview")
def workflow_overview(
    days: int = Query(30, ge=1, le=90),
    user: Dict[str, Any] = Depends(_require_admin),
) -> Dict[str, Any]:
    """
    Aggregate workflow metrics from analytics_events.
    Returns: recommendation generation count, supplier selection rate, RFQ conversion, quote response rate.
    """
    since = _default_since(days)
    counts = db.count_analytics_events_by_name(since=since)

    rec_gen = counts.get("recommendations_generated", 0)
    supplier_viewed = counts.get("supplier_viewed", 0)
    supplier_selected = counts.get("supplier_selected", 0)
    rfq_created = counts.get("rfq_created", 0)
    quote_received = counts.get("quote_received", 0)
    quote_compared = counts.get("quote_compared", 0)
    quote_accepted = counts.get("quote_accepted", 0)
    case_created = counts.get("case_created", 0)
    assistant_questions = counts.get("assistant_question_asked", 0)
    assistant_supported = counts.get("assistant_question_supported", 0)
    assistant_unsupported = counts.get("assistant_question_unsupported", 0)
    assistant_refusals = counts.get("assistant_refusal_shown", 0)
    assistant_follow_ups = counts.get("assistant_follow_up_clicked", 0)
    services_selected = counts.get("services_selected", 0)
    services_answers_saved = counts.get("services_answers_saved", 0)

    supplier_selection_rate = (supplier_selected / supplier_viewed * 100) if supplier_viewed else 0
    rfq_conversion_rate = (rfq_created / supplier_selected * 100) if supplier_selected else 0
    quote_response_rate = (quote_received / rfq_created * 100) if rfq_created else 0

    return {
        "period_days": days,
        "since": since,
        "events": {
            "case_created": case_created,
            "services_selected": services_selected,
            "services_answers_saved": services_answers_saved,
            "recommendations_generated": rec_gen,
            "supplier_viewed": supplier_viewed,
            "supplier_selected": supplier_selected,
            "rfq_created": rfq_created,
            "quote_received": quote_received,
            "quote_compared": quote_compared,
            "quote_accepted": quote_accepted,
            "assistant_question_asked": assistant_questions,
            "assistant_question_supported": assistant_supported,
            "assistant_question_unsupported": assistant_unsupported,
            "assistant_refusal_shown": assistant_refusals,
            "assistant_follow_up_clicked": assistant_follow_ups,
        },
        "rates": {
            "supplier_selection_rate_pct": round(supplier_selection_rate, 1),
            "rfq_conversion_rate_pct": round(rfq_conversion_rate, 1),
            "quote_response_rate_pct": round(quote_response_rate, 1),
            "assistant_unsupported_rate_pct": round(
                (assistant_unsupported / assistant_questions * 100) if assistant_questions else 0,
                1,
            ),
        },
    }


@router.get("/events")
def list_workflow_events(
    event_name: Optional[str] = Query(None, description="Filter by event type"),
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(_require_admin),
) -> Dict[str, Any]:
    """List raw analytics events for debugging or drill-down."""
    since = _default_since(days)
    events = db.list_analytics_events(event_name=event_name, since=since, limit=limit)
    return {"events": events, "count": len(events)}

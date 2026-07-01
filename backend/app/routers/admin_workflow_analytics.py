"""
Admin Workflow Analytics API — observability for user workflows, recommendations, supplier engagement, RFQ conversion.
Uses analytics_events table. Admin-only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from ...database import db
from ..auth_deps import require_admin


router = APIRouter(prefix="/workflow", tags=["admin-workflow-analytics"])


def _default_since(days: int = 30) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _payload_extra(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = event.get("payload") or {}
    extra = payload.get("extra")
    return extra if isinstance(extra, dict) else {}


@router.get("/overview")
def workflow_overview(
    days: int = Query(30, ge=1, le=90),
    user: Dict[str, Any] = Depends(require_admin),
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
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """List raw analytics events for debugging or drill-down."""
    since = _default_since(days)
    events = db.list_analytics_events(event_name=event_name, since=since, limit=limit)
    return {"events": events, "count": len(events)}


@router.get("/policy-pipeline")
def policy_pipeline_overview(
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(5000, ge=100, le=10000),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Policy upload/classification throughput summary built from analytics_events."""
    since = _default_since(days)
    events = db.list_analytics_events(since=since, limit=limit)
    relevant_names = {
        "policy_upload_started",
        "policy_upload_completed",
        "policy_upload_failed",
        "policy_classify_started",
        "policy_classify_completed",
        "policy_classify_failed",
    }
    relevant_events = [event for event in events if event.get("event_name") in relevant_names]
    relevant_events.sort(key=lambda event: event.get("created_at") or "")

    counts = {name: 0 for name in sorted(relevant_names)}
    uploads: Dict[str, Dict[str, Any]] = {}
    failure_counts: Dict[str, int] = {}
    throughput_durations_ms: List[float] = []

    for event in relevant_events:
        event_name = str(event.get("event_name") or "")
        counts[event_name] = counts.get(event_name, 0) + 1
        payload = event.get("payload") or {}
        extra = _payload_extra(event)
        request_id = payload.get("request_id")
        document_id = extra.get("document_id")
        upload_key = str(document_id or request_id or event.get("id") or "")
        if not upload_key:
            continue
        record = uploads.setdefault(
            upload_key,
            {
                "request_id": request_id,
                "document_id": document_id,
                "upload_started_at": None,
                "classify_finished_at": None,
                "classification_status": None,
                "failure_reason": None,
            },
        )

        created_at = _parse_dt(event.get("created_at"))
        if event_name == "policy_upload_started":
            record["upload_started_at"] = created_at
        elif event_name == "policy_classify_completed":
            record["classify_finished_at"] = created_at
            record["classification_status"] = "completed"
        elif event_name == "policy_classify_failed":
            record["classify_finished_at"] = created_at
            record["classification_status"] = "failed"
            failure_reason = str(extra.get("extraction_error") or "unknown").strip() or "unknown"
            normalized_reason = failure_reason[:120]
            record["failure_reason"] = normalized_reason
            failure_counts[normalized_reason] = failure_counts.get(normalized_reason, 0) + 1
        elif event_name == "policy_upload_failed":
            failure_reason = str(extra.get("error_code") or extra.get("message") or "upload_failed").strip() or "upload_failed"
            normalized_reason = failure_reason[:120]
            record["classification_status"] = "upload_failed"
            record["failure_reason"] = normalized_reason
            failure_counts[normalized_reason] = failure_counts.get(normalized_reason, 0) + 1

    completed_count = 0
    failed_count = 0
    in_flight_count = 0
    for record in uploads.values():
        started_at = record.get("upload_started_at")
        finished_at = record.get("classify_finished_at")
        status = record.get("classification_status")
        if started_at and finished_at:
            throughput_durations_ms.append((finished_at - started_at).total_seconds() * 1000.0)
        if status == "completed":
            completed_count += 1
        elif status in ("failed", "upload_failed"):
            failed_count += 1
        else:
            in_flight_count += 1

    sorted_failures = sorted(failure_counts.items(), key=lambda item: item[1], reverse=True)
    sorted_durations = sorted(throughput_durations_ms)

    def _percentile(values: List[float], ratio: float) -> float:
        if not values:
            return 0.0
        idx = max(0, min(len(values) - 1, int(round((len(values) - 1) * ratio))))
        return values[idx]

    return {
        "period_days": days,
        "since": since,
        "scanned_events": len(relevant_events),
        "counts": counts,
        "uploads": {
            "tracked": len(uploads),
            "completed": completed_count,
            "failed": failed_count,
            "in_flight": in_flight_count,
        },
        "throughput_ms": {
            "samples": len(sorted_durations),
            "avg": round(sum(sorted_durations) / len(sorted_durations), 1) if sorted_durations else None,
            "p50": round(_percentile(sorted_durations, 0.50), 1) if sorted_durations else None,
            "p95": round(_percentile(sorted_durations, 0.95), 1) if sorted_durations else None,
            "max": round(max(sorted_durations), 1) if sorted_durations else None,
        },
        "top_failure_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted_failures[:10]
        ],
    }

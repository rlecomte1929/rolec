"""
Precedent insight service (AI-005).

Produces deterministic, SQL-aggregated precedent insights for exception
requests. Given an open exception (category + optional benefit_key), looks at
the history of resolved exceptions on the same shape and returns:

  - rationale: short human-readable string ("73% of similar requests approved
    in the last 24 months")
  - confidence: 0.0–1.0 based on sample size and recency
  - historical_approval_rate: float 0.0–1.0
  - similar_case_ids: up to 5 ids for traceability into the audit trail
  - generated_at: ISO timestamp of computation
  - source_version: stable identifier of the rule version (e.g. "precedent_v1")

Deterministic by design. No LLM. The same inputs against the same DB state
always produce the same output, which lets the AI-002 audit log use a stable
recommendation_id of the form `precedent_v1:<exception_id>` and replay later.

If there isn't enough history (fewer than 3 resolved similar cases), returns
a "no precedent yet" insight with confidence 0 so the frontend can still
surface a structured payload to the AIRecommendationCard.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

SOURCE_VERSION = "precedent_v1"

# Tunable knobs — kept inline; if these grow, move to a config module.
_MIN_SAMPLES_FOR_CONFIDENCE = 3
_FULL_CONFIDENCE_SAMPLE_SIZE = 12
_HISTORY_WINDOW_MONTHS = 24
_MAX_SIMILAR_IDS = 5


def compute_precedent_insight(
    conn,
    *,
    category: str,
    benefit_key: Optional[str],
    organization_id: str,
    exclude_request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a structured precedent insight dict for an exception request.

    Always returns a dict (never None). If there's no useful history, the
    rationale explains so and `confidence` is 0. Callers can still surface
    the payload as an AI recommendation and capture the human's response.

    Parameters
    ----------
    conn:
        An active SQLAlchemy connection. The service does not open or commit
        transactions — the caller controls the unit of work.
    category:
        The `policy_cap_requests.category` value of the open exception
        (e.g. "new_category", "cap_override").
    benefit_key:
        Optional benefit identifier (e.g. "international_school"). When
        provided, the precedent query is scoped to the same benefit; when
        not, it broadens to all requests of the same category.
    organization_id:
        Tenant scoping — only the company's own history is considered.
    exclude_request_id:
        The id of the request we're computing the insight FOR. Excluded from
        the sample so we never count a row as its own precedent.
    """
    where_clauses = [
        "organization_id = :org",
        "category = :category",
        "status IN ('approved', 'rejected')",
        "resolved_at IS NOT NULL",
        f"resolved_at > NOW() - INTERVAL '{_HISTORY_WINDOW_MONTHS} months'",
    ]
    params: Dict[str, Any] = {"org": organization_id, "category": category}

    if benefit_key:
        where_clauses.append("benefit_key = :benefit")
        params["benefit"] = benefit_key
    if exclude_request_id:
        where_clauses.append("id <> :exclude")
        params["exclude"] = exclude_request_id

    where_sql = " AND ".join(where_clauses)
    rows = (
        conn.execute(
            text(
                f"""
                SELECT id, status, resolved_at
                FROM policy_cap_requests
                WHERE {where_sql}
                ORDER BY resolved_at DESC
                """
            ),
            params,
        )
        .mappings()
        .all()
    )

    total = len(rows)
    approved = sum(1 for r in rows if r["status"] == "approved")
    approval_rate = (approved / total) if total else 0.0
    similar_ids = [str(r["id"]) for r in rows[:_MAX_SIMILAR_IDS]]

    if total < _MIN_SAMPLES_FOR_CONFIDENCE:
        rationale = (
            "No precedent yet — fewer than 3 similar exceptions have been "
            "decided in the last 24 months."
        )
        confidence = 0.0
    else:
        # Confidence ramps linearly from 0 (at the min-sample floor) to 1
        # (at the full-confidence sample size). Caps at 1.0.
        sample_factor = min(
            1.0,
            max(
                0.0,
                (total - _MIN_SAMPLES_FOR_CONFIDENCE)
                / max(1, _FULL_CONFIDENCE_SAMPLE_SIZE - _MIN_SAMPLES_FOR_CONFIDENCE),
            ),
        )
        confidence = round(sample_factor, 2)
        rate_pct = round(approval_rate * 100)
        benefit_phrase = f" for {benefit_key.replace('_', ' ')}" if benefit_key else ""
        rationale = (
            f"{rate_pct}% of similar {category.replace('_', ' ')} requests"
            f"{benefit_phrase} were approved in the last 24 months "
            f"({approved} of {total})."
        )

    return {
        "rationale": rationale,
        "confidence": confidence,
        "historical_approval_rate": round(approval_rate, 4),
        "sample_size": total,
        "similar_case_ids": similar_ids,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_version": SOURCE_VERSION,
    }


def insight_recommendation_id(exception_request_id: str) -> str:
    """Stable id used as `ai_decisions.recommendation_id` when the human
    accepts/overrides/rejects this insight. Lets the audit log dedupe by
    insight version + request, and lets replay reconstruct the source.
    """
    return f"{SOURCE_VERSION}:{exception_request_id}"

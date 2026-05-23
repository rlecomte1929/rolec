"""
outcome_recorder.py — write assignment outcome ratings to public.assignment_outcomes.

Usage (fire-and-forget; never raises):
    from backend.services.outcome_recorder import record_outcome

    record_outcome(
        assignment_id=provider_task_id,
        supplier_id=provider_id,
        rated_by=hr_user_id,          # raw — will be SHA-256 hashed internally
        quality_score=4.5,
        speed_score=4.0,
        communication_score=5.0,
        completed_on_time=True,
        budget_variance_pct=-3.2,     # negative = under budget
        hr_feedback="Great communication throughout.",
    )

All calls are best-effort: failures are logged at WARNING level and swallowed
so they never break the calling endpoint.

The supplier_stats materialised view is NOT refreshed here — that happens nightly
via the nightly-aggregation Edge Function (or on demand via refresh_supplier_stats()).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

log = logging.getLogger(__name__)

# ─── Privacy helper ───────────────────────────────────────────────────────────

def _hash_user_id(raw: Optional[str]) -> Optional[str]:
    """SHA-256 hash of a user ID so no raw PII is stored."""
    if not raw:
        return None
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── Lazy Supabase client ─────────────────────────────────────────────────────

_supabase_client = None


def _get_client():
    """Lazily initialise the Supabase service-role client."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    try:
        from .supabase_client import get_supabase_admin_client
        _supabase_client = get_supabase_admin_client()
    except Exception as exc:
        log.debug(
            "outcome_recorder: Supabase client unavailable (%s); outcomes will be dropped.", exc
        )
        _supabase_client = None
    return _supabase_client


# ─── Public API ───────────────────────────────────────────────────────────────

def record_outcome(
    *,
    assignment_id: str,
    supplier_id: str,
    rated_by: Optional[str] = None,
    quality_score: Optional[float] = None,
    speed_score: Optional[float] = None,
    communication_score: Optional[float] = None,
    completed_on_time: Optional[bool] = None,
    budget_variance_pct: Optional[float] = None,
    hr_feedback: Optional[str] = None,
    source_table: str = "provider_tasks",
) -> None:
    """
    Insert one row into public.assignment_outcomes.

    Silently drops if:
      - Supabase client is unavailable
      - An outcome already exists for this assignment_id (unique constraint)
      - Any unexpected error occurs (logged at WARNING)

    Args:
        assignment_id:        ID of the completed provider_task (or case_assignment)
        supplier_id:          ID from public.suppliers
        rated_by:             Raw user ID — hashed to SHA-256 before storage
        quality_score:        1.0–5.0 rating for output quality
        speed_score:          1.0–5.0 rating for delivery speed
        communication_score:  1.0–5.0 rating for communication
        completed_on_time:    Whether the task finished by the agreed deadline
        budget_variance_pct:  (actual - budget) / budget × 100 (negative = under budget)
        hr_feedback:          Free-text qualitative notes from HR
        source_table:         'provider_tasks' (default) or 'case_assignments'
    """
    client = _get_client()
    if client is None:
        return

    # Validate scores are in range before inserting (avoid DB CHECK failures)
    for name, value in [
        ("quality_score", quality_score),
        ("speed_score", speed_score),
        ("communication_score", communication_score),
    ]:
        if value is not None and not (1.0 <= value <= 5.0):
            log.warning(
                "outcome_recorder: %s=%.2f out of range [1,5]; dropping outcome for %s",
                name, value, assignment_id,
            )
            return

    payload = {
        "assignment_id": assignment_id,
        "supplier_id": supplier_id,
        "source_table": source_table,
        "rated_by": _hash_user_id(rated_by),
    }

    # Only include optional fields if provided (avoid nulling existing data on upsert)
    if quality_score is not None:
        payload["quality_score"] = round(float(quality_score), 2)
    if speed_score is not None:
        payload["speed_score"] = round(float(speed_score), 2)
    if communication_score is not None:
        payload["communication_score"] = round(float(communication_score), 2)
    if completed_on_time is not None:
        payload["completed_on_time"] = completed_on_time
    if budget_variance_pct is not None:
        payload["budget_variance_pct"] = round(float(budget_variance_pct), 2)
    if hr_feedback is not None:
        payload["hr_feedback"] = hr_feedback.strip() or None

    try:
        response = (
            client.table("assignment_outcomes")
            .insert(payload)
            .execute()
        )
        if hasattr(response, "error") and response.error:
            # Unique constraint violation is expected on retry — log at debug
            msg = str(response.error)
            level = logging.DEBUG if "unique" in msg.lower() else logging.WARNING
            log.log(level, "outcome_recorder: insert error for %s: %s", assignment_id, msg)
    except Exception as exc:
        log.warning(
            "outcome_recorder: unexpected error for assignment %s: %s",
            assignment_id, exc,
        )

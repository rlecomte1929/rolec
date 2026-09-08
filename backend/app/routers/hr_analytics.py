"""
GAP 3: Policy compliance matrix — GET /api/hr/policy-compliance-matrix

Cross-case aggregated view: all active assignments × 13 benefit types → compliance cell status.
Used by S5c (Policy vs. Reality heatmap).

Response shape:
  {
    cases: [{id, name, init, dest, tier, type, start, budget, spend, cells: {benefit_key: status}}],
    kpis: {compliance_pct, active_count, avg_overage, most_overrun_benefit}
  }

Cell statuses: green | amber | red | grey | blue
  green  = within policy, no issues
  amber  = within policy but <20% headroom
  red    = over policy cap
  grey   = benefit not applicable / not selected
  blue   = exception request pending
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db as main_db

router = APIRouter(prefix="/api/hr", tags=["hr-analytics"])


@router.get(
    "/committed-spend",
    summary="Committed spend across the caller's company, derived from validated RFQ quotes",
)
def get_company_committed_spend(user: dict = Depends(require_admin_or_hr)) -> dict:
    """[AIQ-2089] Committed spend derived from validated RFQ quotes (rfqs.validated_quote_id ⋈
    quotes), tenant-scoped to the caller's company via relocation_cases.company_id. Per-currency
    subtotals; a company with no validated quote yet returns has_spend=False (never a fabricated
    0). Never totals estimates and never sums across currencies.
    """
    from ..services.case_spend import committed_spend_for_company

    company_id = None
    try:
        company_id = get_org_id_for_hr_user(user)
    except Exception:  # noqa: BLE001 — fall back to the token claim, never 500 the report
        company_id = None
    company_id = company_id or user.get("company_id")
    return committed_spend_for_company(company_id or "")
logger = logging.getLogger(__name__)

# [AIQ-2087] The Policy-vs-Reality compliance matrix was REMOVED here, along with
# its /policy-compliance-matrix endpoint, its CSV/PDF export (backend/app/routers/
# hr_export.py) and its page (/hr/policy-vs-reality).
#
# It could not report anything true, and fixing it halfway would have made it worse.
# Two independent faults:
#
#   * _get_matrix_data filtered `status IN ('active','in_progress','onboarding',
#     'documents_pending')`. None are canonical — app/services/case_status.py permits
#     only created|assigned|awaiting_intake|submitted|approved|rejected|closed — so the
#     query returned zero rows by construction. It also scoped the company from a JWT
#     claim rather than _get_hr_company_id.
#
#   * `spend_by_benefit` was hardcoded `{}` ("# No spend data yet — real spend tracking
#     is V2"), and _compute_cells did `ratio = spend / cap` -> 0 -> "green". So had the
#     status filter been fixed alone, every covered benefit for every employee would
#     have rendered GREEN — a compliance grid asserting compliance it never measured.
#
# That is the AIQ-1527 failure exactly (see backend/tests/test_budget_summary_honest.py:
# "a green tick derived from nothing"). Empty was honest; all-green would not have been.
# Rebuild it on a real spend ledger, or not at all.

# ---------------------------------------------------------------------------
# P5-7: Policy Calibration Alerts
# ---------------------------------------------------------------------------
# Generated weekly by the gap-detection-weekly Edge Function.
# HR/Admin see undismissed alerts for their organisation; they can dismiss them
# individually via the PATCH endpoint.
# ---------------------------------------------------------------------------

class CalibrationAlertOut(BaseModel):
    id: str
    organization_id: str
    category: str
    tier_name: Optional[str]
    exception_count: int
    avg_excess_pct: float
    alert_message: str
    created_at: str


@router.get(
    "/calibration-alerts",
    response_model=List[CalibrationAlertOut],
    summary="List undismissed policy calibration alerts for the caller's organisation",
)
def list_calibration_alerts(
    user: dict = Depends(require_admin_or_hr),
):
    """
    Returns all non-dismissed policy_calibration_alerts rows for the
    caller's organisation, newest first.
    """
    company_id: Optional[str] = user.get("company_id")
    if not company_id:
        return []

    with main_db.engine.connect() as conn:
        rows = conn.execute(
            main_db.text(
                """
                SELECT id, organization_id, category, tier_name,
                       exception_count, avg_excess_pct, alert_message,
                       created_at
                FROM public.policy_calibration_alerts
                WHERE organization_id = :org_id
                  AND dismissed_at IS NULL
                ORDER BY created_at DESC
                """
            ),
            {"org_id": company_id},
        ).fetchall()

    return [
        CalibrationAlertOut(
            id=str(r["id"]),
            organization_id=str(r["organization_id"]),
            category=r["category"],
            tier_name=r["tier_name"],
            exception_count=r["exception_count"],
            avg_excess_pct=float(r["avg_excess_pct"]),
            alert_message=r["alert_message"],
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.patch(
    "/calibration-alerts/{alert_id}/dismiss",
    status_code=204,
    summary="Dismiss a policy calibration alert",
)
def dismiss_calibration_alert(
    alert_id: str,
    user: dict = Depends(require_admin_or_hr),
):
    """
    Sets dismissed_at = NOW() and dismissed_by = current user on the given
    alert row.  Returns 404 if the alert doesn't exist or belongs to a
    different organisation.
    """
    from fastapi import HTTPException
    import uuid

    company_id: Optional[str] = user.get("company_id")
    user_id: Optional[str] = user.get("id") or user.get("sub")

    if not company_id:
        raise HTTPException(status_code=403, detail="No company context")

    with main_db.engine.begin() as conn:
        result = conn.execute(
            main_db.text(
                """
                UPDATE public.policy_calibration_alerts
                SET    dismissed_at = NOW(),
                       dismissed_by = :user_id
                WHERE  id = :alert_id
                  AND  organization_id = :org_id
                  AND  dismissed_at IS NULL
                """
            ),
            {
                "alert_id": alert_id,
                "org_id": company_id,
                "user_id": user_id,
            },
        )

    if result.rowcount == 0:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Alert not found or already dismissed",
        )


# ── W2-5 answer provenance ────────────────────────────────────────────────
class GateImpact(BaseModel):
    """Estimated effect of the groundedness gate, from persisted traces only."""

    min_score: float
    n_answers: int
    n_would_refuse: int
    would_refuse_rate: float
    n_would_refuse_helpful: int


class AnswerProvenanceResponse(BaseModel):
    """Per-company Policy Assistant answer-provenance rollup over a recent window.

    grounded_rate is denominated on answered questions (grounding only runs on
    real answers, not refusals). refusal_rate is denominated on all questions.
    unverified_count is the number of answers where the grounding verifier failed
    open (could not produce a verdict).
    """

    total: int
    answers: int
    refusals: int
    grounded: int
    unverified_count: int
    refusal_rate: float
    grounded_rate: float
    window_days: int
    # P1 gate-impact canary (additive, read-only): what the groundedness gate
    # WOULD refuse at the default min_score if POLICY_RAG_GROUNDEDNESS_GATE were
    # flipped on. None when the rollup is unavailable. Does not change behavior.
    gate_impact: Optional[GateImpact] = None


@router.get(
    "/answer-provenance",
    response_model=AnswerProvenanceResponse,
    summary="Policy Assistant answer provenance (grounded% / refusal% / unverified)",
)
def get_answer_provenance(
    window_days: int = Query(30, ge=1, le=365),
    org_id: str = Depends(get_org_id_for_hr_user),
):
    """W2-5: surface answer trustworthiness for the caller's company.

    Reads the queryable provenance columns on policy_assistant_traces
    (answer_kind / grounding_verdict / verification_skipped) populated by the
    answer pipeline. Returns zeroed counts for a company with no traces in the
    window — never errors on empty data.
    """
    from datetime import datetime, timedelta

    if not org_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="No company context")

    since = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    rollup = main_db.get_answer_provenance_rollup(company_id=org_id, since=since)
    # P1 gate-impact canary (additive, read-only): estimate what the groundedness
    # gate would refuse at its default min_score. Never breaks the response.
    gate_impact = None
    try:
        gi = main_db.get_gate_impact_rollup(company_id=org_id, since=since)
        gate_impact = GateImpact(
            min_score=gi["min_score"],
            n_answers=gi["n_answers"],
            n_would_refuse=gi["n_would_refuse"],
            would_refuse_rate=gi["would_refuse_rate"],
            n_would_refuse_helpful=gi["n_would_refuse_helpful"],
        )
    except Exception:
        gate_impact = None
    return AnswerProvenanceResponse(
        total=rollup["total"],
        answers=rollup["answers"],
        refusals=rollup["refusals"],
        grounded=rollup["grounded"],
        unverified_count=rollup["unverified_count"],
        refusal_rate=rollup["refusal_rate"],
        grounded_rate=rollup["grounded_rate"],
        window_days=window_days,
        gate_impact=gate_impact,
    )

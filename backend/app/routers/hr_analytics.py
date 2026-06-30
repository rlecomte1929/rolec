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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db as main_db

router = APIRouter(prefix="/api/hr", tags=["hr-analytics"])
logger = logging.getLogger(__name__)

# The 13 benefit columns shown in the S5c heatmap
BENEFIT_COLUMNS = [
    "temporary_housing",
    "shipment",
    "immigration",
    "tax",
    "language",
    "spouse_support",
    "schooling",
    "settling_in",
    "home_leave",
    "transportation",
    "allowance",
    "mobility_premium",
    "pet_relocation",
]

BENEFIT_LABELS: Dict[str, str] = {
    "temporary_housing": "Temp housing",
    "shipment": "Int'l shipping",
    "immigration": "Immigration",
    "tax": "Tax equalisation",
    "language": "Language",
    "spouse_support": "Spouse career",
    "schooling": "Int'l school",
    "settling_in": "Settling-in",
    "home_leave": "Home leave",
    "transportation": "Transport",
    "allowance": "Allowance",
    "mobility_premium": "Mobility prem.",
    "pet_relocation": "Pet relocation",
}


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceCaseRow(BaseModel):
    id: str
    name: str
    init: str
    origin: Optional[str] = None
    dest: Optional[str] = None
    tier: Optional[str] = None
    assignment_type: Optional[str] = None
    start_date: Optional[str] = None
    budget_eur: Optional[int] = None
    spend_eur: Optional[int] = None
    cells: Dict[str, str]  # benefit_key → status colour


class ComplianceKpis(BaseModel):
    compliance_pct: int
    active_count: int
    avg_overage_eur: Optional[int] = None
    most_overrun_benefit: Optional[str] = None
    benefit_columns: List[str]
    benefit_labels: Dict[str, str]


class PolicyComplianceMatrixResponse(BaseModel):
    cases: List[ComplianceCaseRow]
    kpis: ComplianceKpis


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0].upper() for p in parts[:2])


def _compute_cells(
    assignment: Dict[str, Any],
    covered_benefits: set,
    exception_benefit_keys: set,
    spend_by_benefit: Dict[str, float],
    caps_by_benefit: Dict[str, float],
) -> Dict[str, str]:
    """Compute compliance cell status for each benefit column."""
    cells = {}
    for key in BENEFIT_COLUMNS:
        if key not in covered_benefits:
            cells[key] = "grey"
            continue
        if key in exception_benefit_keys:
            cells[key] = "blue"
            continue
        cap = caps_by_benefit.get(key)
        spend = spend_by_benefit.get(key, 0)
        if cap is None:
            cells[key] = "green"
            continue
        ratio = spend / cap if cap > 0 else 0
        if ratio > 1.0:
            cells[key] = "red"
        elif ratio > 0.8:
            cells[key] = "amber"
        else:
            cells[key] = "green"
    return cells


def _get_matrix_data(company_id: str, period_months: int) -> List[Dict[str, Any]]:
    """Fetch assignment + benefit data from Supabase for the compliance matrix."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()

        # Active assignments for this company
        result = (
            sb.table("case_assignments")
            .select("id, employee_name, employee_identifier, origin_country, destination_country, "
                    "assignment_type, start_date, status, company_id")
            .eq("company_id", company_id)
            .in_("status", ["active", "in_progress", "onboarding", "documents_pending"])
            .limit(200)
            .execute()
        )
        return result.data if result and result.data else []
    except Exception:
        logger.exception("Failed to fetch matrix data for company %s", company_id)
        return []


def _get_covered_benefits_for_company(company_id: str) -> Dict[str, Dict[str, Any]]:
    """Return {benefit_key: {cap, coverage_type}} for the company's active policy."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("policy_config_benefits")
            .select("benefit_key, coverage_type, cap_amount, cap_currency")
            .eq("company_id", company_id)
            .execute()
        )
        if result and result.data:
            return {
                row["benefit_key"]: row
                for row in result.data
                if row.get("coverage_type") not in ("excluded", "not_applicable")
            }
    except Exception:
        logger.debug("Could not fetch policy config benefits for company %s", company_id)
    return {}


def _get_exception_keys_for_assignment(assignment_id: str) -> set:
    """Return benefit keys with a pending exception request for this assignment."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("exception_requests")
            .select("benefit_key")
            .eq("assignment_id", assignment_id)
            .eq("status", "pending")
            .execute()
        )
        if result and result.data:
            return {row.get("benefit_key") for row in result.data if row.get("benefit_key")}
    except Exception:
        pass
    return set()


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/policy-compliance-matrix", response_model=PolicyComplianceMatrixResponse)
def get_policy_compliance_matrix(
    period: str = Query("12mo", description="Period filter: 6mo | 12mo | 24mo"),
    tier: Optional[str] = Query(None, description="Filter by assignment tier"),
    destination: Optional[str] = Query(None, description="Filter by destination country code"),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
):
    """
    GAP 3: Cross-case compliance heatmap for the HR control center (S5c).
    Returns all active cases with per-benefit compliance status cells.
    """
    company_id = str(user.get("company") or user.get("company_id") or "")

    period_months = {"6mo": 6, "12mo": 12, "24mo": 24}.get(period, 12)

    # Fetch data
    assignments = _get_matrix_data(company_id, period_months)
    covered_benefits_map = _get_covered_benefits_for_company(company_id)
    covered_keys = set(covered_benefits_map.keys())

    # Build caps dict
    caps_by_benefit = {
        k: float(v["cap_amount"])
        for k, v in covered_benefits_map.items()
        if v.get("cap_amount") is not None
    }

    if destination:
        assignments = [a for a in assignments if a.get("destination_country") == destination.upper()]
    if tier:
        assignments = [a for a in assignments if a.get("assignment_type") == tier]

    cases: List[ComplianceCaseRow] = []
    overrun_counts: Dict[str, int] = {k: 0 for k in BENEFIT_COLUMNS}
    total_cells = 0
    compliant_cells = 0

    for assign in assignments:
        aid = assign.get("id", "")
        name = assign.get("employee_name") or assign.get("employee_identifier") or "Unknown"
        exception_keys = _get_exception_keys_for_assignment(aid)

        # No spend data yet — use zeros (real spend tracking is V2)
        spend_by_benefit: Dict[str, float] = {}

        cells = _compute_cells(
            assign,
            covered_keys,
            exception_keys,
            spend_by_benefit,
            caps_by_benefit,
        )

        for key, status in cells.items():
            if status != "grey":
                total_cells += 1
                if status == "green":
                    compliant_cells += 1
                elif status == "red":
                    overrun_counts[key] = overrun_counts.get(key, 0) + 1

        cases.append(ComplianceCaseRow(
            id=aid,
            name=name,
            init=_initials(name),
            origin=assign.get("origin_country"),
            dest=assign.get("destination_country"),
            tier=assign.get("assignment_type"),
            assignment_type=assign.get("assignment_type"),
            start_date=assign.get("start_date"),
            budget_eur=None,
            spend_eur=None,
            cells=cells,
        ))

    compliance_pct = int((compliant_cells / total_cells) * 100) if total_cells else 100
    most_overrun = max(overrun_counts, key=overrun_counts.get) if any(overrun_counts.values()) else None

    return PolicyComplianceMatrixResponse(
        cases=cases,
        kpis=ComplianceKpis(
            compliance_pct=compliance_pct,
            active_count=len(cases),
            avg_overage_eur=None,
            most_overrun_benefit=most_overrun,
            benefit_columns=BENEFIT_COLUMNS,
            benefit_labels=BENEFIT_LABELS,
        ),
    )


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

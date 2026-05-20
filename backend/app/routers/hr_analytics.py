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

from ..auth_deps import get_current_user, require_admin_or_hr
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
        from ...services.supabase_client import get_supabase_admin_client
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
        from ...services.supabase_client import get_supabase_admin_client
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
        from ...services.supabase_client import get_supabase_admin_client
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

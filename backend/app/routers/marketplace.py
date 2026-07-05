"""
GAP 8: Enriched service marketplace — GET /api/employee/assignments/{id}/marketplace

Server-side join of suppliers × policy_envelope (covered) × preferred_suppliers (preferred).
Returns vendors enriched with coverage flag, preferred flag, rating, price_range, sla.
Sorted: preferred+covered first, then covered only, then uncovered.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth_deps import get_current_user
from ...database import db as main_db

router = APIRouter(prefix="/api/employee/assignments", tags=["marketplace"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────

class MarketplaceVendor(BaseModel):
    id: str
    name: str
    service_category: str
    logo_initials: str
    rating: Optional[float] = None
    rating_count: int = 0
    price_display: Optional[str] = None
    sla_display: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    preferred: bool = False
    covered: bool = False
    preferred_partner: bool = False
    languages: Optional[List[str]] = None
    verified: bool = False


class MarketplaceResponse(BaseModel):
    assignment_id: str
    corridor: Optional[str] = None
    vendors: List[MarketplaceVendor]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _logo_initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0].upper() for p in parts[:2])


_CATEGORY_BENEFIT_MAP: Dict[str, str] = {
    "immigration": "immigration",
    "immigration_lawyer": "immigration",
    "housing": "housing",
    "housing_agent": "housing",
    "temporary_housing": "temporary_housing",
    "serviced_apartments": "temporary_housing",
    "international_movers": "shipment",
    "shipping": "shipment",
    "language_tuition": "language",
    "school_consultant": "schooling",
    "tax_advisor": "tax",
    "pet_relocation": "pet_relocation",
    "career_coaching": "spouse_support",
    "banking": "banking",
}

def _benefit_key_for_category(cat: str) -> Optional[str]:
    return _CATEGORY_BENEFIT_MAP.get((cat or "").lower().replace(" ", "_"))


def _get_covered_benefit_keys(assignment_id: str) -> set:
    """Return the set of benefit keys covered by the assignment's policy."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        # Use policy_config_benefits for the assignment's company + policy_config
        assign = main_db.get_assignment_by_id(assignment_id)
        if not assign:
            return set()
        company_id = assign.get("company_id")
        result = (
            sb.table("policy_config_benefits")
            .select("benefit_key, coverage_type")
            .eq("company_id", company_id)
            .execute()
        )
        if result and result.data:
            return {
                row["benefit_key"]
                for row in result.data
                if row.get("coverage_type") not in ("excluded", "not_applicable")
            }
    except Exception:
        logger.debug("Could not fetch policy benefit keys for assignment %s", assignment_id)
    return set()


def _get_preferred_supplier_ids(company_id: str) -> set:
    """Return supplier IDs preferred for this company — the union of globally
    preferred partners (supplier_scoring_metadata.preferred_partner) and this
    company's own HR-curated picks (company_preferred_suppliers). The sort_key in
    get_marketplace ranks preferred suppliers first, so both surface at the top."""
    preferred: set = set()
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        result = (
            sb.table("supplier_scoring_metadata")
            .select("supplier_id")
            .eq("preferred_partner", True)
            .execute()
        )
        if result and result.data:
            preferred.update(row["supplier_id"] for row in result.data)
    except Exception:
        logger.debug("Could not fetch global preferred suppliers")
    if company_id:
        try:
            from ..services.supabase_client import get_supabase_admin_client
            sb = get_supabase_admin_client()
            cps = (
                sb.table("company_preferred_suppliers")
                .select("supplier_id")
                .eq("company_id", company_id)
                .eq("status", "active")
                .execute()
            )
            if cps and cps.data:
                preferred.update(row["supplier_id"] for row in cps.data)
        except Exception:
            logger.debug("Could not fetch company preferred suppliers for %s", company_id)
    return preferred


def _fetch_suppliers(dest_country: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch suppliers with their scoring metadata and capabilities."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()

        # Get suppliers with scoring metadata joined
        result = (
            sb.table("suppliers")
            .select(
                "id, name, description, website, verified, "
                "supplier_scoring_metadata(average_rating, review_count, response_sla_hours, preferred_partner), "
                "supplier_service_capabilities(service_category, country_code, min_budget, max_budget, platform_vetting_status)"
            )
            .eq("status", "active")
            .execute()
        )
        if result and result.data:
            return result.data
    except Exception:
        logger.exception("Failed to fetch suppliers from DB")
    return []


def _sla_display(sla_hours: Optional[int]) -> Optional[str]:
    if sla_hours is None:
        return None
    if sla_hours <= 24:
        return f"{sla_hours}h response"
    days = sla_hours // 24
    return f"{days} day response"


def _price_display(min_b: Optional[float], max_b: Optional[float]) -> Optional[str]:
    if min_b is None and max_b is None:
        return None
    if min_b and max_b and min_b != max_b:
        return f"€{int(min_b):,}–€{int(max_b):,}"
    if min_b:
        return f"From €{int(min_b):,}"
    if max_b:
        return f"Up to €{int(max_b):,}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{assignment_id}/marketplace", response_model=MarketplaceResponse)
def get_marketplace(
    assignment_id: str,
    category: Optional[str] = Query(None, description="Filter by service category"),
    covered_only: bool = Query(False, description="Only show policy-covered vendors"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 8: Return vendors enriched with policy coverage and preferred status
    for the given assignment.
    """
    assignment = main_db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    company_id = assignment.get("company_id") or ""
    dest_country = assignment.get("destination_country") or assignment.get("dest_country")

    # Gather covered benefit keys and preferred supplier IDs
    covered_keys = _get_covered_benefit_keys(assignment_id)
    preferred_ids = _get_preferred_supplier_ids(company_id)

    corridor = None
    origin_country = assignment.get("origin_country") or assignment.get("from_country")
    if origin_country and dest_country:
        corridor = f"{origin_country}→{dest_country}"

    raw_suppliers = _fetch_suppliers(dest_country)

    vendors: List[MarketplaceVendor] = []
    for s in raw_suppliers:
        scoring = s.get("supplier_scoring_metadata") or {}
        # scoring can be a list (from join) or dict
        if isinstance(scoring, list):
            scoring = scoring[0] if scoring else {}

        capabilities = s.get("supplier_service_capabilities") or []
        # GAP 3: only approved capabilities may reach an employee. This path
        # queries Supabase directly and bypasses search_by_service_destination,
        # so it needs its own vetting gate. Drop the supplier if nothing remains.
        capabilities = [
            c for c in capabilities if c.get("platform_vetting_status") == "approved"
        ]
        if not capabilities:
            continue

        # Find the best matching capability for this corridor
        best_cap = None
        for cap in capabilities:
            if dest_country and cap.get("country_code") == dest_country:
                best_cap = cap
                break
        if not best_cap and capabilities:
            best_cap = capabilities[0]

        service_cat = (best_cap or {}).get("service_category", "general")

        # Filter by category if requested
        if category and service_cat.lower() != category.lower():
            continue

        benefit_key = _benefit_key_for_category(service_cat)
        is_covered = benefit_key in covered_keys if benefit_key else False
        is_preferred = s["id"] in preferred_ids or bool(scoring.get("preferred_partner"))

        if covered_only and not is_covered:
            continue

        min_b = (best_cap or {}).get("min_budget")
        max_b = (best_cap or {}).get("max_budget")
        sla_hours = scoring.get("response_sla_hours")

        vendors.append(MarketplaceVendor(
            id=s["id"],
            name=s["name"],
            service_category=service_cat,
            logo_initials=_logo_initials(s["name"]),
            rating=scoring.get("average_rating"),
            rating_count=scoring.get("review_count") or 0,
            price_display=_price_display(min_b, max_b),
            sla_display=_sla_display(sla_hours),
            description=s.get("description"),
            website=s.get("website"),
            preferred=is_preferred,
            covered=is_covered,
            preferred_partner=bool(scoring.get("preferred_partner")),
            verified=bool(s.get("verified")),
        ))

    # Sort: preferred+covered → covered → preferred → rest
    def sort_key(v: MarketplaceVendor) -> tuple:
        return (
            not (v.preferred and v.covered),
            not v.covered,
            not v.preferred,
            -(v.rating or 0),
        )

    vendors.sort(key=sort_key)

    return MarketplaceResponse(
        assignment_id=assignment_id,
        corridor=corridor,
        vendors=vendors,
        total=len(vendors),
    )

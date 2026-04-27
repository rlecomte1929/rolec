"""
Employee recommendations filter — Phase 2c.

Closes the authority loop:

    ADMIN  →  service_catalog_items   (Phase 2a)
                  ↓
    HR     →  company_vendor_selections   (Phase 2d)
                  ↓ (THIS FILTER)
    EMPLOYEE  →  recommendations API filtered through HR's selections

Strict default: an employee sees a master vendor ONLY when HR has an
explicit selected=true row for it. Items HR has no decision on are
hidden, not shown. HR's custom vendors are added to the result as
synthesized recommendation rows.

Empty-state contract: when the (company, category, city) has zero
HR-approved rows (no master selections + no customs), the filter
returns ([], "hr_pending") so the caller can render a "Your HR is
finalizing providers for {category}" placeholder rather than the
raw master.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..app.recommendations.types import (
    RecommendationExplanation,
    RecommendationItem,
    RecommendationTier,
)
from . import service_catalog, vendor_curation

log = logging.getLogger(__name__)

# Synthesized score for HR custom vendors. They didn't go through the
# scoring engine but HR explicitly approved them for this company →
# treat as "good fit" baseline; UX adds an "HR preferred" badge.
_HR_CUSTOM_SCORE = 80.0


def _custom_to_recommendation(row: Dict[str, Any]) -> RecommendationItem:
    payload = row.get("custom_item_json") or {}
    name = str(payload.get("name") or "(unnamed)")
    notes = payload.get("notes")
    metadata: Dict[str, Any] = {
        "hr_custom": True,
        "company_preferred": True,
    }
    if notes:
        metadata["notes"] = str(notes)
    rationale_bits = ["Approved by your HR team for this company."]
    if notes:
        rationale_bits.append(str(notes))
    explanation = RecommendationExplanation(
        match_reasons=["HR-approved vendor"],
        explanation_summary="HR-approved vendor for your company",
    )
    return RecommendationItem(
        item_id=f"hr-custom-{row['id']}",
        name=name,
        score=_HR_CUSTOM_SCORE,
        tier=RecommendationTier.GOOD_FIT,
        summary="Approved by your HR team",
        rationale=" ".join(rationale_bits),
        breakdown={},
        pros=["HR-approved for your company"],
        cons=[],
        metadata=metadata,
        explanation=explanation,
    )


def apply_hr_curation(
    *,
    category: str,
    items: List[RecommendationItem],
    company_id: Optional[str],
    destination_city: Optional[str],
    destination_country: Optional[str] = None,
) -> Tuple[List[RecommendationItem], Optional[str]]:
    """
    Filter the engine's ranked items down to those HR has approved for the
    company, and append HR's custom vendors. Returns (filtered_items, status)
    where status is one of:

      - None              → curation applied (or no company context — pass through)
      - "hr_pending"      → company exists but HR hasn't approved anything in
                            this category × city; UI should render placeholder.
    """
    if not company_id:
        # No tenant context (admin debug calls, unauth flows): pass through.
        return items, None

    # 1. Pull HR's selections for the (company, category, city) scope.
    selections = vendor_curation.list_curation(
        company_id=company_id,
        category=category,
        destination_city=destination_city,
    )
    approved_master_ids = {
        s["master_item_id"]
        for s in selections
        if s.get("master_item_id") and s.get("selected")
    }
    customs = [
        s
        for s in selections
        if not s.get("master_item_id") and s.get("custom_item_json") and s.get("selected")
    ]

    # 2. Walk each engine item; keep only when its master_item_id is in
    # the approved set. Items that don't have a master row at all (e.g.
    # legacy datasets that haven't been backfilled) are dropped — HR
    # can't curate what isn't in the master.
    kept: List[RecommendationItem] = []
    for rec in items:
        master = service_catalog.find_master_by_external_id(category, rec.item_id)
        if not master:
            log.debug(
                "hr_curation_filter dropped item with no master entry: "
                "category=%s item_id=%s",
                category,
                rec.item_id,
            )
            continue
        if master["id"] in approved_master_ids:
            kept.append(rec)

    # 3. Append HR custom vendors as synthesized recommendations.
    for c in customs:
        kept.append(_custom_to_recommendation(c))

    if not kept:
        # Record the demand signal so HR can see who's waiting on what.
        # Best-effort — never raise on the filter path.
        try:
            from . import employee_demand
            employee_demand.record_demand(
                company_id=company_id,
                category=category,
                destination_city=destination_city,
                destination_country=destination_country,
            )
        except Exception:
            log.exception("record_demand dispatch failed")
        return [], "hr_pending"
    return kept, None

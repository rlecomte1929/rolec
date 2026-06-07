"""
DEPRECATED (N12/AIQ-852): the ``benefits_templates`` table read here is one of four
legacy template systems now unified by ``policy_template_service.PolicyTemplateService``.
Left in place until a follow-up cleanup task migrates this route to the unified
service and retires the table after validation — do not extend.

Policy Builder — 3-tier template library (P1-2).

Routes:
  GET /api/policy/templates  — return all 3 tiers × 14 categories
                               structured as { tiers: [...] }.
                               No auth required — templates are global
                               reference data with no company-scoped values.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/policy/templates", tags=["policy_templates"])


def _sb():
    """Lazy Supabase admin client (fails fast if env vars missing)."""
    return get_supabase_admin_client()


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class TemplateCategoryOut(BaseModel):
    category_id: str
    code: str
    display_name: str
    cap_value: float
    cap_unit: str
    cap_currency: str
    benchmark_source: str


class TemplateTierOut(BaseModel):
    tier: str
    tier_order: int
    categories: List[TemplateCategoryOut]


class TemplatesResponse(BaseModel):
    ok: bool = True
    tiers: List[TemplateTierOut]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("", response_model=TemplatesResponse)
def get_policy_templates() -> TemplatesResponse:
    """
    Return the 3-tier template library (Conservative / Standard / Premium),
    each tier containing all 14 benefit categories with benchmark cap values.

    Values are seeded from AIRINC 2025, Mercer 2024, and ECA International.
    Conservative caps are always <= Standard caps <= Premium caps.
    """
    try:
        result = (
            _sb()
            .table("benefits_templates")
            .select(
                "tier, tier_order, cap_value, cap_unit, cap_currency, benchmark_source,"
                " policy_categories(id, code, display_name, sort_order)"
            )
            .order("tier_order")
            .order("policy_categories(sort_order)")
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        log.exception("get_policy_templates: DB fetch failed")
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    # Group by tier (rows already ordered by tier_order, then category sort_order)
    tiers_map: Dict[str, TemplateTierOut] = {}
    for row in rows:
        cat = row.get("policy_categories") or {}
        tier_name: str = row["tier"]
        tier_order: int = row["tier_order"]

        if tier_name not in tiers_map:
            tiers_map[tier_name] = TemplateTierOut(
                tier=tier_name,
                tier_order=tier_order,
                categories=[],
            )

        tiers_map[tier_name].categories.append(
            TemplateCategoryOut(
                category_id=cat.get("id", ""),
                code=cat.get("code", ""),
                display_name=cat.get("display_name", ""),
                cap_value=float(row["cap_value"]),
                cap_unit=row["cap_unit"],
                cap_currency=row["cap_currency"],
                benchmark_source=row["benchmark_source"],
            )
        )

    # Return tiers sorted by tier_order
    tiers = sorted(tiers_map.values(), key=lambda t: t.tier_order)

    if not tiers:
        log.warning("get_policy_templates: no template rows found — benefits_templates may be empty")

    return TemplatesResponse(tiers=tiers)

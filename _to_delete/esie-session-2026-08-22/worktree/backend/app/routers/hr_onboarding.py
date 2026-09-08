"""AIQ-1223c — HR onboarding inference endpoint.

Exposes the deterministic inference engine
(:mod:`backend.app.services.hr_onboarding_inference`) as a read-only HR route.
The proposed config is *suggested*, never applied server-side — the first-run
onboarding UI (1223d) renders it as editable pre-fills.

Per CLAUDE.md the router is registered in BOTH ``backend/app/main.py`` and
``backend/main.py`` (prod entry).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..services.hr_onboarding_inference import infer_workspace_config

router = APIRouter(prefix="/api/hr/onboarding", tags=["hr-onboarding"])


@router.get("/inferred-config")
def get_inferred_config(
    _user=Depends(require_admin_or_hr),
    company_id: str = Depends(get_org_id_for_hr_user),
):
    """Return the deterministic proposed workspace config for the caller's company.

    Resolves company via ``get_org_id_for_hr_user`` (→ ``db.get_hr_company_id``),
    matching the policy resolver. When the HR user has no resolvable company the
    proposal degrades to an empty-signal, low-confidence config rather than 500.
    """
    if not company_id:
        return {
            "company_id": None,
            "signals": {
                "size_band": None,
                "size_bucket": "unknown",
                "default_destination_country": None,
                "default_working_location": None,
                "published_tier_count": 0,
                "has_published_policy": False,
                "case_count": 0,
                "has_active_program": False,
            },
            "proposed_config": {
                "policy_tiers": ["All employees"],
                "tier_source": "size_band_guess",
                "default_destination_country": None,
                "default_working_location": None,
                "dashboard_density": "standard",
                "bulk_assign_enabled": False,
                "show_volume_nudges": False,
            },
            "confidence": "low",
        }
    return infer_workspace_config(company_id)

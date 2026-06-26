"""AIQ-1223c — deterministic HR-onboarding inference engine.

Reads the three first-session signals for a company and returns a *proposed*
workspace configuration. Per the spec
(``docs/design/aiq-1223-inference-onboarding-spec.md`` §4) the mapping is a set
of pure, deterministic table lookups — **no LLM is involved**, so there is no
``mask_pii`` / prompt path here. The proposal is always *suggested*, never
silently applied: the UI (1223d) renders it as editable pre-fills.

Signals (spec §3):
  1. Company size      → ``companies.size_band``
  2. Policy tier count → published ``policy_config_versions`` +
                         ``policy_config_benefits`` (the LIVE config-matrix
                         system, NOT legacy ``relocation_policies``/``hr_policies``)
  3. Mobility volume   → count of ``relocation_cases`` for the company

HR → company resolution is the caller's responsibility (the router uses
``get_org_id_for_hr_user`` → ``db.get_hr_company_id``), matching the policy
resolver so it never mis-scopes a legacy text HR id.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .policy_config_matrix_service import CONFIG_KEY

log = logging.getLogger(__name__)

# Deterministic tier scaffolds keyed by coarse size bucket (spec §4).
_TIERS_SINGLE: List[str] = ["All employees"]
_TIERS_TWO: List[str] = ["Standard", "Senior"]
_TIERS_THREE: List[str] = ["Standard", "Senior", "Executive"]


def _size_bucket(size_band: Optional[str]) -> str:
    """Map a (free-form) size_band string to a coarse bucket.

    ReloPass has two band vocabularies in the wild — the HR company-profile form
    uses ``1–10 … 5000+`` while the admin company form uses ``10–50``/
    ``200–1000``. Rather than exact-match the strings we parse the numeric
    ceiling out of the band and bucket on that, so both vocabularies resolve
    deterministically.

    Returns one of: ``"small"`` (≤50), ``"medium"`` (≤500), ``"large"`` (>500),
    or ``"unknown"`` when no number can be parsed.
    """
    if not size_band:
        return "unknown"
    nums = [int(n) for n in re.findall(r"\d+", str(size_band))]
    if not nums:
        return "unknown"
    ceiling = max(nums)
    if ceiling <= 50:
        return "small"
    if ceiling <= 500:
        return "medium"
    return "large"


def _published_tier_count(company_id: str) -> int:
    """Distinct policy tiers in the company's LIVE published config.

    A "tier" is a distinct targeting group, identified by
    ``policy_config_benefits.targeting_signature`` within the published version.
    Returns 0 when no published config exists. Pure lookup — never raises.
    """
    try:
        pub = db.get_latest_published_policy_config_version(str(company_id), CONFIG_KEY)
        if not pub or not pub.get("id"):
            return 0
        benefits = db.list_policy_config_benefits(str(pub["id"])) or []
        sigs = {
            str(b.get("targeting_signature") or "")
            for b in benefits
            if b.get("targeting_signature")
        }
        return len(sigs)
    except Exception as exc:  # pragma: no cover - defensive, degrade to 0
        log.warning("hr_onboarding_inference: tier-count lookup failed: %s", exc)
        return 0


def _case_count(company_id: str) -> int:
    """Number of relocation_cases for the company (mobility-volume signal)."""
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM relocation_cases WHERE company_id = :cid"),
                {"cid": str(company_id)},
            ).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception as exc:  # pragma: no cover - defensive, degrade to 0
        log.warning("hr_onboarding_inference: case-count lookup failed: %s", exc)
        return 0


def _scaffold_for_bucket(bucket: str) -> List[str]:
    if bucket == "small":
        return list(_TIERS_SINGLE)
    if bucket == "large":
        return list(_TIERS_THREE)
    if bucket == "medium":
        return list(_TIERS_TWO)
    # unknown → conservative single-tier scaffold
    return list(_TIERS_SINGLE)


def _scaffold_for_count(tier_count: int) -> List[str]:
    """Reconcile a generic tier scaffold to a real published tier count."""
    if tier_count <= 1:
        return list(_TIERS_SINGLE)
    if tier_count == 2:
        return list(_TIERS_TWO)
    if tier_count == 3:
        return list(_TIERS_THREE)
    return [f"Tier {i + 1}" for i in range(tier_count)]


def infer_workspace_config(company_id: str) -> Dict[str, Any]:
    """Return the proposed workspace config + confidence for ``company_id``.

    Fully deterministic. All lookups degrade gracefully so the endpoint always
    returns a usable proposal (the UI uses it as editable pre-fills).
    """
    company = db.get_company(str(company_id)) or {}
    size_band = (company.get("size_band") or "").strip() or None
    dest_country = (company.get("default_destination_country") or "").strip() or None
    working_location = (company.get("default_working_location") or "").strip() or None

    bucket = _size_bucket(size_band)
    tier_count = _published_tier_count(str(company_id))
    has_published_policy = tier_count > 0
    case_count = _case_count(str(company_id))
    has_active_program = case_count > 0

    # Tier scaffold: real published tier count wins over the size-band guess
    # (spec §4 "real data wins over the size-band guess").
    if has_published_policy:
        policy_tiers = _scaffold_for_count(tier_count)
        tier_source = "published"
    else:
        policy_tiers = _scaffold_for_bucket(bucket)
        tier_source = "size_band_guess"

    # Dashboard density: active program once cases exist; else compact for the
    # smallest orgs, standard otherwise.
    if has_active_program:
        dashboard_density = "active_program"
    elif bucket == "small":
        dashboard_density = "compact"
    else:
        dashboard_density = "standard"

    bulk_assign_enabled = bucket == "large"
    show_volume_nudges = bucket != "small" and bucket != "unknown"

    # Confidence: high when we have real published data + a size band; medium
    # when we only have the size band; low when even the size band is missing.
    if has_published_policy and size_band:
        confidence = "high"
    elif size_band:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "company_id": str(company_id),
        "signals": {
            "size_band": size_band,
            "size_bucket": bucket,
            "default_destination_country": dest_country,
            "default_working_location": working_location,
            "published_tier_count": tier_count,
            "has_published_policy": has_published_policy,
            "case_count": case_count,
            "has_active_program": has_active_program,
        },
        "proposed_config": {
            "policy_tiers": policy_tiers,
            "tier_source": tier_source,
            "default_destination_country": dest_country,
            "default_working_location": working_location,
            "dashboard_density": dashboard_density,
            "bulk_assign_enabled": bulk_assign_enabled,
            "show_volume_nudges": show_volume_nudges,
        },
        "confidence": confidence,
    }

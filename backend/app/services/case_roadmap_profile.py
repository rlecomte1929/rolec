"""P2-01e — map a wizard case to the RAG roadmap pipeline inputs and run it.

Bridges the user-facing case (wizard_cases draft) to the immigration RAG pipeline:
classify the pathway (immigration_regime), normalise countries to ISO-2 so the
corridor matches the ingested rule chunks (e.g. "FR→NO"), build the retriever's
UserProfile + PathClassification, and run rag_pipeline. Returns the pipeline
roadmap (which may be RULE_NOT_FOUND) or None when the case can't be mapped.

The country normaliser and EEA/pathway classification are reused from existing
services so this stays a thin glue layer.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from . import rag_pipeline
from .country_resources import _country_code_from_name
from .immigration_regime import ImmigrationRegimeRouter, _is_eu_national
from .immigration_retriever import PathClassification, UserProfile, corridor_key

log = logging.getLogger(__name__)

_router = ImmigrationRegimeRouter()


def _iso2(value: Optional[str]) -> Optional[str]:
    """Normalise a country name or code to ISO-2 (e.g. 'France'/'fr' → 'FR')."""
    if not value:
        return None
    code = _country_code_from_name(str(value).strip())
    return code or None


def build_case_profile(
    case: Dict[str, Any],
) -> Optional[Tuple[UserProfile, PathClassification]]:
    """Map a case dict (with a `draft`) to (UserProfile, PathClassification), or
    None when origin/destination are missing. Countries are ISO-2 normalised so
    the corridor matches the ingested rule chunks."""
    draft = case.get("draft") or {}
    basics = draft.get("relocationBasics") or {}
    origin_raw = basics.get("originCountry")
    dest_raw = basics.get("destCountry")
    if not origin_raw or not dest_raw:
        return None
    origin = _iso2(origin_raw)
    dest = _iso2(dest_raw)
    if not origin or not dest:
        return None

    nationality = (
        basics.get("nationality")
        or (draft.get("personalInfo") or {}).get("nationality")
        or origin_raw  # an EEA-corridor mover is typically a national of the origin
    )
    regime = _router.detect_regime(
        nationality=nationality,
        destination_country=dest_raw,
        origin_country=origin_raw,
    )
    profile = UserProfile(
        nationality=str(nationality or ""),
        origin_country=origin,
        destination_country=dest,
        is_eea=_is_eu_national(nationality),
    )
    classification = PathClassification(
        pathway_type=regime.regime_id,
        corridor=corridor_key(origin, dest),
    )
    return profile, classification


def generate_ai_roadmap_for_case(case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build the case profile and run the RAG roadmap pipeline end to end.
    Returns the pipeline roadmap dict (possibly RULE_NOT_FOUND), or None when the
    case can't be mapped to a corridor."""
    mapping = build_case_profile(case)
    if mapping is None:
        return None
    profile, classification = mapping
    return rag_pipeline.generate_roadmap(profile=profile, classification=classification)

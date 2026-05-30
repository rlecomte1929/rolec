"""
Immigration RAG retriever (P1-01a) — first stage of the roadmap pipeline.

Wraps the company-scoped `policy_chunk_retriever` and adds the
immigration-specific applicability filters the generator needs: corridor
(origin→destination) and visa pathway type. Immigration rules are not
company-specific, so they live under a single synthetic corpus "company"
(`IMMIGRATION_CORPUS_COMPANY_ID`) and are tagged with corridor + pathway_type
in `chunk_metadata`.

`policy_chunk_retriever` only filters by company_id + source_type, so this
wrapper over-fetches and then post-filters the result set down to the
applicable corridor/pathway. An uncovered corridor yields an empty list,
which is the retriever-side basis for the generator's RULE_NOT_FOUND guard
(P1-01b) — we never substitute a different corridor's rules.

Returned chunk shape is unchanged from `policy_chunk_retriever.retrieve`
(id, source_type, source_ref, chunk_text, chunk_metadata, score).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import policy_chunk_retriever
from .policy_assistant_embedder import Embedder

log = logging.getLogger(__name__)

# Synthetic corpus owner: immigration rules are corridor-scoped, not
# company-scoped, but policy_chunk_retriever requires a company_id.
IMMIGRATION_CORPUS_COMPANY_ID = "__immigration_corpus__"
IMMIGRATION_SOURCE_TYPE = "immigration_rule"

# Over-fetch factor: policy_chunk_retriever can't filter by corridor, so we
# pull more than top_k and trim after corridor/pathway filtering.
_OVER_FETCH_FACTOR = 5
_MAX_FETCH = 50  # policy_chunk_retriever caps top_k at 50 anyway.


@dataclass(frozen=True)
class UserProfile:
    """Classified mobility subject. Country fields are ISO-2 codes."""

    nationality: str
    origin_country: str
    destination_country: str
    is_eea: Optional[bool] = None


@dataclass(frozen=True)
class PathClassification:
    """Output of the (upstream) pathway classifier. `corridor` is derived
    from the profile when not supplied explicitly."""

    pathway_type: str
    corridor: Optional[str] = None


def corridor_key(origin: str, destination: str) -> str:
    """Canonical corridor string, e.g. ("fr", "no") -> "FR→NO"."""
    return f"{origin.strip().upper()}→{destination.strip().upper()}"


def retrieve_for_profile(
    *,
    profile: UserProfile,
    classification: PathClassification,
    top_k: int = 10,
    company_id: str = IMMIGRATION_CORPUS_COMPANY_ID,
    source_type: str = IMMIGRATION_SOURCE_TYPE,
    embedder: Optional[Embedder] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve the immigration-rule chunks that apply to this profile's
    corridor and pathway, ranked by relevance.

    Returns an empty list when the profile is incomplete or the corridor
    is uncovered (no matching chunks) — never cross-corridor substitutes.
    """
    if not profile.origin_country or not profile.destination_country:
        return []

    corridor = classification.corridor or corridor_key(
        profile.origin_country, profile.destination_country
    )
    query = _build_query(profile, classification, corridor)

    fetch_k = min(_MAX_FETCH, max(top_k, top_k * _OVER_FETCH_FACTOR))
    candidates = policy_chunk_retriever.retrieve(
        company_id=company_id,
        query=query,
        top_k=fetch_k,
        source_types=[source_type],
        embedder=embedder,
    )

    applicable = [
        c for c in candidates
        if _applies(c.get("chunk_metadata") or {}, corridor, classification.pathway_type)
    ]
    result = applicable[:top_k]

    log.info(
        "immigration_retriever corridor=%s pathway=%s candidates=%d applicable=%d returned=%d scores=%s",
        corridor,
        classification.pathway_type,
        len(candidates),
        len(applicable),
        len(result),
        [round(c.get("score", 0.0), 4) for c in result],
    )
    return result


def _applies(meta: Dict[str, Any], corridor: str, pathway_type: str) -> bool:
    """A chunk applies when its corridor matches and its pathway_type either
    matches or is unset (a corridor-wide rule that spans all pathways)."""
    if meta.get("corridor") != corridor:
        return False
    chunk_pathway = meta.get("pathway_type")
    return chunk_pathway is None or chunk_pathway == pathway_type


def _build_query(
    profile: UserProfile, classification: PathClassification, corridor: str
) -> str:
    eea = "EEA" if profile.is_eea else "non-EEA"
    return (
        f"{classification.pathway_type} immigration requirements for a "
        f"{eea} {profile.nationality} national relocating {corridor}"
    )

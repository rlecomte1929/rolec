"""[AIQ-806 / P3-04f] Single source of truth for source-tier → confidence level.

A source page's trust *tier* (``source_pages.tier``) is the provenance signal that
drives the roadmap ConfidenceBadge. Tier 1 = official primary authority → HIGH;
tier 2 = secondary/official-adjacent → MEDIUM; tier 3 = informational → LOW.
Anything missing or unrecognised → UNKNOWN — we never fabricate confidence when
there is no source behind a step.

This mapping was previously inlined as ``_tier_to_confidence`` in
``backend/app/routers/cases_read.py`` (P3-04e-FU). It is centralised here so every
roadmap serializer (the ``/roadmap/tracks`` projection AND the relocation-plan
view) resolves confidence identically — no drift between surfaces.

The tier weights line up with the retrieval-boost convention in
``policy_chunk_retriever.py`` ({1: 1.0, 2: 0.9, 3: 0.75}) and the documented
RequirementCard bands (>80 green / 50-80 yellow / <50 red — see
``cases_read._bucket_confidence``).
"""
from __future__ import annotations

from typing import Optional, Union

# Tier is stored as TEXT ('1'/'2'/'3') in source_pages but arrives as int from
# corpus JSON, so accept both. Order matters only for readability.
_TIER_TO_CONFIDENCE = {"1": "HIGH", "2": "MEDIUM", "3": "LOW"}

UNKNOWN = "UNKNOWN"


def tier_to_confidence(tier: Union[int, str, None]) -> str:
    """Map a source trust tier to a roadmap-step confidence level.

    Returns one of ``'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'``. Missing or
    unrecognised tiers resolve to ``'UNKNOWN'`` (honest — never fabricated).

    >>> tier_to_confidence(1), tier_to_confidence("2"), tier_to_confidence(3)
    ('HIGH', 'MEDIUM', 'LOW')
    >>> tier_to_confidence(None), tier_to_confidence("9"), tier_to_confidence("")
    ('UNKNOWN', 'UNKNOWN', 'UNKNOWN')
    """
    if tier is None:
        return UNKNOWN
    # int(2) and "2" must collapse to the same key; floats like 2.0 too.
    if isinstance(tier, float):
        tier = int(tier)
    key = str(tier).strip()
    return _TIER_TO_CONFIDENCE.get(key, UNKNOWN)

"""[AIQ-806 / P3-04f] Single source of truth for source-tier → confidence level.

A source page's trust *tier* (``source_pages.tier``) is the provenance signal that
drives the roadmap ConfidenceBadge. Tier 1 = official primary authority → HIGH;
tier 2 = secondary/official-adjacent → MEDIUM; tier 3 = informational → LOW.
Anything missing or unrecognised → UNKNOWN — we never fabricate confidence when
there is no source behind a step.

``source_pages.tier`` carries TWO tier vocabularies in practice (AIQ-1378):
- **numeric** ``'1'/'2'/'3'`` — the form_templates seed + the corpus backfill
  (corpus ``source_tier`` is an int), and
- **crawler trust_tier** ``T0/T1/T2/T3`` — written by the crawl source registry
  (``crawl_tier_config.py``: T0 = critical/official-primary, T1 = stable tier-1,
  T2/T3 = lower-trust).
Both are recognised here so crawler-sourced steps resolve a real badge instead of
falling through to UNKNOWN.

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

from typing import Union

# Numeric vocabulary — TEXT ('1'/'2'/'3') in source_pages, int from corpus JSON.
_TIER_TO_CONFIDENCE = {"1": "HIGH", "2": "MEDIUM", "3": "LOW"}

# Crawler trust_tier vocabulary (T0..T3) — see crawl_tier_config.py. T0 (critical)
# and T1 (stable tier-1) are both official "Tier 1" sources → HIGH; T2/T3 are the
# lower-trust monthly-crawl band → MEDIUM/LOW.
_TRUST_TIER_TO_CONFIDENCE = {"T0": "HIGH", "T1": "HIGH", "T2": "MEDIUM", "T3": "LOW"}

UNKNOWN = "UNKNOWN"


def tier_to_confidence(tier: Union[int, str, None]) -> str:
    """Map a source trust tier to a roadmap-step confidence level.

    Accepts both the numeric (``1/2/3``) and crawler trust_tier (``T0..T3``,
    case-insensitive) vocabularies. Returns one of
    ``'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'``. Missing or unrecognised tiers
    resolve to ``'UNKNOWN'`` (honest — never fabricated).

    >>> tier_to_confidence(1), tier_to_confidence("2"), tier_to_confidence(3)
    ('HIGH', 'MEDIUM', 'LOW')
    >>> tier_to_confidence("T0"), tier_to_confidence("t2"), tier_to_confidence("T3")
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
    if key in _TIER_TO_CONFIDENCE:
        return _TIER_TO_CONFIDENCE[key]
    return _TRUST_TIER_TO_CONFIDENCE.get(key.upper(), UNKNOWN)

"""
N9 / AIQ-849 — multi-source triangulation reconciler.

Given the official (trust_tier=1) and the unrestricted (all-tier) retrieval sets
for a corridor, decide for each chunk whether its claim is CORROBORATED across
source tiers. Agreement signal is semantic similarity between stored chunk
embeddings — NO LLM/embedder call (keeps latency low), per the N9 constraint.

source_agreement per chunk:
  - 'confirmed'      — a same-corridor chunk in the OTHER tier has cosine >= 0.85
  - 'official_only'  — a tier-1 chunk with no secondary corroboration
  - 'secondary_only' — a non-tier-1 chunk with no official corroboration

A tier-1 chunk is "official"; everything else is "secondary". Corroboration must
cross that boundary — a tier-1 source agreeing with another tier-1 source (or a
secondary with another secondary) is not triangulation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .policy_assistant_embedder import cosine_similarity

AGREEMENT_THRESHOLD = 0.85
_OFFICIAL_TIER = 1

# Confidence contribution per agreement state (answer confidence = max over chunks).
_AGREEMENT_WEIGHT = {
    "confirmed": 1.0,
    "official_only": 0.75,
    "secondary_only": 0.4,
}


def _tier(chunk: Dict[str, Any]) -> Optional[int]:
    try:
        t = chunk.get("trust_tier")
        return int(t) if t is not None and str(t).strip() != "" else None
    except (TypeError, ValueError):
        return None


def _is_official(chunk: Dict[str, Any]) -> bool:
    return _tier(chunk) == _OFFICIAL_TIER


def _embedding(chunk: Dict[str, Any]) -> List[float]:
    emb = chunk.get("embedding") or []
    return emb if isinstance(emb, list) else []


def _corroborated(chunk: Dict[str, Any], others: Sequence[Dict[str, Any]], threshold: float) -> bool:
    """True iff some `other` (same corridor) is semantically near this chunk."""
    emb = _embedding(chunk)
    if not emb:
        return False
    corridor = chunk.get("corridor")
    for o in others:
        if o.get("corridor") != corridor:
            continue
        oe = _embedding(o)
        if oe and cosine_similarity(emb, oe) >= threshold:
            return True
    return False


def reconcile(
    official_chunks: Sequence[Dict[str, Any]],
    secondary_chunks: Sequence[Dict[str, Any]],
    *,
    threshold: float = AGREEMENT_THRESHOLD,
) -> Dict[str, Any]:
    """
    Triangulate the two retrieval sets. Returns:
      {
        "reconciled_chunks": [...],   # deduped by id, each with source_agreement
        "summary": {confirmed, official_only, secondary_only},
      }
    Pure vector math — takes no client/embedder and makes no model call.
    """
    # Dedup the union by chunk id (the unrestricted set re-returns the tier-1 rows).
    merged: Dict[Any, Dict[str, Any]] = {}
    for c in list(official_chunks) + list(secondary_chunks):
        cid = c.get("id")
        if cid not in merged:
            merged[cid] = c

    chunks = list(merged.values())
    officials = [c for c in chunks if _is_official(c)]
    secondaries = [c for c in chunks if not _is_official(c)]

    reconciled: List[Dict[str, Any]] = []
    summary = {"confirmed": 0, "official_only": 0, "secondary_only": 0}
    for c in chunks:
        if _is_official(c):
            agreement = "confirmed" if _corroborated(c, secondaries, threshold) else "official_only"
        else:
            agreement = "confirmed" if _corroborated(c, officials, threshold) else "secondary_only"
        summary[agreement] += 1
        reconciled.append({**c, "source_agreement": agreement})

    return {"reconciled_chunks": reconciled, "summary": summary}


def confidence_from_agreement(reconciled_chunks: Sequence[Dict[str, Any]]) -> float:
    """
    Derive an answer-level confidence (0..1) from per-chunk source_agreement.
    Confirmed (cross-tier corroborated) > official_only > secondary_only.

    This is the N9-owned confidence signal. It is intentionally simple (max over
    the chunks the answer is built from) and is the hook a future dedicated
    confidence model (N6) can refine.
    """
    weights = [
        _AGREEMENT_WEIGHT.get(str(c.get("source_agreement")), 0.0)
        for c in reconciled_chunks
    ]
    return max(weights) if weights else 0.0

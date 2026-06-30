"""
Claim-level RAG error localization (a RAGChecker analog).

Closes a documented gap in ``backend/app/services/factual_verifier.py``:
``verify_step`` can only tell whether a roadmap step is supported by the
chunks that were RETRIEVED. When a step is *not* grounded, it cannot say
*why* — and the two causes need opposite fixes:

  * **retriever_miss**           — a chunk that WOULD support the step's claim
                                   exists in the CORPUS but was not retrieved.
                                   The generator is fine; fix RETRIEVAL.
  * **generator_hallucination**  — no supporting chunk exists in the corpus at
                                   all (the claim is invented or contradicts the
                                   corpus). Retrieval is fine; fix the GENERATOR.

This module is the deterministic decision core. It is pure: no DB, no LLM, no
network. The offline default approximates "would support" with the gold
``expected_chunk_ids`` for a query/step (the support of a step is its expected
chunk). An optional ``grounded`` override lets a ``--live`` caller substitute
``factual_verifier``'s real verdict for the offline grounding heuristic while
reusing the same localization logic.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Optional, Sequence

# Localization labels (the three mutually exclusive outcomes).
GROUNDED = "grounded"
RETRIEVER_MISS = "retriever_miss"
GENERATOR_HALLUCINATION = "generator_hallucination"
LABELS = (GROUNDED, RETRIEVER_MISS, GENERATOR_HALLUCINATION)


def localize_step(
    step: Any,
    retrieved_ids: Sequence[str],
    corpus_ids: Sequence[str],
    gold_support_ids: Sequence[str],
    *,
    grounded: Optional[bool] = None,
) -> str:
    """Localize the error for a single (possibly ungrounded) step.

    Args:
        step: The roadmap step under evaluation. Carried for caller context and
            the optional live-grounding path; the deterministic decision below
            is driven entirely by the three id sets, so its concrete type is
            unconstrained (a dict, a title string, a query id, ...).
        retrieved_ids: Chunk ids the retriever returned for the profile (top-k).
        corpus_ids: The full corridor chunk set the retriever drew from.
        gold_support_ids: Ids of chunks that support the step's claim. Offline
            this is the query's gold ``expected_chunk_ids``.
        grounded: Optional override for the grounding decision. ``None`` (default)
            uses the hermetic heuristic — grounded iff a gold-support chunk was
            actually retrieved. A ``--live`` caller may pass ``factual_verifier``'s
            ``StepVerdict.supported`` here instead.

    Returns:
        One of ``LABELS``.
    """
    retrieved = set(retrieved_ids or ())
    corpus = set(corpus_ids or ())
    gold = set(gold_support_ids or ())

    if grounded is None:
        is_grounded = bool(gold & retrieved)
    else:
        is_grounded = bool(grounded)

    if is_grounded:
        return GROUNDED

    # Not grounded — localize the failure.
    if gold & corpus:
        # Support EXISTS in the corpus but was not retrieved -> retriever's fault.
        return RETRIEVER_MISS
    # No supporting chunk anywhere in the corpus -> the generator invented it.
    return GENERATOR_HALLUCINATION


def aggregate_localization(results: Iterable[Any]) -> dict:
    """Aggregate a stream of localization outcomes into counts + rates.

    Args:
        results: Iterable of either label strings (see ``LABELS``) or dicts
            carrying a ``"localization"`` key.

    Returns:
        ``{n, grounded, retriever_miss, generator_hallucination,
           grounded_rate, retriever_miss_rate, generator_hallucination_rate}``.
    """
    counts: Counter = Counter()
    n = 0
    for r in results:
        if isinstance(r, str):
            label = r
        elif isinstance(r, dict):
            label = r.get("localization")
        else:
            label = None
        if label not in LABELS:
            raise ValueError(f"Unknown localization label: {label!r}")
        counts[label] += 1
        n += 1

    def _rate(label: str) -> float:
        return round(counts[label] / n, 4) if n else 0.0

    return {
        "n": n,
        GROUNDED: counts[GROUNDED],
        RETRIEVER_MISS: counts[RETRIEVER_MISS],
        GENERATOR_HALLUCINATION: counts[GENERATOR_HALLUCINATION],
        "grounded_rate": _rate(GROUNDED),
        "retriever_miss_rate": _rate(RETRIEVER_MISS),
        "generator_hallucination_rate": _rate(GENERATOR_HALLUCINATION),
    }

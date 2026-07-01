# WS-D — pure-python ranking metrics for the supplier-ranking eval.
# No third-party deps: NDCG@k, MRR, precision@k computed from a predicted item
# ordering and a graded-relevance map. Mirrors the small-metrics-module style of
# extraction_metrics.py / roadmap_metrics.py.
from __future__ import annotations

import math
from typing import Dict, List, Sequence


def dcg_at_k(predicted_ids: Sequence[str], relevance: Dict[str, float], k: int) -> float:
    """Discounted cumulative gain over the first k predicted items.

    gain_i = rel_i / log2(i + 1) for 1-indexed positions i.
    """
    total = 0.0
    for i, item_id in enumerate(predicted_ids[:k], start=1):
        rel = float(relevance.get(item_id, 0.0))
        if rel:
            total += rel / math.log2(i + 1)
    return total


def ndcg_at_k(predicted_ids: Sequence[str], relevance: Dict[str, float], k: int) -> float:
    """Normalized DCG@k in [0, 1]. Returns 1.0 when there is no relevance signal."""
    ideal_ids = [
        item_id for item_id, _ in sorted(relevance.items(), key=lambda kv: -kv[1])
    ]
    idcg = dcg_at_k(ideal_ids, relevance, k)
    if idcg <= 0.0:
        return 1.0
    return dcg_at_k(predicted_ids, relevance, k) / idcg


def mrr(predicted_ids: Sequence[str], relevance: Dict[str, float]) -> float:
    """Reciprocal rank of the first relevant (rel > 0) predicted item; 0 if none."""
    for i, item_id in enumerate(predicted_ids, start=1):
        if float(relevance.get(item_id, 0.0)) > 0.0:
            return 1.0 / i
    return 0.0


def precision_at_k(predicted_ids: Sequence[str], relevance: Dict[str, float], k: int) -> float:
    """Fraction of the top-k predicted items that are relevant (rel > 0)."""
    if k <= 0:
        return 0.0
    hits = sum(1 for item_id in predicted_ids[:k] if float(relevance.get(item_id, 0.0)) > 0.0)
    return hits / k


def aggregate(per_case: List[Dict[str, float]]) -> Dict[str, float]:
    """Mean of each metric across cases. Empty input → zeros."""
    if not per_case:
        return {"ndcg": 0.0, "mrr": 0.0, "precision": 0.0}
    n = len(per_case)
    return {
        "ndcg": sum(c["ndcg"] for c in per_case) / n,
        "mrr": sum(c["mrr"] for c in per_case) / n,
        "precision": sum(c["precision"] for c in per_case) / n,
    }

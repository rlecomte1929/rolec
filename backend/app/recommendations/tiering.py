"""Cluster-relative supplier tiering (Parker-C).

Absolute tiering (``BasePlugin.tier``: 85/70/50 cutoffs) stops discriminating in a
thin market — e.g. all banks in BE can land in one tier. This module tiers a
supplier by its **percentile inside its own cluster**: within a (category, country)
cell, KMeans clusters suppliers on their feature profile (K chosen by silhouette),
then each cluster's score distribution defines the cutoffs — top 15% BEST_MATCH,
next 35% GOOD_FIT, next 35% OK, bottom 15% WEAK.

``scikit-learn``/``scipy``/``numpy`` are imported **lazily** inside the functions
that need them, so importing this module never requires the ML stack. Cells with
fewer than ``MIN_CLUSTER_CELL`` suppliers fall back to absolute thresholds upstream
(see ``engine.tier``), so behavior never degrades on thin data.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .types import RecommendationTier

log = logging.getLogger(__name__)

# A (category, country) cell needs at least this many clustered suppliers before
# cluster-relative tiering kicks in; below it, the caller uses absolute thresholds.
MIN_CLUSTER_CELL = 8

# Percentile cutoffs that define the tier split (top 15 / 35 / 35 / 15).
PCT_BEST = 85.0
PCT_GOOD = 50.0
PCT_OK = 15.0

# KMeans search range and determinism knobs.
K_MIN = 2
K_MAX = 6
RANDOM_STATE = 42
N_INIT = 10

# Feature extraction. availability_level is ordinal → numeric.
_AVAILABILITY_RANK = {"high": 3.0, "medium": 2.0, "low": 1.0, "scarce": 0.0}

# Process-level counter: how many times tiering fell back to absolute thresholds.
_fallback_total = 0


def fallback_total() -> int:
    """Return the process-wide cluster-tiering fallback count."""
    return _fallback_total


def incr_fallback() -> None:
    """Increment the process-wide cluster-tiering fallback count."""
    global _fallback_total
    _fallback_total += 1


@dataclass(frozen=True)
class ClusterAssignment:
    """Result of clustering one (category, country) cell.

    ``labels`` is parallel to the input supplier list; ``-1`` marks a supplier
    excluded from clustering because it had a missing feature.
    """

    labels: List[int]
    k_selected: int
    silhouette: float
    cluster_sizes: Dict[int, int] = field(default_factory=dict)


def _feature_vector(supplier: Dict[str, Any]) -> Optional[List[float]]:
    """Extract a numeric feature vector, or ``None`` if any feature is missing."""
    rating = supplier.get("rating")
    rating_count = supplier.get("rating_count")
    confidence = supplier.get("confidence")
    avail = supplier.get("availability_level")
    if rating is None or rating_count is None or confidence is None or avail is None:
        return None
    avail_rank = _AVAILABILITY_RANK.get(str(avail).lower())
    if avail_rank is None:
        return None
    try:
        return [float(rating), float(rating_count), float(confidence), avail_rank]
    except (TypeError, ValueError):
        return None


def cluster_suppliers(
    suppliers: List[Dict[str, Any]], category: str, country_iso2: str
) -> ClusterAssignment:
    """Cluster a cell's suppliers; pick K in ``[K_MIN, K_MAX]`` by best silhouette.

    Suppliers with a missing feature get label ``-1`` and are excluded from the
    fit. Deterministic for a given input ordering (fixed ``random_state``).
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    labels: List[int] = [-1] * len(suppliers)
    valid_idx: List[int] = []
    vectors: List[List[float]] = []
    for i, s in enumerate(suppliers):
        vec = _feature_vector(s)
        if vec is not None:
            valid_idx.append(i)
            vectors.append(vec)

    n = len(vectors)
    if n < MIN_CLUSTER_CELL:
        # Caller will fall back to absolute thresholds; nothing to cluster.
        return ClusterAssignment(labels=labels, k_selected=0, silhouette=0.0)

    scaled = StandardScaler().fit_transform(vectors)

    best_k = K_MIN
    best_sil = -1.0
    best_labels: List[int] = [0] * n
    k_hi = min(K_MAX, n - 1)
    for k in range(K_MIN, k_hi + 1):
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT)
        fit_labels = km.fit_predict(scaled)
        sil = float(silhouette_score(scaled, fit_labels))
        if sil > best_sil:
            best_sil = sil
            best_k = k
            best_labels = [int(x) for x in fit_labels]

    cluster_sizes: Dict[int, int] = {}
    for pos, idx in enumerate(valid_idx):
        cid = best_labels[pos]
        labels[idx] = cid
        cluster_sizes[cid] = cluster_sizes.get(cid, 0) + 1

    return ClusterAssignment(
        labels=labels,
        k_selected=best_k,
        silhouette=best_sil,
        cluster_sizes=cluster_sizes,
    )


def tier_with_cluster_context(
    score: float,
    cluster_id: int,
    thresholds_per_cluster: Dict[Any, Dict[str, float]],
) -> RecommendationTier:
    """Tier ``score`` by its cluster's percentile cutoffs.

    ``thresholds_per_cluster`` maps cluster id → ``{"best", "good", "ok"}`` score
    cutoffs (the cluster's p85/p50/p15). Raises ``KeyError`` for an unknown cluster
    so the caller can fall back to absolute thresholds.
    """
    cut = thresholds_per_cluster[_cluster_key(cluster_id, thresholds_per_cluster)]
    if score >= cut["best"]:
        return RecommendationTier.BEST_MATCH
    if score >= cut["good"]:
        return RecommendationTier.GOOD_FIT
    if score >= cut["ok"]:
        return RecommendationTier.OK
    return RecommendationTier.WEAK


def _cluster_key(cluster_id: int, mapping: Dict[Any, Any]) -> Any:
    """Resolve a cluster id against a map whose keys may be int or str (JSON)."""
    if cluster_id in mapping:
        return cluster_id
    skey = str(cluster_id)
    if skey in mapping:
        return skey
    raise KeyError(cluster_id)


def _percentile_thresholds(scores: List[float]) -> Dict[str, float]:
    """Compute p85/p50/p15 score cutoffs for one cluster's scores."""
    import numpy as np

    arr = np.asarray(scores, dtype=float)
    return {
        "best": float(np.percentile(arr, PCT_BEST)),
        "good": float(np.percentile(arr, PCT_GOOD)),
        "ok": float(np.percentile(arr, PCT_OK)),
    }


def compute_cluster_cache(
    category: str, country_iso2: str, session: Any = None
) -> Optional[Dict[str, Any]]:
    """Build the ``supplier_cluster_cache`` row payload for one (category, country).

    Loads suppliers via the supplier registry, scores each with the category
    plugin, clusters them, and derives per-cluster percentile thresholds. Returns
    ``None`` when the cell is too thin to cluster (caller skips writing a row).
    """
    from datetime import datetime, timezone

    from .registry import get_plugin
    from ..services.supplier_registry import search_by_service_destination

    plugin = get_plugin(category)
    if plugin is None:
        raise ValueError(f"Unknown category: {category}")

    owns_session = False
    if session is None:
        from ..db import SessionLocal

        session = SessionLocal()
        owns_session = True
    try:
        suppliers = search_by_service_destination(
            session, category, destination_country=country_iso2, limit=500
        )
    finally:
        if owns_session:
            session.close()

    if not suppliers:
        return None

    criteria_obj = plugin.validate_and_parse({"destination_country": country_iso2})
    raw_scores = [float(plugin.score(criteria_obj, s).get("score_raw") or 0.0) for s in suppliers]
    norm_scores = plugin.normalize(raw_scores)

    assignment = cluster_suppliers(suppliers, category, country_iso2)
    total_clustered = sum(assignment.cluster_sizes.values())
    if total_clustered < MIN_CLUSTER_CELL:
        log.info(
            "cluster_tiering_refresh %s",
            json.dumps(
                {
                    "category": category,
                    "country": country_iso2,
                    "skipped": "below_min_cell",
                    "supplier_count": total_clustered,
                },
                separators=(",", ":"),
            ),
        )
        return None

    by_cluster: Dict[int, List[float]] = {}
    ids_by_cluster: Dict[str, List[str]] = {}
    for pos, supplier in enumerate(suppliers):
        cid = assignment.labels[pos]
        if cid < 0:
            continue
        by_cluster.setdefault(cid, []).append(norm_scores[pos])
        ids_by_cluster.setdefault(str(cid), []).append(str(supplier.get("item_id") or ""))

    thresholds = {str(cid): _percentile_thresholds(scores) for cid, scores in by_cluster.items()}

    log.info(
        "cluster_tiering_refresh %s",
        json.dumps(
            {
                "category": category,
                "country": country_iso2,
                "k_selected": assignment.k_selected,
                "silhouette": round(assignment.silhouette, 4),
                "supplier_count": total_clustered,
            },
            separators=(",", ":"),
        ),
    )

    return {
        "service_category": category,
        "country_iso2": country_iso2,
        "cluster_id": None,
        "cluster_size": total_clustered,
        "k_selected": assignment.k_selected,
        "silhouette": round(assignment.silhouette, 6),
        "thresholds_json": thresholds,
        "supplier_ids_json": ids_by_cluster,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

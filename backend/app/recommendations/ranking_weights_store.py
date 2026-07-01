"""Per-segment learned supplier-ranking weights store (P2).

Mirrors the ``supplier_cluster_cache`` read/write convention: one append-only
row per ``(category, segment)`` refresh, "latest ``computed_at`` wins" on read.
We chose a dedicated ``supplier_ranking_weights`` table over packing the weights
into ``ml_models.pickled_blob`` because:

* the payload is a tiny, human-readable JSON weight map (not a pickled sklearn
  object), so a queryable jsonb column beats an opaque blob for inspection and
  for the offline ranking eval to diff candidate weight sets;
* the read sits on the recommendation hot path behind a flag — a per-cell
  ``select ... order by computed_at desc limit 1`` mirrors the proven cluster
  cache exactly, with no pickle/unpickle cost;
* it keeps the trusted-pickle boundary (``ml_models``) reserved for genuine
  model artifacts.

Reads are best-effort and never raise (the table may not exist pre-migration);
writes are performed by the offline fitter CLI running as the service role.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

log = logging.getLogger(__name__)

# Sentinel for the global (un-segmented) bucket. ``segment`` is NOT NULL in the
# table so a global override is stored under this stable key; ``None`` callers
# read/write here.
GLOBAL_SEGMENT = "__global__"


def _seg(segment: Optional[str]) -> str:
    return segment if segment else GLOBAL_SEGMENT


def load_segment_weights(
    category: str, segment: Optional[str]
) -> Optional[Dict[str, float]]:
    """Latest learned weight map for ``(category, segment)``, or ``None``.

    Best-effort: returns ``None`` when the table is absent (pre-migration), the
    cell has never been fit, or anything else goes wrong. Never raises.
    """
    try:
        from ..db import SessionLocal

        sql = text(
            """
            select weights_json
            from public.supplier_ranking_weights
            where service_category = :cat and segment = :seg
            order by computed_at desc
            limit 1
            """
        )
        with SessionLocal() as session:
            row = session.execute(sql, {"cat": category, "seg": _seg(segment)}).first()
        if row is None or row[0] is None:
            return None
        raw = row[0]
        data = raw if isinstance(raw, dict) else json.loads(raw)
        return {str(k): float(v) for k, v in data.items()}
    except Exception as exc:
        log.debug("load_segment_weights(%s/%s) failed: %s", category, segment, exc)
        return None


def save_segment_weights(
    session: Any,
    *,
    category: str,
    segment: Optional[str],
    weights: Dict[str, float],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert ONE new ``supplier_ranking_weights`` row (latest wins on read).

    Mirrors ``refresh_supplier_clusters._write_cell``: append-only, never
    updates in place. The caller owns the session/commit lifecycle.
    """
    session.execute(
        text(
            """
            insert into public.supplier_ranking_weights
                (service_category, segment, weights_json, n_training_pairs,
                 model_kind, metadata_json, computed_at)
            values
                (:cat, :seg, :weights, :n_pairs, :kind, :meta, now())
            """
        ),
        {
            "cat": category,
            "seg": _seg(segment),
            "weights": json.dumps({str(k): float(v) for k, v in weights.items()}),
            "n_pairs": int((metadata or {}).get("n_training_pairs") or 0),
            "kind": (metadata or {}).get("model_kind") or "logistic_ltr",
            "meta": json.dumps(metadata or {}),
        },
    )


def list_segments_with_weights(session: Any) -> List[Dict[str, str]]:
    """All ``(service_category, segment)`` cells that have a stored weight set.

    Used by the measurement hook to know which cells a candidate eval covers.
    Best-effort: ``[]`` when the table is absent.
    """
    try:
        rows = session.execute(
            text(
                "select distinct service_category, segment "
                "from public.supplier_ranking_weights"
            )
        ).all()
        return [{"category": r[0], "segment": r[1]} for r in rows]
    except Exception as exc:
        log.debug("list_segments_with_weights failed: %s", exc)
        return []

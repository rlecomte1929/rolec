"""
Source-reliability A/B harness (deepen-evals slice 4).

The N8 source-reliability loop (down-rank chunks behind rejected answers) is built
but dormant (IMMIGRATION_RELIABILITY_WEIGHT=0). Before flipping it in prod you want
EVIDENCE it helps. This harness runs immigration_retriever._apply_quality_gates over
the same chunks at weight 0 vs weight>0 and reports the precision@k delta — so the
decision to enable re-ranking is measured, not guessed.

It only sets the (monkeypatchable) module-level weight in-process and restores it;
it never writes prod env. Build the proof here, then flip the weight separately.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from backend.app.services import source_reliability_config as _cfg
from backend.app.services.immigration_retriever import _apply_quality_gates

_MIN_SIMILARITY = 0.25


def precision_at_k(ranked_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """Fraction of the top-k ranked ids that are relevant."""
    if k <= 0:
        return 0.0
    topk = ranked_ids[:k]
    return round(sum(1 for cid in topk if cid in relevant_ids) / k, 4)


def run_ab(
    chunks: List[Dict[str, Any]],
    relevant_ids: Iterable[str],
    *,
    k: int,
    weight: float,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Rank chunks at a given reliability weight; report ranked ids + precision@k.
    Saves/restores the module weight so there is no global-state leak."""
    relevant = set(relevant_ids)
    now = now or datetime.now(timezone.utc)
    saved = _cfg.RELIABILITY_WEIGHT
    try:
        _cfg.RELIABILITY_WEIGHT = float(weight)
        ranked = _apply_quality_gates(
            chunks, min_similarity=_MIN_SIMILARITY, top_k=len(chunks), now=now
        )
    finally:
        _cfg.RELIABILITY_WEIGHT = saved
    ranked_ids = [str(c.get("id")) for c in ranked]
    return {"weight": float(weight), "ranked_ids": ranked_ids,
            "precision_at_k": precision_at_k(ranked_ids, relevant, k)}


def compare(
    chunks: List[Dict[str, Any]],
    relevant_ids: Iterable[str],
    *,
    k: int,
    weight_on: float = 1.0,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """A/B the dormant (weight 0) vs enabled (weight_on) reliability re-ranking."""
    relevant = set(relevant_ids)
    off = run_ab(chunks, relevant, k=k, weight=0.0, now=now)
    on = run_ab(chunks, relevant, k=k, weight=weight_on, now=now)
    return {"k": k, "off": off, "on": on,
            "delta": round(on["precision_at_k"] - off["precision_at_k"], 4)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="A/B source-reliability re-ranking on a chunk set.")
    parser.add_argument("--scenario", type=Path, required=True,
                        help='JSON: {"chunks":[...], "relevant_ids":[...], "k":int, "weight_on":float}')
    args = parser.parse_args(argv)
    s = json.loads(args.scenario.read_text())
    report = compare(s["chunks"], s.get("relevant_ids", []),
                     k=int(s.get("k", 1)), weight_on=float(s.get("weight_on", 1.0)))
    print(json.dumps(report, indent=2))
    if report["delta"] > 0:
        print(f"reliability re-ranking improves precision@{report['k']} by +{report['delta']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

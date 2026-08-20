"""
Roadmap completeness/ordering eval runner (Phase 2, gaps #2 + #4).

Grades produced AI roadmaps against a corridor gold (expected step set + ordering
constraints) and reports completeness / noise-precision / ordering + a composite
outcome_accuracy. Produced roadmaps come from either a JSON file or the replay-record
DB (feature_key='rag_roadmap'), so it grades exactly what the live AI path emitted.

RETIRED: this runner no longer emits the 'roadmap_completeness' dashboard report
(the aggregate corridor completeness %). An aggregate average hides rare-slice
failures (Ng MLOps C1 W2-3); the health dashboard now plots sliced non-obvious
recall vs the lawyer-verified HLP baseline instead \u2014 see
backend.eval.run_nonobvious_recall_eval. For the same reason the --gate here now
judges the WORST produced roadmap, not the mean across roadmaps.

Usage
─────
    # Grade a sample produced roadmap against the IN->DE gold:
    python -m backend.eval.run_roadmap_outcome_eval \
        --gold backend/tests/fixtures/eval/roadmap/in_de.json \
        --produced backend/tests/fixtures/eval/roadmap/in_de_produced_sample.json

    # Grade everything the live AI path has emitted for a corridor:
    python -m backend.eval.run_roadmap_outcome_eval \
        --gold .../in_de.json --from-db --corridor IN_DE --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .roadmap_metrics import aggregate_roadmap_scores, score_roadmap


def _steps_from_db(corridor: Optional[str]) -> List[List[Dict[str, Any]]]:
    from backend.app.services.ai_replay_store import list_replay_records

    out: List[List[Dict[str, Any]]] = []
    for rec in list_replay_records(feature_key="rag_roadmap", corridor=corridor, limit=5000):
        try:
            obj = json.loads(rec.get("output_masked") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if obj.get("result") == "OK" and obj.get("steps"):
            out.append(obj["steps"])
    return out


def grade_roadmaps(produced_roadmaps: List[List[Dict[str, Any]]], gold: Dict[str, Any]) -> Dict[str, Any]:
    """Score each produced roadmap against the gold and aggregate."""
    per = [score_roadmap(steps, gold) for steps in produced_roadmaps]
    agg = aggregate_roadmap_scores(per)
    agg["per_roadmap"] = per
    return agg


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade AI roadmap completeness/ordering vs a gold.")
    parser.add_argument("--gold", type=Path, required=True, help="Gold JSON (expected_steps + order).")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--produced", type=Path, help="JSON array of produced roadmaps ([[step,...],...] or [{steps:[...]}]).")
    src.add_argument("--from-db", action="store_true", help="Read produced roadmaps from replay records.")
    parser.add_argument("--corridor", default=None, help="Corridor scope for --from-db (e.g. IN_DE).")
    parser.add_argument("--min-completeness", type=float, default=0.9)
    parser.add_argument("--min-ordering", type=float, default=1.0)
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if the WORST produced roadmap is below thresholds.")
    args = parser.parse_args(argv)

    gold = json.loads(args.gold.read_text())

    if args.from_db:
        produced = _steps_from_db(args.corridor)
    else:
        raw = json.loads(args.produced.read_text())
        produced = [r["steps"] if isinstance(r, dict) else r for r in raw]

    report = grade_roadmaps(produced, gold)
    print(json.dumps(report, indent=2))

    # Gate on the WORST produced roadmap: a mean would let one badly incomplete
    # roadmap hide behind many good ones \u2014 the exact rare-slice failure mode the
    # sliced non-obvious recall metric exists to surface.
    per = report.get("per_roadmap") or []
    worst_completeness = min((r["completeness"] for r in per), default=report["completeness"])
    worst_ordering = min((r["ordering"] for r in per), default=report["ordering"])
    if args.gate and (worst_completeness < args.min_completeness
                      or worst_ordering < args.min_ordering):
        print(
            f"GATE FAILED (worst roadmap): completeness {worst_completeness} (min {args.min_completeness}), "
            f"ordering {worst_ordering} (min {args.min_ordering})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

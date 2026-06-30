# WS-D — offline supplier-ranking eval.
# Runs the live recommendation engine for each golden (category, corridor) case
# and scores its predicted ordering against the seeded golden relevance using
# NDCG@k / MRR / precision@k. With --ci, exits non-zero when mean NDCG@k drops
# below a regression threshold.
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ranking_metrics import aggregate, mrr, ndcg_at_k, precision_at_k

DEFAULT_FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "ranking"
    / "golden_rankings.json"
)

# Mean NDCG@k below this fails --ci. The engine reproduces the golden ordering it
# was seeded from, so a healthy run scores ~1.0; this guards against regressions.
NDCG_GATE = 0.90


def _load_fixtures(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _predicted_order(category: str, criteria: Dict[str, Any]) -> List[str]:
    """Engine's ranked item_ids for a category+criteria (admin/uncurated path)."""
    # Imported lazily so the metrics stay importable without the backend stack.
    from backend.app.recommendations.engine import recommend_debug

    dbg = recommend_debug(category, criteria, top_n=100)
    return [row["item_id"] for row in dbg["ranked"]]


def run_eval(fixtures: Dict[str, Any]) -> Dict[str, Any]:
    k = int(fixtures.get("_meta", {}).get("k", 5))
    per_case: List[Dict[str, Any]] = []
    metric_rows: List[Dict[str, float]] = []

    for case in fixtures.get("cases", []):
        category = case["category"]
        corridor = case.get("corridor", "")
        relevance = {str(kk): float(vv) for kk, vv in case.get("relevance", {}).items()}
        predicted = _predicted_order(category, case["criteria"])

        row = {
            "ndcg": ndcg_at_k(predicted, relevance, k),
            "mrr": mrr(predicted, relevance),
            "precision": precision_at_k(predicted, relevance, k),
        }
        metric_rows.append(row)
        per_case.append(
            {
                "category": category,
                "corridor": corridor,
                "k": k,
                **{m: round(v, 4) for m, v in row.items()},
                "predicted_top_k": predicted[:k],
                "ideal_top_k": case.get("ideal_order", [])[:k],
            }
        )

    agg = aggregate(metric_rows)
    return {
        "k": k,
        "n_cases": len(per_case),
        "aggregate": {m: round(v, 4) for m, v in agg.items()},
        "ndcg_gate": NDCG_GATE,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline supplier-ranking eval.")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="Golden rankings JSON (default: tests/fixtures/ranking/golden_rankings.json).",
    )
    parser.add_argument("--json", action="store_true", help="Emit the full JSON report.")
    parser.add_argument(
        "--ci",
        action="store_true",
        help=f"Exit 1 if mean NDCG@k < {NDCG_GATE}.",
    )
    args = parser.parse_args()

    os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
    report = run_eval(_load_fixtures(args.fixtures))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        agg = report["aggregate"]
        print(
            f"ranking eval: cases={report['n_cases']} k={report['k']} "
            f"NDCG@{report['k']}={agg['ndcg']:.4f} MRR={agg['mrr']:.4f} "
            f"P@{report['k']}={agg['precision']:.4f}"
        )

    if args.ci and report["aggregate"]["ndcg"] < NDCG_GATE:
        print(
            f"\nGATE FAILURE: mean NDCG@{report['k']}="
            f"{report['aggregate']['ndcg']:.4f} < {NDCG_GATE}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

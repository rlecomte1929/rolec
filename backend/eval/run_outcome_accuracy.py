"""
Outcome-accuracy producer for the rag-eval dashboard.

Unblocks the dashboard's previously-dead ``outcome_accuracy`` metric
(``rag_eval_reports.METRIC_SPECS`` has had an ``outcome_accuracy`` spec with no
producer — ``run_roadmap_outcome_eval`` writes under the ``roadmap_completeness``
key, so the ``outcome_accuracy`` filename family was never emitted).

This producer grades an ASSEMBLED roadmap against a seeded golden roadmap and writes
``outcome_accuracy_<YYYYMMDD>.json`` into ``audit/rag_eval/`` in the exact shape
``rag_eval_reports.load_live_reports`` reads (top-level numeric ``aggregate`` +
``generated_at``).

The roadmap is assembled deterministically from the gold's ``profile`` via
``ImmigrationRegimeRouter`` (task_codes → step titles), then scored with the existing
``roadmap_metrics.score_roadmap`` / ``aggregate_roadmap_scores`` helpers. The composite
``outcome_accuracy`` (mean of completeness / noise-precision / ordering) is the reported
aggregate — fully offline, no LLM, reusing the shipped grading + dashboard-writer infra.

Usage
─────
    # Emit audit/rag_eval/outcome_accuracy_20260630.json from the seed gold:
    python -m backend.eval.run_outcome_accuracy \
        --gold backend/tests/fixtures/eval/outcome_accuracy/us_l1b_gold.json \
        --out audit/rag_eval --today 2026-06-30 --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .dashboard_report import write_dashboard_report
from .roadmap_metrics import aggregate_roadmap_scores, score_roadmap

# Anchor to this source file (backend/eval/…), not the process cwd, so the gold
# fixture loads whether pytest/python runs from the repo root or from backend/.
# parents[1] = the backend/ dir. (AIQ-1665)
_DEFAULT_GOLD = Path(__file__).resolve().parents[1] / "tests/fixtures/eval/outcome_accuracy/us_l1b_gold.json"


def assemble_roadmap(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Assemble a roadmap from the deterministic immigration regime router.

    Each regime task_code becomes a roadmap step whose title is the task_code, so the
    gold's `match` substrings can grade it. No LLM — pure lookup-table composition.
    """
    from backend.app.services.immigration_regime import ImmigrationRegimeRouter

    result = ImmigrationRegimeRouter().detect_regime(
        nationality=profile.get("nationality"),
        destination_country=profile.get("destination_country"),
        origin_country=profile.get("origin_country"),
        contract_type=profile.get("contract_type"),
    )
    return [
        {"order": i + 1, "title": code} for i, code in enumerate(result.task_codes)
    ]


def grade(gold: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble + score the roadmap for this gold; return the report dict.

    aggregate_roadmap_scores supplies the composite `outcome_accuracy` (mean of
    completeness / noise_precision / ordering).
    """
    produced = assemble_roadmap(gold.get("profile") or {})
    per = score_roadmap(produced, gold)
    report = aggregate_roadmap_scores([per])
    report["per_roadmap"] = per
    report["assembled_steps"] = [s["title"] for s in produced]
    report["corridor"] = gold.get("corridor")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grade an assembled roadmap vs a golden roadmap; emit the "
        "outcome_accuracy dashboard report."
    )
    parser.add_argument("--gold", type=Path, default=_DEFAULT_GOLD,
                        help="Golden roadmap JSON (profile + expected_steps + order).")
    parser.add_argument("--out", type=Path, default=Path("audit/rag_eval"),
                        help="Dir to write outcome_accuracy_<date>.json.")
    parser.add_argument("--today", type=str, default=None,
                        help="YYYY-MM-DD stamp for the report filename (default: today).")
    parser.add_argument("--min-outcome-accuracy", type=float, default=0.90,
                        help="Gate threshold (matches the dashboard's outcome_accuracy spec).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if outcome_accuracy < threshold.")
    args = parser.parse_args(argv)

    gold = json.loads(args.gold.read_text())
    report = grade(gold)
    print(json.dumps(report, indent=2))

    today = date.fromisoformat(args.today) if args.today else None
    dest = write_dashboard_report(
        args.out, "outcome_accuracy", report["outcome_accuracy"], report, today=today
    )
    print(f"wrote {dest}", file=sys.stderr)

    if args.gate and report["outcome_accuracy"] < args.min_outcome_accuracy:
        print(
            f"GATE FAILED: outcome_accuracy {report['outcome_accuracy']} "
            f"< {args.min_outcome_accuracy}. Missing: {report['per_roadmap']['missing_steps']}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

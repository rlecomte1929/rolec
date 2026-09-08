"""P1 gate-impact canary — CLI.

Runs the read-only gate-impact rollup against the configured DB and prints a
threshold sweep (0.3 / 0.5 / 0.7), so flipping ``POLICY_RAG_GROUNDEDNESS_GATE``
becomes evidence-based. No LLM, no replay — it only re-applies the gate predicate
to grounding verdicts/scores the verifier already persisted on every answer.

How to read the number
──────────────────────
``would_refuse_rate`` at min_score=0.5 is the fraction of REAL policy answers the
gate would have replaced with a refusal. ``n_would_refuse_helpful`` is the count
of those answers a real user marked helpful — candidate FALSE refusals (the
higher this is, the more user-useful answers the gate would suppress).

Usage
─────
    python -m backend.scripts.eval_gate_impact
    python -m backend.scripts.eval_gate_impact --json
    python -m backend.scripts.eval_gate_impact --since 2026-01-01 --company <id>
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

DEFAULT_THRESHOLDS = [0.3, 0.5, 0.7]


def run_sweep(
    *,
    thresholds: List[float],
    since: Optional[str],
    company_id: Optional[str],
    feature_key: str,
) -> Dict[str, Any]:
    """Call the DB rollup once per threshold; return a JSON-able report."""
    from backend.database import db  # lazy: avoid DB engine init on import

    sweep = [
        db.get_gate_impact_rollup(
            min_score=t,
            since=since,
            company_id=company_id,
            feature_key=feature_key,
        )
        for t in thresholds
    ]
    return {
        "feature_key": feature_key,
        "since": since,
        "company_id": company_id,
        "sweep": sweep,
    }


def _print_human(report: Dict[str, Any]) -> None:
    scope = report.get("company_id") or "ALL companies"
    since = report.get("since") or "all time"
    print(f"Gate-impact canary — {report['feature_key']} — {scope} — since {since}")
    print("(read-only: re-applies the groundedness gate predicate to persisted traces)")
    print()
    header = f"{'min_score':>10}  {'answers':>8}  {'would_refuse':>12}  {'rate':>7}  {'helpful*':>9}"
    print(header)
    print("-" * len(header))
    for r in report["sweep"]:
        print(
            f"{r['min_score']:>10}  {r['n_answers']:>8}  {r['n_would_refuse']:>12}  "
            f"{r['would_refuse_rate']:>7}  {r['n_would_refuse_helpful']:>9}"
        )
    print()
    print("* helpful = would-be-refused answers a user marked helpful (candidate FALSE refusals)")
    if report["sweep"] and report["sweep"][0]["n_answers"] == 0:
        print("\nNote: 0 answers in scope — empty result is expected on an empty/local DB.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only groundedness gate-impact canary (threshold sweep)."
    )
    parser.add_argument(
        "--thresholds",
        default=None,
        help="Comma-separated min_score values (default: 0.3,0.5,0.7).",
    )
    parser.add_argument("--since", default=None, help="ISO timestamp lower bound on created_at.")
    parser.add_argument("--company", default=None, help="Scope to one company_id (default: all).")
    parser.add_argument(
        "--feature-key", default="policy_assistant", help="feature_key filter."
    )
    parser.add_argument("--json", action="store_true", help="Emit the raw JSON report.")
    args = parser.parse_args(argv)

    if args.thresholds:
        thresholds = [float(x) for x in args.thresholds.split(",") if x.strip()]
    else:
        thresholds = list(DEFAULT_THRESHOLDS)

    report = run_sweep(
        thresholds=thresholds,
        since=args.since,
        company_id=args.company,
        feature_key=args.feature_key,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

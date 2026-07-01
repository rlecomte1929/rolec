"""
Assistant routing eval runner (policy-bridge quality).

Runs a (question → expected_domain) gold set through the REAL assistant domain
router and reports routing accuracy + per-domain precision/recall/F1 + ambiguous-
rate. The gold encodes the routing the bridge SHOULD produce, so this doubles as a
regression guard: any lexicon change that misroutes a question drops the score and
(with --gate) fails CI. Emits the `routing_accuracy` rag-eval dashboard metric.

Usage
─────
    python -m backend.eval.run_routing_eval \
        --gold backend/tests/fixtures/eval/routing/domain_gold.jsonl --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .routing_metrics import score_routing


def load_gold(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL gold file (one {question, expected_domain} per line)."""
    cases: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade assistant domain routing against a gold set.")
    parser.add_argument("--gold", type=Path, required=True, help="JSONL gold cases.")
    parser.add_argument("--min-accuracy", type=float, default=0.90,
                        help="Gate threshold (default 0.90).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if accuracy < --min-accuracy.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Dir to write routing_accuracy_<date>.json (rag-eval dashboard).")
    args = parser.parse_args(argv)

    report = score_routing(load_gold(args.gold))
    print(json.dumps(report, indent=2))

    if args.out:
        from .dashboard_report import write_dashboard_report
        dest = write_dashboard_report(args.out, "routing_accuracy", report["accuracy"], report)
        print(f"wrote {dest}", file=sys.stderr)

    if args.gate and report["accuracy"] < args.min_accuracy:
        misroutes = [k for k, v in report["confusion"].items()
                     if k.split("->")[0] != k.split("->")[1]]
        print(
            f"GATE FAILED: routing accuracy {report['accuracy']:.3f} < {args.min_accuracy}. "
            f"Misroutes: {misroutes}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

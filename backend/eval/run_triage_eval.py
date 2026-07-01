"""
Mission Control P3 — triage eval runner.

Runs a gold set of {title, body, expected_kind, expected_priority?} through the REAL
demand triage classifier and reports kind/priority accuracy + a confusion map. The
gold encodes the routing the triage SHOULD produce, so this doubles as a regression
guard: a lexicon change that misroutes a demand drops the score and (with --gate)
fails CI. Emits the `triage_accuracy` rag-eval dashboard metric.

    python -m backend.eval.run_triage_eval \
        --gold backend/tests/fixtures/eval/triage/triage_gold.jsonl --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .triage_metrics import score_triage


def load_gold(path: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade demand triage against a gold set.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--min-accuracy", type=float, default=0.85)
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--out", type=Path, default=None, help="Dir for triage_accuracy_<date>.json")
    args = parser.parse_args(argv)

    report = score_triage(load_gold(args.gold))
    print(json.dumps(report, indent=2))

    if args.out:
        from .dashboard_report import write_dashboard_report
        dest = write_dashboard_report(args.out, "triage_accuracy", report["kind_accuracy"], report)
        print(f"wrote {dest}", file=sys.stderr)

    if args.gate and report["kind_accuracy"] < args.min_accuracy:
        misroutes = [k for k, v in report["confusion"].items() if k.split("->")[0] != k.split("->")[1]]
        print(f"GATE FAILED: triage kind_accuracy {report['kind_accuracy']:.3f} < {args.min_accuracy}. "
              f"Misroutes: {misroutes}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

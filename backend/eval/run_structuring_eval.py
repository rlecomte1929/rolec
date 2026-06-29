"""
Structuring eval runner (Phase 2, gap #3).

Runs a corridor gold set of (fact, case_profile, expected_status) cases through the
REAL policy_applicability_engine and reports accuracy + applicable-class
precision/recall/F1 + per-axis accuracy. The gold encodes the engine's correct
structuring behaviour, so this doubles as a regression guard: any change that
mis-applies requirements for a profile drops the score and (with --gate) fails CI.

Usage
─────
    python -m backend.eval.run_structuring_eval \
        --gold backend/tests/fixtures/eval/structuring/in_de.jsonl --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .structuring_metrics import score_structuring


def load_gold(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL gold file (one case object per line; blank lines skipped)."""
    cases: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade requirement structuring for a corridor.")
    parser.add_argument("--gold", type=Path, required=True, help="JSONL gold cases.")
    parser.add_argument("--min-accuracy", type=float, default=1.0,
                        help="Gate threshold (default 1.0 — the gold encodes correct behaviour).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if accuracy < --min-accuracy.")
    args = parser.parse_args(argv)

    report = score_structuring(load_gold(args.gold))
    print(json.dumps(report, indent=2))

    if args.gate and report["accuracy"] < args.min_accuracy:
        print(
            f"GATE FAILED: structuring accuracy {report['accuracy']} < {args.min_accuracy}. "
            f"Misclassified: {[k for k, v in report['confusion'].items() if '->' in k and k.split('->')[0] != k.split('->')[1]]}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

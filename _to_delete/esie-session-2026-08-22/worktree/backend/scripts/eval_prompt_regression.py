#!/usr/bin/env python3
"""WS-E — prompt-regression CLI gate.

Runs :func:`backend.eval.prompt_regression.run_prompt_regression` (the composed
offline gates: WS-A refusal/PII + WS-C HR-policy context-precision + WS-C RAG
triad mock judge) and exits non-zero on any regression, so it is directly usable
as a pre-merge gate when a versioned prompt file changes.

Usage
-----
    python -m backend.scripts.eval_prompt_regression
    python -m backend.scripts.eval_prompt_regression --json
    python -m backend.scripts.eval_prompt_regression --threshold 0.6

Exit codes
----------
    0 — every composed offline gate passed.
    1 — at least one gate regressed (fails the build).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))  # backend/scripts -> repo root
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.prompt_regression import (  # noqa: E402
    CONTEXT_PRECISION_THRESHOLD,
    run_prompt_regression,
)


def _print_human(report: dict) -> None:
    fp = report["prompt_fingerprint"]
    lines = [
        "",
        "=== WS-E Prompt-Regression Gate ===",
        f"Prompt version: {fp['system_prompt_version']}  (sha256 {fp['sha256'][:12]})",
        f"Gates: {report['n_gates']}   Failed: {report['n_failed']}",
        "  gate                          pass",
    ]
    for g in report["gates"]:
        lines.append(f"  {g['name']:<28} {'OK' if g['passed'] else 'FAIL'}")
    lines.append(f"VERDICT: {'PASS' if report['all_passed'] else 'FAIL'}")
    lines.append("")
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WS-E prompt-regression gate.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=CONTEXT_PRECISION_THRESHOLD,
        help=(
            "HR-policy context-precision threshold for gating "
            f"(default {CONTEXT_PRECISION_THRESHOLD})."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of the human summary.",
    )
    args = parser.parse_args(argv)

    report = run_prompt_regression(context_precision_threshold=args.threshold)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

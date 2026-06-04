# AIQ-583 — run_eligibility_eval: batch evaluation of eligibility verdicts against ground truth.
"""
CLI: python -m eval.run_eligibility_eval --corpus tests/fixtures/pilot/ [--ci]

For each ground_truth.json found under the corpus directory:
  - Loads the eligibility_verdict block (outcome_set + citations).
  - Runs the predictor (default: mock.perfect, which echoes ground truth).
  - Checks:
      - predicted outcomes are a subset of ground-truth outcome_set
      - every cited rule is effective on the evaluation reference date (2026-07-01)
  - Emits a JSON report with: outcome_accuracy, citation_effective_ratio, n_has_citation.

Exit codes:
  0 — all gates pass (or --ci not set)
  1 — outcome_accuracy < 1.0 or citation_effective_ratio < 1.0 (only when --ci)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .rule_registry import is_effective

# Reference date for citation-effectiveness checks.
EVAL_DATE = date(2026, 7, 1)


# ---------------------------------------------------------------------------
# Predictor protocol
# ---------------------------------------------------------------------------

def _mock_perfect_predictor(ground_truth: Dict[str, Any]) -> Dict[str, Any]:
    """Echo the ground-truth eligibility_verdict unchanged."""
    return ground_truth.get("eligibility_verdict", {})


# ---------------------------------------------------------------------------
# Per-dossier evaluation
# ---------------------------------------------------------------------------

def _eval_one(
    ground_truth: Dict[str, Any],
    predictor: Callable[[Dict[str, Any]], Dict[str, Any]],
    eval_date: date = EVAL_DATE,
) -> Dict[str, Any]:
    """Evaluate a single dossier.  Returns per-dossier metrics dict."""
    gt_verdict = ground_truth.get("eligibility_verdict", {})
    gt_outcome_set: List[str] = gt_verdict.get("outcome_set", [])

    predicted: Dict[str, Any] = predictor(ground_truth)
    pred_outcomes: List[str] = predicted.get("outcome_set", [])
    pred_citations: List[str] = predicted.get("citations", [])

    # Outcome accuracy: 1.0 iff every predicted outcome is in the ground-truth set.
    if pred_outcomes:
        gt_set = set(gt_outcome_set)
        correct = sum(1 for o in pred_outcomes if o in gt_set)
        outcome_accuracy = correct / len(pred_outcomes)
    else:
        # No predictions — treat as 0 accuracy (nothing was predicted).
        outcome_accuracy = 0.0

    # Citation effectiveness.
    n_has_citation = 1 if pred_citations else 0
    if pred_citations:
        effective_count = sum(1 for c in pred_citations if is_effective(c, eval_date))
        citation_effective_ratio = effective_count / len(pred_citations)
    else:
        citation_effective_ratio = 1.0  # vacuously true — no citations to check

    return {
        "outcome_accuracy": outcome_accuracy,
        "citation_effective_ratio": citation_effective_ratio,
        "n_has_citation": n_has_citation,
    }


# ---------------------------------------------------------------------------
# Corpus runner
# ---------------------------------------------------------------------------

def run_eval(
    corpus_dir: str,
    predictor: Optional[Callable] = None,
    eval_date: date = EVAL_DATE,
) -> Dict[str, Any]:
    """Run eval over all ground_truth.json files under corpus_dir.

    Returns aggregate report dict.
    """
    if predictor is None:
        predictor = _mock_perfect_predictor

    corpus_path = Path(corpus_dir)
    ground_truth_files = sorted(corpus_path.rglob("ground_truth.json"))

    results = []
    for gt_file in ground_truth_files:
        with open(gt_file, "r") as fh:
            gt = json.load(fh)
        metrics = _eval_one(gt, predictor, eval_date)
        results.append(metrics)

    n = len(results)
    if n == 0:
        return {
            "n_dossiers": 0,
            "outcome_accuracy": 1.0,
            "citation_effective_ratio": 1.0,
            "n_has_citation": 0,
        }

    aggregate = {
        "n_dossiers": n,
        "outcome_accuracy": sum(r["outcome_accuracy"] for r in results) / n,
        "citation_effective_ratio": sum(r["citation_effective_ratio"] for r in results) / n,
        "n_has_citation": sum(r["n_has_citation"] for r in results),
    }
    return aggregate


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Run eligibility-verdict evaluation against a ground-truth corpus."
    )
    parser.add_argument("--corpus", required=True, help="Directory containing ground_truth.json files.")
    parser.add_argument("--ci", action="store_true", help="Exit 1 if any gate fails.")
    args = parser.parse_args()

    report = run_eval(args.corpus)
    print(json.dumps(report, indent=2))

    if args.ci:
        if report["outcome_accuracy"] < 1.0 or report["citation_effective_ratio"] < 1.0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())

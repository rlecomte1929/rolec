# AIQ-584 — run_contradiction_eval: batch evaluation of contradiction detectors against ground truth.
"""
CLI: python -m eval.run_contradiction_eval --corpus tests/fixtures/pilot/ [--ci]

For each ground_truth.json found under corpus:
  - Loads seeded_contradictions (list of contradiction objects).
  - Runs the predictor (default: mock.perfect, which echoes seeded_contradictions).
  - Matches predictions to ground truth using (dossier_id, type, field_key,
    affected_documents intersection non-empty) as the match key.
  - Computes recall, precision, fp_per_dossier.

Gates (--ci exits 1 if any fails):
  recall >= 0.90
  precision >= 0.85
  fp_per_dossier <= 1.0

Contradiction types: SURNAME_MISMATCH, DOB_MISMATCH, EMPLOYER_MISMATCH,
                     SALARY_MISMATCH, ADDRESS_MISMATCH.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

CONTRADICTION_TYPES = {
    "SURNAME_MISMATCH",
    "DOB_MISMATCH",
    "EMPLOYER_MISMATCH",
    "SALARY_MISMATCH",
    "ADDRESS_MISMATCH",
}

# Gates
RECALL_GATE = 0.90
PRECISION_GATE = 0.85
FP_PER_DOSSIER_GATE = 1.0


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _match_key(contradiction: Dict[str, Any]) -> tuple:
    """Canonical match key for a contradiction: (dossier_id, type, field_key)."""
    return (
        contradiction.get("dossier_id", ""),
        contradiction.get("type", ""),
        contradiction.get("field_key", ""),
    )


def _affected_docs_set(contradiction: Dict[str, Any]) -> set:
    return set(contradiction.get("affected_documents", []))


def _is_match(pred: Dict[str, Any], gt: Dict[str, Any]) -> bool:
    """True iff pred matches gt: same (dossier_id, type, field_key) AND
    affected_documents intersection is non-empty."""
    if _match_key(pred) != _match_key(gt):
        return False
    return bool(_affected_docs_set(pred) & _affected_docs_set(gt))


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

def _mock_perfect_predictor(ground_truth: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Echo the seeded_contradictions unchanged."""
    return list(ground_truth.get("seeded_contradictions", []))


# ---------------------------------------------------------------------------
# Per-dossier evaluation
# ---------------------------------------------------------------------------

def _eval_one_dossier(
    ground_truth: Dict[str, Any],
    predictor: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Evaluate a single dossier.  Returns per-dossier metrics."""
    gt_contradictions: List[Dict[str, Any]] = ground_truth.get("seeded_contradictions", [])
    predictions: List[Dict[str, Any]] = predictor(ground_truth)

    # For each ground-truth item, check if any prediction matches it (TP).
    tp_gt = 0
    for gt_item in gt_contradictions:
        if any(_is_match(pred, gt_item) for pred in predictions):
            tp_gt += 1

    # For each prediction, check if it matches any ground-truth item (TP from pred side).
    tp_pred = 0
    for pred in predictions:
        if any(_is_match(pred, gt_item) for gt_item in gt_contradictions):
            tp_pred += 1

    fp = len(predictions) - tp_pred

    return {
        "n_gt": len(gt_contradictions),
        "n_pred": len(predictions),
        "tp_gt": tp_gt,  # used for recall numerator
        "tp_pred": tp_pred,  # used for precision numerator
        "fp": fp,
    }


# ---------------------------------------------------------------------------
# Corpus runner
# ---------------------------------------------------------------------------

def run_eval(
    corpus_dir: str,
    predictor: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run contradiction eval over all ground_truth.json files under corpus_dir."""
    if predictor is None:
        predictor = _mock_perfect_predictor

    corpus_path = Path(corpus_dir)
    gt_files = sorted(corpus_path.rglob("ground_truth.json"))

    total_gt = 0
    total_tp_gt = 0
    total_tp_pred = 0
    total_pred = 0
    total_fp = 0
    n_dossiers = len(gt_files)

    for gt_file in gt_files:
        with open(gt_file, "r") as fh:
            gt = json.load(fh)
        metrics = _eval_one_dossier(gt, predictor)
        total_gt += metrics["n_gt"]
        total_pred += metrics["n_pred"]
        total_tp_gt += metrics["tp_gt"]
        total_tp_pred += metrics["tp_pred"]
        total_fp += metrics["fp"]

    recall = total_tp_gt / total_gt if total_gt > 0 else 0.0
    precision = total_tp_pred / total_pred if total_pred > 0 else 0.0
    fp_per_dossier = total_fp / n_dossiers if n_dossiers > 0 else 0.0

    return {
        "n_dossiers": n_dossiers,
        "recall": recall,
        "precision": precision,
        "fp_per_dossier": fp_per_dossier,
        "gates": {
            "recall_pass": recall >= RECALL_GATE,
            "precision_pass": precision >= PRECISION_GATE,
            "fp_per_dossier_pass": fp_per_dossier <= FP_PER_DOSSIER_GATE,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Run contradiction-detector evaluation against a ground-truth corpus."
    )
    parser.add_argument("--corpus", required=True, help="Directory containing ground_truth.json files.")
    parser.add_argument("--ci", action="store_true", help="Exit 1 if any gate fails.")
    args = parser.parse_args()

    report = run_eval(args.corpus)
    print(json.dumps(report, indent=2))

    if args.ci:
        gates = report["gates"]
        if not (gates["recall_pass"] and gates["precision_pass"] and gates["fp_per_dossier_pass"]):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())

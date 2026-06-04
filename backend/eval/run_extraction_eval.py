# AIQ-582 — CLI runner for document extraction evaluation against a corpus
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .extraction_metrics import (
    GATE_THRESHOLDS,
    AgentScore,
    aggregate_scores,
    bbox_iou,
    money_within_tolerance,
    normalize_value,
)

# Minimum IoU to count a bbox prediction as correct
BBOX_IOU_THRESHOLD = 0.5


def _load_ground_truth_files(corpus_dir: Path) -> List[Dict[str, Any]]:
    """Recursively find all ground_truth.json files under corpus_dir."""
    records = []
    for gt_path in sorted(corpus_dir.rglob("ground_truth.json")):
        with gt_path.open() as f:
            data = json.load(f)
        # Attach the source path for doc_type resolution
        data["_source_path"] = str(gt_path)
        records.append(data)
    return records


def _load_predictions(predictions_path: Path) -> Dict[str, Any]:
    """Load JSONL predictions file keyed by document_id."""
    predictions: Dict[str, Any] = {}
    with predictions_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            doc_id = obj.get("document_id")
            if doc_id:
                predictions[doc_id] = obj
    return predictions


def _mock_perfect_prediction(gt_record: Dict[str, Any]) -> Dict[str, Any]:
    """Echo the ground truth as the prediction (perfect predictor)."""
    return dict(gt_record)


def _score_record(
    gt: Dict[str, Any],
    pred: Dict[str, Any],
) -> AgentScore:
    """Score a single document's predicted fields against ground truth."""
    doc_type: str = gt.get("doc_type", "default")
    gt_fields: List[Dict[str, Any]] = gt.get("fields", [])
    pred_fields_by_name: Dict[str, Any] = {
        f["name"]: f for f in pred.get("fields", [])
    }

    n_fields = 0
    n_value_correct = 0
    n_bbox_correct = 0
    n_money_correct = 0

    for gt_field in gt_fields:
        n_fields += 1
        name = gt_field.get("name", "")
        gt_value = str(gt_field.get("value", ""))
        gt_bbox = gt_field.get("bbox")
        is_money = gt_field.get("is_money", False)

        pred_field = pred_fields_by_name.get(name, {})
        pred_value = str(pred_field.get("value", ""))
        pred_bbox = pred_field.get("bbox")

        # Value correctness
        if normalize_value(pred_value) == normalize_value(gt_value):
            n_value_correct += 1

        # Money correctness (separate counter)
        if is_money and money_within_tolerance(pred_value, gt_value):
            n_money_correct += 1

        # BBox correctness
        if gt_bbox and pred_bbox:
            iou = bbox_iou(pred_bbox, gt_bbox)
            if iou >= BBOX_IOU_THRESHOLD:
                n_bbox_correct += 1

    per_doc_type: Dict[str, Dict] = {
        doc_type: {
            "n_fields": n_fields,
            "n_value_correct": n_value_correct,
            "n_bbox_correct": n_bbox_correct,
            "n_money_correct": n_money_correct,
        }
    }

    return AgentScore(
        n_fields=n_fields,
        n_value_correct=n_value_correct,
        n_bbox_correct=n_bbox_correct,
        n_money_correct=n_money_correct,
        per_doc_type=per_doc_type,
    )


def run_eval(
    corpus_dir: Path,
    predictions_path: Optional[Path] = None,
) -> AgentScore:
    """Run extraction evaluation and return aggregate AgentScore."""
    gt_records = _load_ground_truth_files(corpus_dir)

    predictions: Optional[Dict[str, Any]] = None
    if predictions_path is not None:
        predictions = _load_predictions(predictions_path)

    scores: List[AgentScore] = []
    for gt in gt_records:
        doc_id = gt.get("document_id", gt["_source_path"])
        if predictions is not None:
            pred = predictions.get(doc_id, {})
        else:
            pred = _mock_perfect_prediction(gt)

        score = _score_record(gt, pred)
        scores.append(score)

    return aggregate_scores(scores)


def _build_report(score: AgentScore) -> Dict[str, Any]:
    per_type_summary = {}
    for doc_type, stats in score.per_doc_type.items():
        nf = stats["n_fields"]
        per_type_summary[doc_type] = {
            "n_fields": nf,
            "value_accuracy": stats["n_value_correct"] / nf if nf else 0.0,
            "bbox_accuracy": stats["n_bbox_correct"] / nf if nf else 0.0,
            "money_accuracy": stats["n_money_correct"] / nf if nf else 0.0,
            "gate_threshold": GATE_THRESHOLDS.get(doc_type, GATE_THRESHOLDS["default"]),
        }

    return {
        "total_fields": score.n_fields,
        "value_accuracy": score.value_accuracy,
        "bbox_accuracy": score.bbox_accuracy,
        "money_accuracy": score.money_accuracy,
        "per_doc_type": per_type_summary,
    }


def _check_gates(report: Dict[str, Any]) -> List[str]:
    """Return list of doc types that fail their gate threshold."""
    failures = []
    for doc_type, stats in report["per_doc_type"].items():
        threshold = stats["gate_threshold"]
        if stats["value_accuracy"] < threshold:
            failures.append(
                f"{doc_type}: value_accuracy={stats['value_accuracy']:.3f} < {threshold}"
            )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run document extraction evaluation against a corpus."
    )
    parser.add_argument(
        "--corpus",
        required=True,
        type=Path,
        help="Directory containing ground_truth.json files.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="JSONL file with predictions (default: mock.perfect).",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit with code 1 if any doc type is below its gate threshold.",
    )
    args = parser.parse_args()

    score = run_eval(args.corpus, args.predictions)
    report = _build_report(score)
    print(json.dumps(report, indent=2))

    if args.ci:
        failures = _check_gates(report)
        if failures:
            print("\nGATE FAILURES:", file=sys.stderr)
            for f in failures:
                print(f"  {f}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

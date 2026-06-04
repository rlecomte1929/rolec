# AIQ-582 — extraction evaluation metrics: normalize, money tolerance, bbox IoU, scoring
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List


def normalize_value(v: str) -> str:
    """Strip, lowercase, collapse interior whitespace."""
    return re.sub(r"\s+", " ", v.strip().lower())


def _parse_eur(s: str) -> float:
    """Parse a EUR amount string to a float.

    Handles:
      - leading/trailing whitespace
      - currency symbols: €, EUR (case-insensitive)
      - thousands separators: space, comma, period-as-thousands (when followed by 3 digits)
      - decimal separator: period or comma
    """
    s = s.strip()
    # Remove currency symbol/text
    s = re.sub(r"(?i)(eur|€)\s*", "", s).strip()

    # Detect European decimal format: ends with ,XX (1-2 digits) with . or space as thousands sep
    # e.g. "1.234,56" or "1 234,56" → 1234.56
    if re.search(r"[\. ]\d{3},\d{1,2}$", s):
        s = s.replace(".", "").replace(" ", "").replace(",", ".")
    # Detect comma as decimal: ends with ,XX not preceded by 3-digit group
    elif re.search(r",\d{1,2}$", s):
        s = s.replace(",", ".")
        s = s.replace(" ", "")
    else:
        # Remove comma/space used as thousands separator
        s = s.replace(",", "").replace(" ", "")

    return float(s)


def money_within_tolerance(predicted: str, ground_truth: str, pct: float = 0.01) -> bool:
    """Return True if predicted EUR amount is within pct of ground_truth."""
    try:
        pred_val = _parse_eur(predicted)
        gt_val = _parse_eur(ground_truth)
    except (ValueError, AttributeError):
        return False
    if gt_val == 0:
        return pred_val == 0
    return abs(pred_val - gt_val) / abs(gt_val) <= pct


def bbox_iou(pred: dict, gt: dict) -> float:
    """Compute IoU between two bounding boxes in {x0, y0, x1, y1} coordinates."""
    ix0 = max(pred["x0"], gt["x0"])
    iy0 = max(pred["y0"], gt["y0"])
    ix1 = min(pred["x1"], gt["x1"])
    iy1 = min(pred["y1"], gt["y1"])

    inter_w = max(0.0, ix1 - ix0)
    inter_h = max(0.0, iy1 - iy0)
    inter_area = inter_w * inter_h

    pred_area = max(0.0, pred["x1"] - pred["x0"]) * max(0.0, pred["y1"] - pred["y0"])
    gt_area = max(0.0, gt["x1"] - gt["x0"]) * max(0.0, gt["y1"] - gt["y0"])
    union_area = pred_area + gt_area - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


GATE_THRESHOLDS: Dict[str, float] = {
    "passport_td3_non_mrz": 0.92,
    "employment_contract_money": 0.85,
    "diploma": 0.80,
    "default": 0.75,
}


@dataclass
class AgentScore:
    n_fields: int = 0
    n_value_correct: int = 0
    n_bbox_correct: int = 0
    n_money_correct: int = 0
    per_doc_type: Dict[str, Dict] = field(default_factory=dict)

    @property
    def value_accuracy(self) -> float:
        return self.n_value_correct / self.n_fields if self.n_fields else 0.0

    @property
    def bbox_accuracy(self) -> float:
        return self.n_bbox_correct / self.n_fields if self.n_fields else 0.0

    @property
    def money_accuracy(self) -> float:
        return self.n_money_correct / self.n_fields if self.n_fields else 0.0


def aggregate_scores(scores: List[AgentScore]) -> AgentScore:
    """Sum raw counts across a list of AgentScore objects."""
    total = AgentScore()
    for s in scores:
        total.n_fields += s.n_fields
        total.n_value_correct += s.n_value_correct
        total.n_bbox_correct += s.n_bbox_correct
        total.n_money_correct += s.n_money_correct
        for doc_type, stats in s.per_doc_type.items():
            if doc_type not in total.per_doc_type:
                total.per_doc_type[doc_type] = dict(stats)
            else:
                for k, v in stats.items():
                    total.per_doc_type[doc_type][k] = total.per_doc_type[doc_type].get(k, 0) + v
    return total

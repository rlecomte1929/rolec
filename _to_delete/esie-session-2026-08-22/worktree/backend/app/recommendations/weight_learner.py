"""[P2] Offline learner for per-segment supplier-ranking weights.

Builds chosen-vs-shown training examples from logged recommendation slates
(``recommendation_slates``) joined to selection events (``supplier_selected`` /
``quote_accepted``), fits a logistic learn-to-rank over each scoring factor, and
emits a normalised per-factor weight map per ``(category, segment)`` cell.

This is a SCAFFOLD: it is data-blocked today (the platform is pre-launch with
fake data, so no real slate⋈selection volume exists). It therefore follows the
same discipline as ``case_duration_model`` / ``preference_dataset_builder`` —
**no-op below ``MIN_TRAINING_PAIRS`` and warn rather than fabricate**. Serving any
weights it produces is gated separately behind ``SUPPLIER_LEARNED_WEIGHTS`` (see
``weights.get_weights``); with that flag off, fitting weights changes nothing.

The pure functions here (``build_training_examples``, ``fit_weights_from_examples``,
``fit_cell``) take plain data and are unit-tested without a DB or the flag. The
CLI ``backend/scripts/fit_supplier_weights.py`` wires them to the store.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

log = logging.getLogger(__name__)

# Warn-don't-fabricate threshold. Mirrors case_duration_model.MIN_TRAINING_ROWS=50:
# below this many shown-item examples in a cell we refuse to fit and keep the
# static weights.
MIN_TRAINING_PAIRS = 50


@dataclass
class TrainingExample:
    """One shown supplier in one recommendation slate, with its per-factor score
    breakdown and whether the user ultimately chose it."""

    category: str
    segment: Optional[str]
    features: Dict[str, float]
    chosen: bool


def build_training_examples(
    slates: Iterable[Dict[str, Any]],
    selections: Iterable[Dict[str, Any]],
) -> List[TrainingExample]:
    """Join shown slates to chosen items into per-item examples.

    ``slates`` rows: ``{category, segment, case_id, items_json|items: [
        {item_id, breakdown: {factor: score}, ...}]}``.
    ``selections`` rows: ``{case_id, item_id}`` (from ``supplier_selected`` /
    ``quote_accepted`` events). An item is ``chosen`` when its ``item_id`` appears
    in a selection for the same ``case_id``. Items with no factor breakdown are
    skipped (nothing to learn from).
    """
    chosen_by_case: Dict[str, set] = defaultdict(set)
    for sel in selections:
        case_id = sel.get("case_id")
        item_id = sel.get("item_id")
        if case_id and item_id:
            chosen_by_case[str(case_id)].add(str(item_id))

    out: List[TrainingExample] = []
    for slate in slates:
        category = slate.get("category")
        if not category:
            continue
        segment = slate.get("segment")
        case_id = str(slate.get("case_id")) if slate.get("case_id") else None
        items = slate.get("items_json") or slate.get("items") or []
        chosen_ids = chosen_by_case.get(case_id, set()) if case_id else set()
        for item in items:
            breakdown = item.get("breakdown") or {}
            if not breakdown:
                continue
            try:
                feats = {str(k): float(v) for k, v in breakdown.items()}
            except (TypeError, ValueError):
                continue
            out.append(
                TrainingExample(
                    category=category,
                    segment=segment,
                    features=feats,
                    chosen=str(item.get("item_id")) in chosen_ids,
                )
            )
    return out


def fit_weights_from_examples(
    examples: List[TrainingExample], factors: List[str]
) -> Optional[Dict[str, float]]:
    """Fit a logistic LTR over ``factors`` and return normalised non-negative
    weights summing to 1, or ``None`` when unfittable.

    A factor whose coefficient is <= 0 (does not positively predict selection)
    gets weight 0; the remainder are renormalised to sum to 1, matching the
    convention that every static ``WEIGHTS[category]`` map sums to 1. Returns
    ``None`` when there is only one class (all chosen or none chosen) or the fit
    is degenerate — the caller then keeps the static weights.
    """
    labels = {e.chosen for e in examples}
    if len(labels) < 2:
        return None
    X = [[float(e.features.get(f, 0.0)) for f in factors] for e in examples]
    y = [1 if e.chosen else 0 for e in examples]
    try:
        from sklearn.linear_model import LogisticRegression

        clf = LogisticRegression(max_iter=1000)
        clf.fit(X, y)
    except Exception as exc:  # sklearn missing / convergence / single feature
        log.warning("logistic fit failed: %s", exc)
        return None

    coefs = list(clf.coef_[0])
    positive = [max(0.0, c) for c in coefs]
    total = sum(positive)
    if total <= 0:  # no factor positively predicts choice -> keep static
        return None
    return {f: round(p / total, 4) for f, p in zip(factors, positive)}


def fit_cell(
    examples: List[TrainingExample],
    factors: List[str],
    *,
    min_pairs: int = MIN_TRAINING_PAIRS,
) -> Tuple[Optional[Dict[str, float]], str]:
    """Fit one ``(category, segment)`` cell. Returns ``(weights|None, reason)``.

    No-op (``None``) below ``min_pairs`` or when the fit is degenerate — the
    reason string explains which, for the CLI's report.
    """
    n = len(examples)
    if n < min_pairs:
        return None, f"insufficient data: {n} < {min_pairs} examples"
    weights = fit_weights_from_examples(examples, factors)
    if weights is None:
        return None, f"unfittable on {n} examples (single class or no positive factor)"
    return weights, f"fit on {n} examples"


def group_by_cell(
    examples: List[TrainingExample],
) -> Dict[Tuple[str, Optional[str]], List[TrainingExample]]:
    """Bucket examples by ``(category, segment)`` for per-cell fitting."""
    cells: Dict[Tuple[str, Optional[str]], List[TrainingExample]] = defaultdict(list)
    for ex in examples:
        cells[(ex.category, ex.segment)].append(ex)
    return dict(cells)

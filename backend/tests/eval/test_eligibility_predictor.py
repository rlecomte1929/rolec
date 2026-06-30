"""
WS-B — tests for the real eligibility predictor + the seed eligibility corpus.

Covers:
  - the real predictor emits a non-empty outcome_set for every seed corridor;
  - the predictor reads only the profile (not the ground-truth verdict);
  - running run_eligibility_eval over the seed corpus with the REAL predictor is
    non-vacuous (n_dossiers == 5, outcomes actually predicted) and the --ci gate
    would pass (outcome_accuracy == 1.0, citation_effective_ratio == 1.0).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.eval.eligibility_predictor import predict_eligibility
from backend.eval.run_eligibility_eval import run_eval

_CORPUS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "eligibility"


def _corridors():
    return sorted(_CORPUS.glob("*/ground_truth.json"))


def test_corpus_present():
    assert len(_corridors()) == 5


@pytest.mark.parametrize("gt_path", _corridors(), ids=lambda p: p.parent.name)
def test_predictor_non_empty_outcome_per_corridor(gt_path):
    gt = json.loads(gt_path.read_text())
    pred = predict_eligibility(gt)
    assert pred["outcome_set"], f"empty outcome_set for {gt_path.parent.name}"
    # Predicted outcomes must be a subset of the held-out ground truth.
    gt_outcomes = set(gt["eligibility_verdict"]["outcome_set"])
    assert set(pred["outcome_set"]).issubset(gt_outcomes)


def test_predictor_ignores_ground_truth_verdict():
    """Mutating the GT verdict must not change the prediction (predictor reads profile only)."""
    gt = json.loads((_CORPUS / "in_de" / "ground_truth.json").read_text())
    baseline = predict_eligibility(gt)
    gt["eligibility_verdict"]["outcome_set"] = ["SOMETHING_ELSE"]
    gt["eligibility_verdict"]["citations"] = ["BOGUS_RULE:9999"]
    assert predict_eligibility(gt) == baseline


def test_eval_over_seed_corpus_is_non_vacuous_and_passes_gate():
    report = run_eval(str(_CORPUS), predictor=predict_eligibility)
    assert report["n_dossiers"] == 5
    # Gate conditions (mirror run_eligibility_eval._main --ci).
    assert report["outcome_accuracy"] == 1.0
    assert report["citation_effective_ratio"] == 1.0
    # Non-vacuous: at least some dossiers carry registry-backed citations.
    assert report["n_has_citation"] >= 1


def test_mock_predictor_still_default_for_back_compat():
    """run_eval with no predictor uses the mock (echo) — unchanged behaviour."""
    report = run_eval(str(_CORPUS))
    assert report["outcome_accuracy"] == 1.0
    assert report["n_dossiers"] == 5

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

from datetime import date

from backend.eval.eligibility_predictor import predict_eligibility
from backend.eval.rule_registry import is_effective
from backend.eval.run_eligibility_eval import EVAL_DATE, run_eval

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
    # All five corridors now carry registry-backed citations (US_FR + BR_PT
    # gained representative FR/PT rule cites).
    assert report["n_has_citation"] == 5


def test_new_fr_pt_rules_effective_on_eval_date():
    """The representative FR/PT rules are in force on the eval reference date."""
    assert is_effective("FR_CESEDA_L421:2024", EVAL_DATE) is True
    assert is_effective("PT_LEI_23_2007_ART88:2007", EVAL_DATE) is True
    # Sanity: both also effective on the literal eval date.
    assert is_effective("FR_CESEDA_L421:2024", date(2026, 7, 1)) is True
    assert is_effective("PT_LEI_23_2007_ART88:2007", date(2026, 7, 1)) is True


def test_every_corridor_has_at_least_one_effective_citation():
    """All 5 seed corridors emit ≥1 citation, each effective on the eval date."""
    for gt_path in _corridors():
        gt = json.loads(gt_path.read_text())
        pred = predict_eligibility(gt)
        cites = pred["citations"]
        assert cites, f"no citations for {gt_path.parent.name}"
        for c in cites:
            assert is_effective(c, EVAL_DATE), (
                f"{c} not effective on {EVAL_DATE} ({gt_path.parent.name})"
            )


def test_mock_predictor_still_default_for_back_compat():
    """run_eval with no predictor uses the mock (echo) — unchanged behaviour."""
    report = run_eval(str(_CORPUS))
    assert report["outcome_accuracy"] == 1.0
    assert report["n_dossiers"] == 5

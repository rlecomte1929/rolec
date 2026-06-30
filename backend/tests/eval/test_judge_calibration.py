# WS-C — unit tests for the grounding-judge calibration (deliverable 4).
from __future__ import annotations

import json

from backend.eval.run_judge_calibration import (
    DEFAULT_FIXTURES,
    cohen_kappa,
    mock_judge,
    run_eval,
)


def test_cohen_kappa_perfect_agreement():
    gold = ["grounded", "partially_grounded", "ungrounded"]
    assert cohen_kappa(gold, list(gold)) == 1.0


def test_cohen_kappa_handles_constant_predictions():
    # All predictions identical -> chance agreement undefined; we return 0.0.
    gold = ["grounded", "ungrounded", "partially_grounded"]
    pred = ["grounded", "grounded", "grounded"]
    assert cohen_kappa(gold, pred) == 0.0


def test_mock_judge_bands_coverage_to_verdict():
    # Fully covered answer -> grounded.
    assert mock_judge({"answer": "housing cap EUR 2500",
                       "chunks": [{"text": "the housing cap is EUR 2500 per month"}]}) == "grounded"
    # Off-topic answer -> ungrounded.
    assert mock_judge({"answer": "penguins migrate across antarctic glaciers",
                       "chunks": [{"text": "the housing cap is EUR 2500 per month"}]}) == "ungrounded"


def test_run_eval_reports_kappa_and_agreement_on_seed():
    report = run_eval(DEFAULT_FIXTURES, judge_name="mock")
    assert report["n_cases"] >= 25
    assert 0.0 <= report["agreement"] <= 1.0
    assert -1.0 <= report["cohen_kappa"] <= 1.0
    # The synthetic seed + mock judge are calibrated to agree well.
    assert report["cohen_kappa"] >= 0.6
    assert report["kappa_warning"] is False


def test_low_kappa_triggers_warning_but_does_not_exit(tmp_path):
    # Construct a fixture where the mock judge systematically disagrees.
    cases = [
        # gold says grounded but answer is off-topic -> judge says ungrounded
        {"id": f"d{i}", "gold": "grounded",
         "answer": "penguins glaciers antarctic migrate",
         "chunks": [{"text": "the housing cap is EUR 2500 per month"}]}
        for i in range(5)
    ]
    fixture = {"kappa_warn_below": 0.6, "cases": cases}
    p = tmp_path / "calib.json"
    p.write_text(json.dumps(fixture))
    report = run_eval(str(p), judge_name="mock")
    assert report["kappa_warning"] is True

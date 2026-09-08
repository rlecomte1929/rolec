"""Tests for the offline-eval aggregator (backend/eval/grader.py).

These also act as a CI gate: ``run_all_offline_gates`` runs the real refusal +
PII fixtures, so a regression that breaks either offline gate fails here (in
addition to the per-runner gate tests in backend/tests/test_*_eval.py).
"""
from backend.eval.grader import OFFLINE_GATES, run_all_offline_gates


def test_all_offline_gates_pass_on_current_fixtures():
    report = run_all_offline_gates()
    assert report["all_passed"] is True, report
    assert report["n_failed"] == 0
    assert report["n_gates"] == len(OFFLINE_GATES) == 2


def test_each_gate_is_normalised():
    report = run_all_offline_gates()
    names = {g["name"] for g in report["gates"]}
    assert names == {"refusal", "pii_leak"}
    for g in report["gates"]:
        assert g["module"] == "hr_policy"
        assert isinstance(g["passed"], bool)
        assert g["headline"]  # non-empty headline metrics
        assert isinstance(g["failing"], dict)
        assert g["cases"], "gate should expose per-case rows for error analysis"


def test_refusal_gate_exposes_recall_headline():
    report = run_all_offline_gates()
    refusal = next(g for g in report["gates"] if g["name"] == "refusal")
    assert "refusal_recall" in refusal["headline"]
    assert refusal["headline"]["refusal_recall"] >= refusal["headline"]["threshold"]


def test_pii_gate_reports_zero_leaks():
    report = run_all_offline_gates()
    pii = next(g for g in report["gates"] if g["name"] == "pii_leak")
    assert pii["headline"]["leak_count"] == 0
    assert pii["failing"]["leaks"] == []

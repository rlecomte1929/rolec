"""WS-E — tests for the prompt-regression gate.

Two things are proven here, exactly as the deliverable requires:
  (a) the gate PASSES on the current tree (committed prompts + fixtures), and
  (b) the gate CATCHES a regression — via an impossibly-high context-precision
      threshold AND via monkeypatching a composed scorer to fail — and the CLI
      exits non-zero in that case.
"""
from __future__ import annotations

from backend.eval import prompt_regression
from backend.scripts import eval_prompt_regression as cli


# ── (a) green on the current tree ─────────────────────────────────────────────


def test_gate_passes_on_current_tree():
    report = prompt_regression.run_prompt_regression()
    assert report["all_passed"] is True, report
    assert report["n_failed"] == 0
    names = {g["name"] for g in report["gates"]}
    assert names == {"offline_gates", "hr_policy_context_precision", "rag_triad"}


def test_report_carries_prompt_fingerprint():
    report = prompt_regression.run_prompt_regression()
    fp = report["prompt_fingerprint"]
    # The versioned system prompt is surfaced for provenance.
    assert fp["system_prompt_version"] != "unknown"
    assert len(fp["sha256"]) == 64
    assert any("policy_assistant_rag_engine.py" in f for f in fp["files"])


def test_cli_exits_zero_on_current_tree():
    assert cli.main([]) == 0


# ── (b) the gate catches a regression ─────────────────────────────────────────


def test_impossible_threshold_fails_the_gate():
    # A context-precision threshold above 1.0 can never be met → regression.
    report = prompt_regression.run_prompt_regression(context_precision_threshold=1.01)
    assert report["all_passed"] is False
    ctx = next(g for g in report["gates"] if g["name"] == "hr_policy_context_precision")
    assert ctx["passed"] is False


def test_cli_exits_nonzero_on_regression_threshold():
    assert cli.main(["--threshold", "1.01"]) == 1


def test_broken_scorer_is_caught(monkeypatch):
    # Simulate a prompt change that regresses the RAG-triad mock scorer: force the
    # triad runner to report a failing gate and assert the composite catches it.
    def _failing_run_eval(*_a, **_k):
        return {
            "judge": "mock",
            "n_cases": 0,
            "aggregates": {},
            "thresholds": {},
            "per_metric_pass": {},
            "gate_pass": False,
        }

    monkeypatch.setattr(prompt_regression.run_rag_triad, "run_eval", _failing_run_eval)
    report = prompt_regression.run_prompt_regression()
    assert report["all_passed"] is False
    triad = next(g for g in report["gates"] if g["name"] == "rag_triad")
    assert triad["passed"] is False
    assert cli.main([]) == 1

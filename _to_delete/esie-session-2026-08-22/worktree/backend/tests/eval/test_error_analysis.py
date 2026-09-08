"""Tests for backend/eval/error_analysis.py.

Covers the happy path (real gates, all green) and a synthetic failing report so
the confusion matrix + failure grouping are exercised without needing a broken
fixture.
"""
from backend.eval.error_analysis import (
    build_error_analysis,
    render_markdown,
)
from backend.eval.grader import run_all_offline_gates


def test_build_on_live_gates_is_all_green():
    analysis = build_error_analysis(run_all_offline_gates())
    assert analysis["all_passed"] is True
    assert analysis["total_failing_cases"] == 0
    # hr_policy module has both gates passing
    assert analysis["by_module"]["hr_policy"] == {"passed": 2, "failed": 0}


def _synthetic_failing_report():
    return {
        "all_passed": False,
        "n_gates": 1,
        "n_failed": 1,
        "gates": [
            {
                "name": "refusal",
                "module": "hr_policy",
                "passed": False,
                "headline": {"refusal_recall": 0.5, "threshold": 0.95},
                "failing": {"missed_refusals": ["c1", "c2"], "over_refusals": ["c3"]},
                "cases": [
                    {"case_id": "c1", "category": "jailbreak", "expected": "refuse", "actual": "answer", "passed": False},
                    {"case_id": "c2", "category": "jailbreak", "expected": "refuse", "actual": "answer", "passed": False},
                    {"case_id": "c3", "category": "policy", "expected": "answer", "actual": "refuse", "passed": False},
                    {"case_id": "c4", "category": "policy", "expected": "answer", "actual": "answer", "passed": True},
                ],
            }
        ],
    }


def test_build_on_failing_report_groups_failures():
    analysis = build_error_analysis(_synthetic_failing_report())
    assert analysis["all_passed"] is False
    assert analysis["total_failing_cases"] == 3  # 2 missed + 1 over
    gate = analysis["gates"][0]
    # failures-by-category counts only failing cases
    assert gate["failures_by_category"] == {"jailbreak": 2, "policy": 1}
    # confusion matrix: refuse->answer = 2, answer->refuse = 1, answer->answer = 1
    assert gate["confusion"]["refuse"]["answer"] == 2
    assert gate["confusion"]["answer"]["refuse"] == 1
    assert gate["confusion"]["answer"]["answer"] == 1


def test_render_markdown_is_nonempty_and_mentions_status():
    md_ok = render_markdown(build_error_analysis(run_all_offline_gates()), "2026-06-30T00:00:00+00:00")
    assert "all gates green" in md_ok
    md_fail = render_markdown(build_error_analysis(_synthetic_failing_report()), "2026-06-30T00:00:00+00:00")
    assert "failures present" in md_fail
    assert "confusion" in md_fail.lower()

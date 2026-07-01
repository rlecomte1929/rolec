# WS-C — unit tests for the RAG triad eval (deliverable 2).
from __future__ import annotations

from backend.eval.run_rag_triad import (
    DEFAULT_FIXTURES,
    METRICS,
    mock_judge,
    run_eval,
)


def test_mock_judge_emits_three_scores():
    case = {
        "query": "What is the housing cap?",
        "retrieved_chunks": [{"id": "h1", "text": "The housing cap is EUR 2,500 per month."}],
        "answer": "The housing cap is EUR 2,500 per month. [chunk:h1]",
    }
    scores = mock_judge(case)
    assert set(scores) == set(METRICS)
    for m in METRICS:
        assert 0.0 <= scores[m] <= 1.0


def test_grounded_answer_scores_higher_than_offtopic():
    chunks = [{"id": "c", "text": "The housing cap is EUR 2,500 per month."}]
    grounded = mock_judge({"query": "housing cap", "retrieved_chunks": chunks,
                           "answer": "The housing cap is EUR 2,500 per month."})
    offtopic = mock_judge({"query": "housing cap", "retrieved_chunks": chunks,
                          "answer": "Penguins migrate across the antarctic ice."})
    assert grounded["groundedness"] > offtopic["groundedness"]


def test_run_eval_on_seed_set_emits_aggregates_and_passes():
    report = run_eval(DEFAULT_FIXTURES, judge_name="mock")
    assert report["judge"] == "mock"
    assert report["n_cases"] >= 8
    assert set(report["aggregates"]) == set(METRICS)
    # The seed set + calibrated gate must pass.
    assert report["gate_pass"] is True
    for m in METRICS:
        assert report["aggregates"][m] >= report["thresholds"][m]


def test_gate_fails_when_threshold_unreachable(tmp_path):
    import json

    fixture = {
        "gate": {"context_relevance": 0.99, "groundedness": 0.99, "answer_relevance": 0.99},
        "cases": [
            {"id": "x", "query": "abc", "retrieved_chunks": [{"id": "z", "text": "totally unrelated text"}],
             "answer": "something else entirely"},
        ],
    }
    p = tmp_path / "triad.json"
    p.write_text(json.dumps(fixture))
    report = run_eval(str(p), judge_name="mock")
    assert report["gate_pass"] is False

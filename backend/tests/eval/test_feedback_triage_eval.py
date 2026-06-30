"""Tests for run_feedback_triage_eval — L2 feedback-triage accuracy eval.

TDD: these tests were written BEFORE the runner was implemented.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest

# Runner is imported here; tests will fail until the runner is implemented.
from backend.eval.run_feedback_triage_eval import run_eval, CI_AREA_ACCURACY_GATE

_FIXTURES = os.path.join(
    os.path.dirname(__file__),
    "..",
    "fixtures",
    "feedback_triage",
    "cases.jsonl",
)

SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def _make_fixture(cases: list[dict]) -> str:
    """Write cases to a temp .jsonl and return the path."""
    meta = {"_meta": True, "verification_status": "representative", "note": "test"}
    lines = [json.dumps(meta)] + [json.dumps(c) for c in cases]
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


_TINY_CASES = [
    {"id": "t1", "text": "button is broken", "category": "bug",
     "gold_severity": "high", "gold_area": "ui"},
    {"id": "t2", "text": "data leak between tenants", "category": "bug",
     "gold_severity": "critical", "gold_area": "isolation"},
    {"id": "t3", "text": "would like a dark mode", "category": "other",
     "gold_severity": "low", "gold_area": "feature"},
]


def _perfect_classifier(text: str, category: str | None) -> dict:
    """Returns exact gold labels hard-coded for _TINY_CASES."""
    mapping = {
        "button is broken": {"severity": "high", "area": "ui"},
        "data leak between tenants": {"severity": "critical", "area": "isolation"},
        "would like a dark mode": {"severity": "low", "area": "feature"},
    }
    return mapping.get(text, {"severity": "low", "area": "other"})


def _wrong_classifier(text: str, category: str | None) -> dict:
    """Always returns wrong labels."""
    return {"severity": "low", "area": "other"}


class TestRunEval:
    def test_perfect_classifier_scores_1(self):
        path = _make_fixture(_TINY_CASES)
        try:
            result = run_eval(path, _perfect_classifier)
        finally:
            os.unlink(path)
        assert result["severity_accuracy"] == 1.0
        assert result["area_accuracy"] == 1.0
        assert result["severity_within_1"] == 1.0
        assert result["total"] == 3
        assert result["mismatched_severity_ids"] == []
        assert result["mismatched_area_ids"] == []

    def test_wrong_classifier_scores_below_1(self):
        path = _make_fixture(_TINY_CASES)
        try:
            result = run_eval(path, _wrong_classifier)
        finally:
            os.unlink(path)
        assert result["severity_accuracy"] < 1.0
        assert result["area_accuracy"] < 1.0
        assert result["total"] == 3
        # all three mismatched on area
        assert len(result["mismatched_area_ids"]) == 3

    def test_meta_line_skipped(self):
        """_meta lines must not count as cases."""
        path = _make_fixture(_TINY_CASES)
        try:
            result = run_eval(path, _perfect_classifier)
        finally:
            os.unlink(path)
        assert result["total"] == 3  # meta line excluded

    def test_severity_within_1_tolerance(self):
        """gold=critical(3), pred=high(2) → |3-2|=1 → within_1 passes."""
        cases = [
            {"id": "w1", "text": "system down", "category": "bug",
             "gold_severity": "critical", "gold_area": "isolation"},
        ]

        def _off_by_one(text, category):
            return {"severity": "high", "area": "isolation"}

        path = _make_fixture(cases)
        try:
            result = run_eval(path, _off_by_one)
        finally:
            os.unlink(path)
        assert result["severity_accuracy"] == 0.0  # exact match fails
        assert result["severity_within_1"] == 1.0  # within-1 passes

    def test_severity_within_2_fails_within_1(self):
        """gold=critical(3), pred=low(0) → |3-0|=3 → within_1 also fails."""
        cases = [
            {"id": "w2", "text": "nothing", "category": "other",
             "gold_severity": "critical", "gold_area": "isolation"},
        ]

        def _way_off(text, category):
            return {"severity": "low", "area": "isolation"}

        path = _make_fixture(cases)
        try:
            result = run_eval(path, _way_off)
        finally:
            os.unlink(path)
        assert result["severity_accuracy"] == 0.0
        assert result["severity_within_1"] == 0.0

    def test_area_confusion_matrix(self):
        """area_confusion counts mis-predictions correctly."""
        cases = [
            {"id": "c1", "text": "t", "category": "bug",
             "gold_severity": "high", "gold_area": "ui"},
            {"id": "c2", "text": "t", "category": "bug",
             "gold_severity": "high", "gold_area": "ui"},
        ]

        def _predict_api(*_):
            return {"severity": "high", "area": "api"}

        path = _make_fixture(cases)
        try:
            result = run_eval(path, _predict_api)
        finally:
            os.unlink(path)
        # Both gold=ui predicted as api
        assert result["area_confusion"]["ui"]["api"] == 2


class TestCiGate:
    def test_ci_gate_passes_deterministic_on_committed_gold_set(self):
        """Deterministic classifier must meet the CI gate on the committed fixture."""
        from backend.app.services.feedback_triage import classify

        result = run_eval(_FIXTURES, classify)
        assert result["area_accuracy"] >= CI_AREA_ACCURACY_GATE, (
            f"Deterministic classifier area_accuracy {result['area_accuracy']:.4f} "
            f"is below CI gate {CI_AREA_ACCURACY_GATE}"
        )

    def test_gate_constant_is_reasonable(self):
        """CI_AREA_ACCURACY_GATE must be in (0, 1]."""
        assert 0 < CI_AREA_ACCURACY_GATE <= 1.0


class TestMockLlmPath:
    def test_mock_llm_runs_offline_without_network(self):
        """--mock path: classify_llm with fake client runs fully offline."""
        from backend.app.services.feedback_triage import classify_llm

        call_log: list[dict] = []

        def _fake_client(**kwargs: Any) -> dict:
            call_log.append(kwargs)
            return {"severity": "medium", "area": "other"}

        cases = [
            {"id": "m1", "text": "The button is broken", "category": "bug",
             "gold_severity": "high", "gold_area": "ui"},
        ]
        path = _make_fixture(cases)

        def _llm_via_mock(text, category):
            return classify_llm(text, category, client=_fake_client)

        try:
            result = run_eval(path, _llm_via_mock)
        finally:
            os.unlink(path)

        # The fake client was called (no network needed)
        assert len(call_log) == 1
        # Mock always returns medium/other — area wrong vs gold=ui
        assert result["area_accuracy"] == 0.0
        # severity medium vs gold high — exact match fails, within_1 passes (|2-1|=1)
        assert result["severity_accuracy"] == 0.0
        assert result["severity_within_1"] == 1.0

    def test_mock_llm_no_real_network_calls(self, monkeypatch):
        """Verify that the offline mock never imports llm_client (avoids API key need)."""
        import sys

        # Remove llm_client from sys.modules so a real import would fail
        monkeypatch.setitem(sys.modules, "backend.app.services.llm_client", None)  # type: ignore[arg-type]

        from backend.app.services.feedback_triage import classify_llm

        def _fake_client(**kwargs: Any) -> dict:
            return {"severity": "low", "area": "feature"}

        # Should not raise even though llm_client is blocked
        result = classify_llm("would like better support", "other", client=_fake_client)
        assert result["severity"] in {"low", "medium", "high", "critical"}
        assert result["area"] in {"ui", "api", "isolation", "feature", "other"}

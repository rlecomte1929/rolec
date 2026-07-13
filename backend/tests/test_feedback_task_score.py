"""test_feedback_task_score.py
==============================================
Unit tests for the feedback pipeline eval gate.

These are PURE UNIT tests — no LLM calls, no network, no Anthropic key needed.
They run in CI alongside the regular suite (-m "not integration").

Covers:
  - format_diagnostics: failingFrame inclusion
  - extract_confirmed_signals: signal extraction from client_context
  - score_task: all five scoring dimensions
"""
from __future__ import annotations

import json
import pytest

from backend.app.services.feedback_task_engineer import (
    extract_confirmed_signals,
    format_diagnostics,
    score_task,
)

# ── format_diagnostics ────────────────────────────────────────────────────────

class TestFormatDiagnostics:
    def test_empty_context_returns_empty_string(self):
        assert format_diagnostics(None) == ""
        assert format_diagnostics({}) == ""
        assert format_diagnostics("not-json") == ""

    def test_failing_frame_included_in_output(self):
        ctx = {
            "recentErrors": [{
                "message": "Cannot read 'data'",
                "failingFrame": "frontend/src/features/hr/pages/HrCasesPage.tsx:142:18",
                "fingerprint": "abc123",
            }]
        }
        out = format_diagnostics(ctx)
        assert "failingFrame=frontend/src/features/hr/pages/HrCasesPage.tsx:142:18" in out
        assert "Cannot read 'data'" in out

    def test_missing_failing_frame_omitted_gracefully(self):
        ctx = {
            "recentErrors": [{
                "message": "Some error",
                "fingerprint": "xyz",
                # no failingFrame key
            }]
        }
        out = format_diagnostics(ctx)
        assert "failingFrame" not in out
        assert "Some error" in out

    def test_failed_requests_included(self):
        ctx = {
            "recentFailedRequests": [
                {"status": 500, "path": "/api/hr/assign"},
                {"status": 404, "path": "/api/cases/99"},
            ]
        }
        out = format_diagnostics(ctx)
        assert "500 /api/hr/assign" in out
        assert "404 /api/cases/99" in out

    def test_json_string_input_parsed(self):
        ctx = json.dumps({
            "recentErrors": [{"message": "Err", "failingFrame": "frontend/src/X.tsx:1", "fingerprint": "f1"}]
        })
        out = format_diagnostics(ctx)
        assert "frontend/src/X.tsx:1" in out


# ── extract_confirmed_signals ─────────────────────────────────────────────────

class TestExtractConfirmedSignals:
    def test_empty_returns_no_signals(self):
        s = extract_confirmed_signals(None)
        assert s["failing_frame"] is None
        assert s["failed_api_paths"] == []
        assert s["has_error_evidence"] is False

    def test_failing_frame_strips_line_numbers(self):
        ctx = {
            "recentErrors": [{
                "failingFrame": "frontend/src/features/hr/pages/HrCasesPage.tsx:142:18"
            }]
        }
        s = extract_confirmed_signals(ctx)
        assert s["failing_frame"] == "frontend/src/features/hr/pages/HrCasesPage.tsx"
        assert s["has_error_evidence"] is True

    def test_failed_api_paths_extracted(self):
        ctx = {
            "recentFailedRequests": [
                {"status": 500, "path": "/api/hr/assign"},
                {"status": 200, "path": "/api/health"},   # 200 — should NOT be included
                {"status": 403, "path": "/api/admin/x"},
            ]
        }
        s = extract_confirmed_signals(ctx)
        assert "/api/hr/assign" in s["failed_api_paths"]
        assert "/api/health" not in s["failed_api_paths"]
        assert "/api/admin/x" in s["failed_api_paths"]

    def test_json_string_parsed(self):
        ctx = json.dumps({
            "recentErrors": [{"failingFrame": "backend/app/routers/cases.py:88"}]
        })
        s = extract_confirmed_signals(ctx)
        assert s["failing_frame"] == "backend/app/routers/cases.py"


# ── score_task ────────────────────────────────────────────────────────────────

def _task(**overrides):
    """Minimal valid task dict — all GAP detectors should pass by default."""
    base = {
        "title": "Fix assign endpoint 500",
        "strategic_objective": "Restore case assignment flow",
        "execution_prompt": (
            "Goal: fix 500 on POST /api/hr/assign.\n"
            "1. Open backend/app/routers/cases.py and locate the assign handler.\n"
            "2. Check for missing null guard on employee_id."
        ),
        "expected_output": "POST /api/hr/assign returns 200",
        "validation_criteria": "Clicking Assign Employee succeeds without error banner",
        "test_command": "cd backend && pytest tests/test_cases.py -k assign -v",
        "technical_constraints": "",
        "risk_rollback": "Revert the null guard if it breaks other callers",
        "files_to_touch": "backend/app/routers/cases.py",
        "priority": "P1",
        "complexity": "Low",
        "task_type": "Backend Implementation",
        "layer": "API",
        "product_area": "Core Product",
        "status": "Ready for AI",
        "autonomy_tier": "yellow",
    }
    base.update(overrides)
    return base


def _no_signals():
    return {"failing_frame": None, "failed_api_paths": [], "has_error_evidence": False}


def _signals(frame=None, paths=None):
    paths = paths or []
    return {
        "failing_frame": frame,
        "failed_api_paths": paths,
        "has_error_evidence": bool(frame or paths),
    }


class TestScoreTask:

    # ── D1: hallucinated paths ────────────────────────────────────────────────

    def test_hallucinated_src_pages_fails(self):
        task = _task(files_to_touch="src/pages/hr/Cases.tsx")
        result = score_task(task, confirmed_signals=_no_signals())
        assert not result["passed"]
        assert result["score"] <= 70
        assert any("hallucinated" in i.lower() for i in result["issues"])

    def test_real_repo_path_passes_d1(self):
        task = _task(files_to_touch="frontend/src/features/hr/pages/HrCasesPage.tsx")
        result = score_task(task, confirmed_signals=_no_signals())
        assert not any("hallucinated" in i.lower() for i in result["issues"])

    def test_recon_required_sentinel_passes_d1(self):
        task = _task(files_to_touch="RECON_REQUIRED")
        result = score_task(task, confirmed_signals=_no_signals())
        assert not any("hallucinated" in i.lower() for i in result["issues"])

    # ── D2: failingFrame not referenced ──────────────────────────────────────

    def test_failing_frame_not_referenced_is_issue(self):
        task = _task(
            files_to_touch="RECON_REQUIRED",
            execution_prompt="Fix something generic",
        )
        signals = _signals(frame="frontend/src/features/hr/pages/HrCasesPage.tsx")
        result = score_task(task, confirmed_signals=signals)
        assert any("confirmed failing file" in i.lower() for i in result["issues"])

    def test_failing_frame_referenced_by_basename_passes(self):
        task = _task(
            files_to_touch="frontend/src/features/hr/pages/HrCasesPage.tsx",
        )
        signals = _signals(frame="frontend/src/features/hr/pages/HrCasesPage.tsx")
        result = score_task(task, confirmed_signals=signals)
        assert not any("confirmed failing file" in i.lower() for i in result["issues"])

    def test_no_failing_frame_d2_skipped(self):
        task = _task(files_to_touch="RECON_REQUIRED")
        result = score_task(task, confirmed_signals=_no_signals())
        # D2 should not fire when there's no failingFrame
        assert not any("confirmed failing file" in i.lower() for i in result["issues"])

    # ── D4: question treated as executable task (GAP-9) ──────────────────────

    def test_question_with_impl_task_type_fails(self):
        task = _task(
            task_type="Frontend Implementation",
            status="Ready for AI",
        )
        result = score_task(
            task,
            confirmed_signals=_no_signals(),
            user_text="Do we actually need both Export buttons?",
        )
        assert not result["passed"]
        assert any("question" in i.lower() for i in result["issues"])

    def test_question_with_research_task_type_passes(self):
        task = _task(task_type="Research", status="Ready for AI")
        result = score_task(
            task,
            confirmed_signals=_no_signals(),
            user_text="Do we actually need both Export buttons?",
        )
        assert not any("question" in i.lower() for i in result["issues"])

    def test_statement_with_impl_task_type_passes_d4(self):
        task = _task(task_type="Backend Implementation", status="Ready for AI")
        result = score_task(
            task,
            confirmed_signals=_no_signals(),
            user_text="Clicking Assign Employee returns a 500 error banner.",
        )
        assert not any("question" in i.lower() for i in result["issues"])

    # ── combined: clean task scores 100 and passes ───────────────────────────

    def test_clean_task_passes_with_score_100(self):
        task = _task()
        result = score_task(task, confirmed_signals=_no_signals())
        assert result["passed"]
        assert result["score"] == 100
        assert result["issues"] == []

    # ── combined: hallucination + question both fire ──────────────────────────

    def test_multiple_issues_accumulate(self):
        task = _task(
            files_to_touch="src/pages/hr/Cases.tsx",   # D1
            task_type="Frontend Implementation",
            status="Ready for AI",
        )
        result = score_task(
            task,
            confirmed_signals=_no_signals(),
            user_text="Should we remove the duplicate button?",  # D4
        )
        assert not result["passed"]
        assert len(result["issues"]) >= 2
        assert result["score"] <= 30

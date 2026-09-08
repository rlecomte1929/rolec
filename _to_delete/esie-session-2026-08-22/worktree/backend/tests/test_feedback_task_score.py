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


# ── AIQ-1567 — the generator asserted unverified root causes as fact ──────────
#
# Four tasks in one day shipped false premises. In every case the reporter's words were
# accurate; what was false was what the generator added. These tests replay the two real
# reports and pin the mechanisms that produced them, so the failure cannot return
# silently. Each fixture below is the ACTUAL captured telemetry, not a sketch.

# BUG-260716-D23E → AIQ-1564. The reporter browsed 6 admin pages in ~43s, blew a shared
# 20/min rate-limit bucket, and every executive tile rendered "unavailable". The generator
# read the first 3 rows of the failed-request buffer as "the dashboard's endpoints" and
# asserted the dashboard was hammering them. All false: the page makes ONE call, never
# polls, and its real endpoint (/api/admin/exec-overview) is 4th in the buffer.
_D23E_CTX = {
    "route": "/admin/executive",
    "breadcrumbs": [
        {"message": "/admin/review-queue"}, {"message": "/admin"},
        {"message": "/admin/rag-quality"}, {"message": "/admin/executive"},
        {"message": "/admin"}, {"message": "/admin/executive"},
    ],
    "recentErrors": [{
        "message": "[swallowed] PlatformShellSidebar: admin notification poll: Too many requests.",
        "fingerprint": "1k525lk",
        "failingFrame": "",          # NB: no frame — nothing confirms a cause
    }],
    "recentFailedRequests": [
        {"status": 429, "path": "/api/admin/ops/sla/overview"},
        {"status": 429, "path": "/api/admin/assignments"},
        {"status": 429, "path": "/api/admin/rag-eval/metrics"},
        {"status": 429, "path": "/api/admin/exec-overview"},          # the real one
        {"status": 429, "path": "/api/admin/catalog/notification-counts"},
    ],
}

# BUG-260717-3D77 → AIQ-1566. Every complaint was about /admin/outreach; the reporter had
# left it 21s before pressing the feedback button. The generator took `route` at face
# value and aimed all three fixes at the wrong page.
_3D77_CTX = {
    "route": "/admin/test-drive",
    "breadcrumbs": [
        {"message": "/admin/outreach"},     # what the report is actually about
        {"message": "/admin/test-drive"},   # where the button was pressed
    ],
}


class TestAIQ1567FailedRequestBufferIsNotEvidence:
    def test_the_real_endpoint_is_no_longer_truncated_away(self):
        """AIQ-1564's endpoint sat 4th and the old [:3] slice dropped it silently."""
        out = format_diagnostics(_D23E_CTX)
        assert "/api/admin/exec-overview" in out, (
            "the page's own endpoint must survive the slice — cutting at 3 is precisely "
            "how the generator never saw it"
        )

    def test_the_buffer_is_labelled_a_lead_not_evidence(self):
        out = format_diagnostics(_D23E_CTX).lower()
        assert "unfiltered" in out and "lead" in out
        assert "session-wide" in out

    def test_a_truncated_buffer_says_so_rather_than_hiding_it(self):
        ctx = {"recentFailedRequests": [{"status": 500, "path": f"/api/x/{i}"} for i in range(9)]}
        out = format_diagnostics(ctx)
        assert "showing 5 of 9" in out, "a silent cut is what lost the real endpoint"

    def test_failed_paths_do_not_count_as_a_confirmed_cause(self):
        sig = extract_confirmed_signals(_D23E_CTX)
        assert sig["failed_api_paths"], "still surfaced as leads"
        assert sig["has_error_evidence"] is True, "something demonstrably failed"
        assert sig["has_confirmed_cause"] is False, (
            "a ring-buffer row is correlation; only a stack frame confirms a cause"
        )

    def test_a_stack_frame_does_confirm_a_cause(self):
        sig = extract_confirmed_signals({
            "recentErrors": [{"message": "boom", "failingFrame": "frontend/src/x/Y.tsx:1:2"}]
        })
        assert sig["has_confirmed_cause"] is True


class TestAIQ1567NavigationTrail:
    def test_breadcrumbs_reach_the_prompt(self):
        """Never read before — the single omission that produced AIQ-1566."""
        out = format_diagnostics(_3D77_CTX)
        assert "/admin/outreach" in out, (
            "without the trail there is no way to know the report is about the previous page"
        )

    def test_route_is_labelled_submit_time_not_subject(self):
        out = format_diagnostics(_3D77_CTX).lower()
        assert "/admin/test-drive" in out
        assert "not necessarily the page being described" in out


class TestAIQ1567D6AssertedCause:
    """D4 catches the question-shaped premise. AIQ-1564's report was a flat statement of
    symptom, so D4 never fired — D6 covers the gap."""

    def _task(self, **over):
        base = {
            "task_type": "Backend Implementation",
            "status": "Ready for AI",
            "priority": "P1",
            "strategic_objective": "Restore live data on /admin/executive.",
            "execution_prompt": "Investigate why the tiles render unavailable.",
            "files_to_touch": "RECON_REQUIRED",
        }
        base.update(over)
        return base

    def test_aiq_1564s_real_text_is_blocked(self):
        task = self._task(
            strategic_objective=(
                "Restore live data on the /admin/executive dashboard by eliminating "
                "rate-limit hammering on the three confirmed failing endpoints."
            ),
            execution_prompt=(
                "The dashboard (and possibly the sidebar notification poller) is making "
                "too-frequent concurrent requests."
            ),
        )
        result = score_task(
            task,
            confirmed_signals=extract_confirmed_signals(_D23E_CTX),
            user_text="most tiles are showing a status as 'unavailable'",   # not a question
        )
        assert not result["passed"], "an impl task built on an invented mechanism must not auto-dispatch"
        assert any("Root cause asserted without evidence" in i for i in result["issues"])

    def test_stating_the_symptom_is_fine(self):
        """The fix must not make every task vague — only cause-claims are penalised."""
        result = score_task(
            self._task(),
            confirmed_signals=extract_confirmed_signals(_D23E_CTX),
            user_text="most tiles are showing a status as 'unavailable'",
        )
        assert result["passed"], f"symptom-only task should pass: {result['issues']}"

    def test_a_confirmed_frame_licenses_a_cause(self):
        """With a stack trace we DO know where — asserting it is legitimate."""
        result = score_task(
            self._task(
                strategic_objective="The crash is caused by the null case in HrCasesPage.",
                execution_prompt="Fix frontend/src/features/hr/pages/HrCasesPage.tsx.",
            ),
            confirmed_signals=extract_confirmed_signals({
                "recentErrors": [{
                    "message": "Cannot read 'data'",
                    "failingFrame": "frontend/src/features/hr/pages/HrCasesPage.tsx:142:18",
                }]
            }),
            user_text="the HR cases page crashes",
        )
        assert result["passed"], f"evidence-backed cause must not be blocked: {result['issues']}"

    def test_research_type_is_not_penalised_for_a_theory(self):
        """Research is the safe lane the prompt already recommends — don't punish it."""
        result = score_task(
            self._task(
                task_type="Research",
                strategic_objective="Investigate whether the dashboard is hammering the API.",
            ),
            confirmed_signals=extract_confirmed_signals(_D23E_CTX),
            user_text="most tiles are showing a status as 'unavailable'",
        )
        assert result["passed"], f"Research may hypothesise: {result['issues']}"


class TestAIQ1567D3NoLongerRewardsTheBuffer:
    def test_omitting_an_unrelated_buffered_endpoint_is_not_an_issue(self):
        """D3 used to call these 'Confirmed' and nudge the model to weave them in."""
        result = score_task(
            {
                "task_type": "Research",
                "status": "Ready for AI",
                "priority": "P2",
                "strategic_objective": "Find out why the tiles show unavailable.",
                "execution_prompt": "Read the executive dashboard page and its endpoint.",
                "files_to_touch": "RECON_REQUIRED",
            },
            confirmed_signals=extract_confirmed_signals(_D23E_CTX),
            user_text="most tiles are showing a status as 'unavailable'",
        )
        assert result["passed"]
        assert not any("Confirmed failing API endpoint" in w for w in result["warnings"]), (
            "a session-wide buffer row is not a confirmed endpoint"
        )

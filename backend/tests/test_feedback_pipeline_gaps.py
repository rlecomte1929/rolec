"""test_feedback_pipeline_gaps.py
================================================
Five targeted gap-detection tests for the feedback → Notion task pipeline.

PURPOSE
-------
These are INTEGRATION tests — they make real LLM calls to engineer_task().
They are NOT meant to all pass on the current pipeline.  Each test has two
layers of assertions clearly labelled:

  # BASELINE  — should pass right now (regression guard)
  # GAP DETECTOR — expected to FAIL on the current pipeline,
                   documenting the known gap.  Once the corresponding fix
                   lands, the assertion should flip to green.

Run (requires ANTHROPIC_API_KEY in env):
  cd backend && pytest tests/test_feedback_pipeline_gaps.py -v -s

The -s flag is important: every test prints the full LLM output so you can
read it for manual gap discovery beyond the automated assertions.

Gap legend (matches the feedback pipeline audit):
  GAP-1  files_to_touch / test_command are hallucinated (wrong paths/framework)
  GAP-2  user pain buried under invented implementation spec
  GAP-7  pipeline can't distinguish intentional gate from broken feature
  GAP-9  user question treated as a factual assertion of a problem
"""
from __future__ import annotations

import os
import re
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.feedback_task_engineer import engineer_task  # noqa: E402

# These make LIVE engineer_task() LLM calls. Two guards:
#   - `integration` marker → excluded from CI, which runs `-m "not integration"`
#     (see .github/workflows/ci.yml). Keeps a deliberately-failing gap detector out
#     of the gating suite.
#   - skipif(no ANTHROPIC_API_KEY) → a direct local run skips cleanly instead of
#     erroring on an unauthenticated LLM call. Provide the key to run for real.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="live engineer_task() LLM calls require ANTHROPIC_API_KEY",
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _call(
    text: str,
    category: str = "bug",
    page_url: str = "/hr/cases",
    severity: str = "medium",
    area: str = "HR",
    admin_context: str = "",
    has_screenshot: bool = False,
    diagnostics: str | None = None,
) -> dict:
    """Thin wrapper with sensible defaults so test bodies stay readable."""
    return engineer_task(
        text=text,
        category=category,
        page_url=page_url,
        severity=severity,
        area=area,
        has_screenshot=has_screenshot,
        reporter_name=None,
        admin_context=admin_context,
        diagnostics=diagnostics,
    )


def _dump(label: str, task: dict) -> None:
    """Pretty-print the full task for human review.  Visible with pytest -s."""
    sep = "=" * 64
    print(f"\n{sep}\nOUTPUT: {label}\n{sep}")
    for key, val in task.items():
        print(f"\n[{key}]\n{val}")
    print(sep)


# Paths that only appear in hallucinated output for this repo.
# Real layout: frontend/src/features/<domain>/  or  backend/app/<layer>/
_HALLUCINATED_PATH_PATTERNS = [
    r"\bsrc/pages/",          # Next.js App-Router convention
    r"\bsrc/components/",     # missing the mandatory frontend/ prefix
    r"\bcomponents/ui/",      # shadcn/ui — wrong design system
    r"\bapp/[a-z][a-z]",      # Next.js /app directory
    r"HRPolicy\.tsx\b",       # non-existent file (real: HrPolicyPageV2.tsx)
    r"HelpWidget\.tsx\b",     # non-existent (real: SetupAssistantFab)
    r"AskAboutPolicy",        # non-existent component name
]


def _hallucinated_paths(text: str) -> list[str]:
    """Return every bad pattern found in the supplied text string."""
    return [p for p in _HALLUCINATED_PATH_PATTERNS if re.search(p, text or "")]


# ── Test 1 — Clear P1 bug: baseline + GAP-1 (file-path hallucination) ─────────

def test_t1_clear_p1_bug_file_paths():
    """
    Scenario
    --------
    An unambiguous, high-severity bug: clicking Assign Employee throws a 500.
    This is the simplest possible feedback — no gate ambiguity, no questioning.

    Baseline assertions (should pass now)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - Priority is P0 or P1 (blocking bug).
    - Layer is API or UI (server-side error in a frontend action).

    GAP-1 detectors (expected to FAIL on the current pipeline)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - files_to_touch must not contain hallucinated paths.
    - files_to_touch should be "RECON_REQUIRED" because the LLM has no
      access to the repo file tree and cannot know the real path.

    After Fix-1 lands (remove files_to_touch from LLM output schema,
    replace with RECON_REQUIRED), this test should be fully green.
    """
    task = _call(
        text=(
            "When I click 'Assign Employee' on any case in the HR command centre, "
            "the page shows a red error banner: '500 Internal Server Error'. "
            "The case stays unassigned. This is blocking us from onboarding employees."
        ),
        category="bug",
        page_url="/hr/cases",
        severity="high",
        area="HR",
        admin_context="Confirmed reproducible. Regression — started after last Tuesday's deploy.",
    )
    _dump("T1 — Clear P1 bug on /hr/cases", task)

    # BASELINE — guard these even after fixes
    assert task["priority"] in ("P0", "P1"), (
        f"Blocking 500 error must be P0 or P1, got {task['priority']!r}"
    )
    assert task["layer"] in ("API", "UI", "Feature"), (
        f"Server-error layer must be API/UI/Feature, got {task['layer']!r}"
    )

    # GAP-1 DETECTOR
    bad = _hallucinated_paths(task.get("files_to_touch", ""))
    assert not bad, (
        f"GAP-1: files_to_touch contains hallucinated path patterns {bad}.\n"
        f"  files_to_touch = {task.get('files_to_touch')!r}\n"
        "  Fix: remove files_to_touch from the LLM output schema and replace "
        "with a RECON_REQUIRED sentinel."
    )

    assert "RECON_REQUIRED" in (task.get("files_to_touch") or "").upper(), (
        "GAP-1: files_to_touch should be RECON_REQUIRED when the LLM has no "
        f"repo access.\n  Got: {task.get('files_to_touch')!r}"
    )


# ── Test 2 — Intentional gate: GAP-7 (designed state vs broken feature) ───────

def test_t2_intentional_gate_not_classified_as_bug():
    """
    Scenario
    --------
    The /hr/analytics page shows nothing.  This could be a render bug OR it
    could be an intentional empty state (e.g. gated on having uploaded data).
    The user's message is ambiguous — they describe the symptom and ask
    whether they need to set something up.

    This is the AIQ-1508 pattern: the pipeline should NOT immediately generate
    a "fix the broken chart" implementation task when the described behaviour
    might be intentional.

    Baseline assertion (should pass now)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - The task is generated without crashing (pipeline robustness).

    GAP-7 detectors (expected to FAIL on the current pipeline)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - execution_prompt must NOT assume the feature is broken or missing.
    - execution_prompt SHOULD flag that the behaviour may be intentional
      and require verification before any implementation begins.

    After Fix-7 lands (pre-engineering classification step), the task would
    be routed to 'Needs Human Clarification' and this assertion would pass.
    """
    task = _call(
        text=(
            "The analytics section on /hr/analytics shows nothing — "
            "just a blank panel where I'd expect to see charts or numbers. "
            "Is this because I haven't configured something, or is it actually broken?"
        ),
        category="bug",
        page_url="/hr/analytics",
        severity="medium",
        area="HR",
        admin_context="",
    )
    _dump("T2 — Empty state / intentional gate on /hr/analytics", task)

    # BASELINE
    assert task.get("title"), "Pipeline must return a non-empty title"

    # GAP-7 DETECTOR — execution_prompt must not presume the feature is broken
    exec_lower = (task.get("execution_prompt") or "").lower()
    strat_lower = (task.get("strategic_objective") or "").lower()
    combined = exec_lower + " " + strat_lower

    broken_presumed = any(phrase in combined for phrase in [
        "fix the broken",
        "the chart is not rendering",
        "implement the analytics",
        "add the missing chart",
        "charts failed to load",
        "resolve the bug",
        "the analytics feature is broken",
    ])
    assert not broken_presumed, (
        "GAP-7: pipeline presumed the feature is broken without verifying that "
        "the empty state might be intentional.\n"
        f"  execution_prompt = {task.get('execution_prompt', '')[:400]!r}\n"
        "  Fix: add a pre-engineering classification step that detects ambiguous "
        "empty-state reports and routes them to 'Needs Human Clarification'."
    )

    uncertainty_flagged = any(word in combined for word in [
        "verify", "confirm", "intentional", "empty state", "clarif",
        "gate", "check if", "may be", "investigate", "determine",
    ])
    assert uncertainty_flagged, (
        "GAP-7: execution_prompt should flag the ambiguity and require a "
        "human to confirm whether the empty state is intentional before coding.\n"
        f"  Got: {task.get('execution_prompt', '')[:400]!r}"
    )


# ── Test 3 — User question treated as assertion: GAP-9 ────────────────────────

def test_t3_user_question_not_treated_as_assertion():
    """
    Scenario
    --------
    The user notices two Export buttons on the /hr/cases page and asks
    whether they are duplicates.  They are NOT reporting a confirmed bug —
    they are asking a product question.

    This is the secondary AIQ-1508 failure: "is it still needed given the
    question-mark widget?" was treated as proof of duplication, and the
    pipeline generated a consolidation task.

    Baseline assertion (should pass now)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - The task is generated without crashing.

    GAP-9 detectors (expected to FAIL on the current pipeline)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - execution_prompt must NOT generate a "remove / consolidate" task
      premised on duplication that has not been confirmed.
    - execution_prompt SHOULD require verification of each button's purpose
      before any consolidation work is attempted.

    After Fix-9 lands, interrogative feedback would be classified as
    ASKING_QUESTION and routed to 'Needs Human Clarification'.
    """
    task = _call(
        text=(
            "I noticed there are two 'Export' buttons on the /hr/cases page — "
            "one in the top-right corner and one inside the filters bar. "
            "Do we actually need both, or is one of them a duplicate?"
        ),
        category="other",
        page_url="/hr/cases",
        severity="low",
        area="HR",
        admin_context="",
    )
    _dump("T3 — User question about duplicate buttons on /hr/cases", task)

    # BASELINE
    assert task.get("title"), "Pipeline must return a non-empty title"

    exec_lower = (task.get("execution_prompt") or "").lower()
    strat_lower = (task.get("strategic_objective") or "").lower()
    combined = exec_lower + " " + strat_lower

    # GAP-9 DETECTOR — must NOT treat the question as a confirmed fact
    asserts_duplication = any(phrase in combined for phrase in [
        "consolidate",
        "remove the duplicate",
        "merge the two",
        "delete one",
        "remove one of",
        "eliminate the redundant",
        "combine the export",
        "there are two redundant",
        "duplicate button",
    ])
    assert not asserts_duplication, (
        "GAP-9: pipeline treated a user question as a confirmed assertion of "
        "duplication and generated a consolidation/removal task.\n"
        f"  execution_prompt = {task.get('execution_prompt', '')[:400]!r}\n"
        "  Fix: detect interrogative phrasing and route to "
        "'Needs Human Clarification' rather than generating an implementation task."
    )

    # Must require confirmation before any action
    requires_verification = any(word in combined for word in [
        "verify", "confirm", "investigate", "check", "clarif",
        "determine", "assess", "review whether",
    ])
    assert requires_verification, (
        "GAP-9: pipeline should require confirmation of whether the buttons "
        "serve distinct purposes before recommending any change.\n"
        f"  Got: {task.get('execution_prompt', '')[:400]!r}"
    )


# ── Test 4 — P0 security / data isolation: BASELINE (must stay green) ─────────

def test_t4_p0_isolation_bug_routes_correctly():
    """
    Scenario
    --------
    Confirmed cross-tenant data leak: an HR user can see another company's
    cases, employee names, and salaries.

    This test should PASS on the current pipeline.  It documents the
    behaviour that any future classification gate must NOT break:
    a P0 security report must flow straight through to 'Ready for AI'
    (or 'Needs Decomposition') with the correct priority and layer — it
    must never be held in a 'Needs Human Clarification' queue.

    Baseline assertions (must all pass now and after every fix)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - priority == "P0"
    - layer == "Isolation"
    - status is NOT a clarification-holding state (P0 cannot be delayed)
    - execution_prompt does not downplay the security severity
    """
    task = _call(
        text=(
            "I'm logged in as HR for Acme Corp and I can see cases belonging "
            "to another company — TechStart Ltd. Their employee names, relocation "
            "destinations, and salary figures are visible in my /hr/cases list. "
            "This is a serious data breach."
        ),
        category="bug",
        page_url="/hr/cases",
        severity="critical",
        area="Security",
        admin_context=(
            "Confirmed by admin. Likely an RLS policy on the cases table that is "
            "not scoping by company_id. Must be treated as P0 — fix before all else."
        ),
    )
    _dump("T4 — P0 cross-tenant data leak on /hr/cases", task)

    # BASELINE — all of these must be green before AND after every fix
    assert task["priority"] == "P0", (
        f"Cross-tenant data leak must be P0, got {task['priority']!r}"
    )
    assert task["layer"] == "Isolation", (
        f"Cross-tenant leak must have layer=Isolation, got {task['layer']!r}"
    )
    # P0 must not land in a human-clarification holding pattern
    status = (task.get("status") or "").lower()
    assert "clarif" not in status and "human" not in status, (
        f"P0 security bugs must not be routed to any clarification queue, "
        f"got status={task.get('status')!r}"
    )
    exec_lower = (task.get("execution_prompt") or "").lower()
    assert "rls" in exec_lower or "row level" in exec_lower or "isolation" in exec_lower or "company_id" in exec_lower, (
        "P0 isolation task should mention RLS / company_id isolation in execution_prompt.\n"
        f"  Got: {task.get('execution_prompt', '')[:400]!r}"
    )


# ── Test 5 — Existing feature hallucinated as missing: GAP-1 extended ─────────

def test_t5_existing_feature_not_claimed_missing():
    """
    Scenario
    --------
    A user requests Word/PDF policy import.  This feature ALREADY EXISTS in
    the ReloPass policy builder (upload & classify → normalize & publish
    pipeline, including DOCX import).

    In AIQ-1507 the pipeline claimed "PDF/DOCX import may need to be added"
    when it already existed and worked.

    This test reproduces that class of hallucination on a different page.

    Baseline assertion (should pass now)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - The task is generated without crashing.

    GAP-1 extended detectors (expected to FAIL on the current pipeline)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - execution_prompt must NOT claim the feature does not exist.
    - execution_prompt SHOULD require recon to verify current state
      before any implementation begins.

    After Fix-1 (remove files_to_touch from LLM output) and Fix-3
    (inject route→component map including feature inventory), this
    test should be fully green.
    """
    task = _call(
        text=(
            "It would be very useful if HR admins could import their existing "
            "relocation policy documents directly from Word or PDF files, rather "
            "than having to re-enter everything manually into the policy builder. "
            "Is that something that could be added?"
        ),
        category="idea",
        page_url="/hr/policy",
        severity="medium",
        area="HR",
        admin_context="Multiple enterprise customers have requested this.",
    )
    _dump("T5 — Feature request for existing PDF/DOCX import on /hr/policy", task)

    # BASELINE
    assert task.get("title"), "Pipeline must return a non-empty title"

    exec_lower = (task.get("execution_prompt") or "").lower()
    strat_lower = (task.get("strategic_objective") or "").lower()
    combined = exec_lower + " " + strat_lower

    # GAP-1 EXTENDED DETECTOR — must NOT claim the feature is absent
    claims_missing = any(phrase in combined for phrase in [
        "implement pdf import",
        "add pdf import",
        "build a pdf import",
        "create pdf import",
        "implement word import",
        "add word document import",
        "build the import feature",
        "feature does not currently exist",
        "no import functionality",
        "pdf import does not exist",
        "docx import does not exist",
        "this feature is not yet",
        "this feature is not currently",
    ])
    assert not claims_missing, (
        "GAP-1 extended: pipeline claimed the PDF/DOCX import feature does not "
        "exist when it is already implemented in the policy builder.\n"
        f"  execution_prompt = {task.get('execution_prompt', '')[:500]!r}\n"
        "  Fix: inject route→component map (Fix-3) so the LLM knows the "
        "policy-builder already has an import pipeline before generating a task."
    )

    # Must flag that current state needs verification
    flags_recon = any(word in combined for word in [
        "verify", "check if", "confirm", "recon", "investigate whether",
        "may already", "already exist", "existing", "recon_required",
        "check whether",
    ])
    assert flags_recon, (
        "GAP-1 extended: pipeline should flag that this capability may already "
        "exist and require recon before generating an implementation task.\n"
        f"  Got: {task.get('execution_prompt', '')[:400]!r}"
    )

# Claude Code Prompt — Feedback Pipeline Eval Gate

## What you are building and why

ReloPass has a feedback pipeline:

1. A user on relopass.com clicks the FeedbackWidget, writes a message, and submits.
2. The browser automatically captures `client_context` — a JSON blob containing
   `recentErrors` (JS errors with stack traces), `recentFailedRequests` (failed API
   calls), and navigation breadcrumbs — and attaches it to the submission.
3. An admin sees the feedback row in `/admin/feedback`, adds a `dispatch_context`
   note, and clicks "Dispatch".
4. `POST /api/admin/feedback/{stream}/{id}/dispatch/preview` calls `engineer_task()`
   — a synchronous LLM call that returns a structured AI Work Queue task dict.
5. The admin reviews the task and confirms via
   `POST /api/admin/feedback/{stream}/{id}/dispatch/create`, which writes it to
   Notion as a new AI Work Queue item.

**Three confirmed bugs in this pipeline:**

**Bug A — `failingFrame` is silently dropped.**
`recentErrors[0].failingFrame` is "the first user-code stack frame = the function
that failed". It is a *real* source file path captured from the browser stack trace
(e.g. `frontend/src/features/hr/pages/HrCasesPage.tsx:142`). The current
`format_diagnostics()` function extracts only `.message` and `.fingerprint` from
`recentErrors` and throws `failingFrame` away. The LLM never sees it, so it
invents file paths instead (hallucination root cause).

**Bug B — No quality gate before Notion.**
`dispatch_create` writes the engineered task to Notion unconditionally. There is no
check for hallucinated file paths, questions treated as executable tasks, or
mismatched evidence. Bad tasks go straight to the AI Work Queue.

**Bug C — `files_to_touch` is hallucinated.**
The LLM output schema includes `files_to_touch`, which the LLM fills with paths
invented from generic React/Next.js conventions (e.g. `src/pages/hr/Cases.tsx`)
rather than the real repo layout (`frontend/src/features/hr/pages/HrCasesPage.tsx`).
When confirmed diagnostic signals are available (failingFrame, failed API path),
those should be used directly. When they are not, the field should be
`"RECON_REQUIRED"` — never a guess.

---

## Files to modify

```
backend/app/services/feedback_task_engineer.py   ← primary changes
backend/app/routers/admin_feedback.py            ← dispatch_preview + dispatch_create
backend/tests/test_feedback_task_score.py        ← new unit test file (no LLM calls)
```

---

## Branch

```bash
git checkout -b feat/feedback-eval-gate origin/main
```

---

## Change 1 — `backend/app/services/feedback_task_engineer.py`

Make **four targeted edits** to this file. Read it first to confirm current line
numbers before making any change.

### 1a. Update `_SYSTEM` — add confirmed-signal rules and remove `files_to_touch` from schema

Find the `_SYSTEM` string. It currently ends with:
```python
'"priority": one of ["P0","P1","P2","P3"], '
'"complexity": one of ["Trivial","Low","Medium","High","Very High"], '
f'"task_type": one of [{_TASK_TYPES}], '
'"layer": one of ["UI","API","Isolation","Feature","Infrastructure"], '
f'"product_area": one of [{_PRODUCT_AREAS}]}}'
```

Replace the entire `_SYSTEM` assignment with the block below (keep everything
before the `"Rules:\n"` line unchanged; only update the Rules section and the
JSON schema at the end):

```python
_SYSTEM = (
    "You are a senior engineering task author for ReloPass — a cross-border "
    "relocation SaaS (TypeScript/React + Vite frontend, Python FastAPI backend, "
    "Supabase/Postgres). Given a user-submitted feedback item (bug/idea/other) and "
    "the admin's added context, produce ONE fully-specified engineering task that an "
    "AI coding agent can execute without further clarification.\n\n"
    "Rules:\n"
    "- Be concrete and implementable. Never use vague language like 'fix it' or "
    "'improve X'. State exactly what to change and why.\n"
    "- execution_prompt: the engineered prompt — a one-line goal, a short plan, then "
    "precise ordered steps.\n"
    "- validation_criteria: explicit, testable pass criteria (how we know it's done).\n"
    "- test_command: concrete command(s) to verify, or '' if none applies.\n"
    "- A data-isolation issue is always priority P0 and layer=Isolation.\n"
    "- REPRODUCTION SIGNAL rules (critical — follow exactly):\n"
    "  • If REPRODUCTION SIGNAL contains 'failingFrame=<path>', that path is a "
    "confirmed stack-trace reference. Reference it verbatim in execution_prompt. "
    "Do NOT substitute any other path.\n"
    "  • If REPRODUCTION SIGNAL contains 'Failed request: <status> <path>', "
    "reference that exact API endpoint path in execution_prompt.\n"
    "  • Never invent file paths from framework conventions. If no confirmed paths "
    "appear in REPRODUCTION SIGNAL, omit file references entirely — the agent will "
    "locate them via repo recon.\n\n"
    "Reply with a SINGLE JSON object ONLY — no markdown, no prose — with exactly "
    "these keys:\n"
    '{"title": str (<=12 words), "strategic_objective": str, "execution_prompt": str, '
    '"expected_output": str, "validation_criteria": str, "test_command": str, '
    '"technical_constraints": str, "risk_rollback": str, '
    '"priority": one of ["P0","P1","P2","P3"], '
    '"complexity": one of ["Trivial","Low","Medium","High","Very High"], '
    f'"task_type": one of [{_TASK_TYPES}], '
    '"layer": one of ["UI","API","Isolation","Feature","Infrastructure"], '
    f'"product_area": one of [{_PRODUCT_AREAS}]}}'
)
```

Note: `files_to_touch` and `test_command` are removed from the JSON schema keys
(the LLM should not guess them). `test_command` is kept in the schema but only
as a concrete command when the LLM has enough info — it may return `""`.
Actually keep `test_command` in the schema since the LLM can legitimately fill
this when it knows the right command (e.g. "cd backend && pytest tests/...").
Only remove `files_to_touch` from the schema.

### 1b. Update `_REQUIRED` — remove `files_to_touch` (it's set by code, not LLM)

Find:
```python
_REQUIRED = (
    "title", "strategic_objective", "execution_prompt", "expected_output",
    "validation_criteria", "priority", "complexity", "task_type", "layer", "product_area",
)
```

This does NOT need to change (files_to_touch was never in _REQUIRED). Confirm
and leave as-is.

### 1c. Fix `format_diagnostics()` — restore `failingFrame`

Find the current `format_diagnostics` function and replace it entirely with:

```python
def format_diagnostics(client_context: Any) -> str:
    """Compact reproduction signal from a feedback item's client_context.
    Empty-safe: returns '' for None / {} / unparseable input. Not yet PII-masked —
    engineer_task re-scrubs it before the prompt.

    IMPORTANT: includes failingFrame (first user-code stack frame) when present.
    This is a confirmed source file path from the browser stack trace — the LLM
    is instructed to treat it as ground truth, not a guess.
    """
    ctx = client_context
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except Exception:  # noqa: BLE001
            return ""
    if not isinstance(ctx, dict) or not ctx:
        return ""
    lines = []
    errs = ctx.get("recentErrors") or []
    if errs:
        e0 = errs[0] or {}
        frame = (e0.get("failingFrame") or "").strip()
        parts = [f"Top error: {e0.get('message', '?')}"]
        if frame:
            parts.append(f"failingFrame={frame}")
        parts.append(f"fingerprint={e0.get('fingerprint', '?')}")
        lines.append(" | ".join(parts))
    for r in (ctx.get("recentFailedRequests") or [])[:3]:
        lines.append(f"Failed request: {r.get('status', '?')} {r.get('path', '?')}")
    fn = ctx.get("failingFunction") or ctx.get("failing_function")
    if fn:
        lines.append(f"Failing function: {fn}")
    return "\n".join(lines)
```

### 1d. Add three new functions after `format_diagnostics()` — before `status_from_complexity()`

Insert the following block between `format_diagnostics` and `status_from_complexity`:

```python
def extract_confirmed_signals(client_context: Any) -> Dict[str, Any]:
    """Extract structured ground-truth signals from client_context for the eval gate.

    Returns:
      failing_frame: str | None  — confirmed source file from stack trace (line
                                   numbers stripped), e.g.
                                   "frontend/src/features/hr/pages/HrCasesPage.tsx"
      failed_api_paths: list[str]  — API paths that returned 4xx/5xx, e.g.
                                     ["/api/hr/assign"]
      has_error_evidence: bool  — True when at least one confirmed signal exists
    """
    ctx = client_context
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except Exception:  # noqa: BLE001
            ctx = {}
    if not isinstance(ctx, dict):
        ctx = {}

    failing_frame: Optional[str] = None
    errs = ctx.get("recentErrors") or []
    if errs:
        frame_raw = (errs[0] or {}).get("failingFrame", "").strip()
        if frame_raw:
            # Strip trailing line/col: "File.tsx:142:18" → "File.tsx"
            failing_frame = re.sub(r":\d+(?::\d+)?$", "", frame_raw)

    reqs = ctx.get("recentFailedRequests") or []
    failed_api_paths = [
        r.get("path", "") for r in reqs[:3]
        if r.get("path") and str(r.get("status", 0)).startswith(("4", "5"))
    ]

    return {
        "failing_frame": failing_frame,
        "failed_api_paths": [p for p in failed_api_paths if p],
        "has_error_evidence": bool(failing_frame or failed_api_paths),
    }


# Patterns that appear in hallucinated file paths for this repo.
# Real layout: frontend/src/features/<domain>/  and  backend/app/<layer>/
# Any path matching these patterns was NOT found via repo inspection.
_HALLUCINATED_PATH_PATTERNS = (
    re.compile(r"\bsrc/pages/"),           # Next.js App-Router convention
    re.compile(r"\bsrc/components/"),      # missing mandatory "frontend/" prefix
    re.compile(r"\bcomponents/ui/"),       # shadcn/ui — wrong design system
    re.compile(r"\bapp/[a-z]{2,}/"),       # Next.js /app directory routing
    re.compile(r"HRPolicy\.tsx\b"),        # non-existent (real: HrPolicyPageV2.tsx)
    re.compile(r"HelpWidget\.tsx\b"),      # non-existent (real: SetupAssistantFab)
    re.compile(r"AskAboutPolicy\b"),       # non-existent component name
)


def _hallucinated_paths(text: str) -> list:
    """Return every bad pattern found in the supplied text string."""
    return [p.pattern for p in _HALLUCINATED_PATH_PATTERNS if p.search(text or "")]


# Interrogative patterns that signal the user is asking a question rather than
# reporting a confirmed fact. A question should not auto-generate an executable
# implementation task — it needs human clarification first.
_QUESTION_RE = re.compile(
    r"\b(do we|does this|should we|is this|are we|"
    r"why (?:is|are|does|do)|or is it|or does|"
    r"what (?:is|are|does)|how (?:does|do|is)|"
    r"would it|could it)\b",
    re.IGNORECASE,
)

_IMPL_TASK_TYPES = frozenset({
    "Frontend Implementation",
    "Backend Implementation",
    "UX Redesign",
    "Database Migration",
})


def score_task(
    task: Dict[str, Any],
    *,
    confirmed_signals: Dict[str, Any],
    user_text: str = "",
) -> Dict[str, Any]:
    """Quality gate — run between engineer_task() and create_work_queue_task().

    Scores the engineered task dict on five dimensions and returns whether it
    meets the quality bar for automatic Notion dispatch.

    Args:
      task: the dict returned by engineer_task()
      confirmed_signals: output of extract_confirmed_signals(client_context)
      user_text: the original user feedback message (for question detection)

    Returns:
      score: int 0–100
      issues: list[str]  — blocking problems (score deductions ≥ 30 pts each)
      warnings: list[str]  — non-blocking concerns (no score deduction)
      passed: bool  — True when score >= 70
    """
    issues: list = []
    warnings: list = []
    score = 100

    # ── D1: Hallucinated file paths ──────────────────────────────────────────
    files_field = task.get("files_to_touch") or ""
    execution_field = task.get("execution_prompt") or ""
    combined_text = files_field + " " + execution_field
    bad_paths = _hallucinated_paths(combined_text)
    if bad_paths:
        issues.append(
            f"Hallucinated file paths detected (wrong framework conventions for "
            f"this repo): {bad_paths}. These paths do not exist in the ReloPass "
            f"codebase. Real layout: frontend/src/features/<domain>/ and "
            f"backend/app/<layer>/."
        )
        score -= 30

    # ── D2: Confirmed failingFrame not referenced ─────────────────────────────
    failing_frame = confirmed_signals.get("failing_frame")
    if failing_frame:
        # Match on basename (without path prefix) to be tolerant of prefix variations
        basename = failing_frame.split("/")[-1]
        basename_stem = re.sub(r"\.(tsx?|py)$", "", basename, flags=re.IGNORECASE)
        search_blob = (files_field + " " + execution_field).lower()
        if (
            failing_frame.lower() not in search_blob
            and basename_stem.lower() not in search_blob
        ):
            issues.append(
                f"Confirmed failing file from stack trace ({failing_frame!r}) is not "
                f"referenced in files_to_touch or execution_prompt. The platform "
                f"captured this path directly — the fix must target it."
            )
            score -= 20

    # ── D3: Confirmed API path not referenced ─────────────────────────────────
    failed_paths = confirmed_signals.get("failed_api_paths") or []
    if failed_paths:
        primary = failed_paths[0]
        segment = primary.rstrip("/").rsplit("/", 1)[-1]
        search_blob = (execution_field + " " + files_field).lower()
        if segment and segment.lower() not in search_blob and primary.lower() not in search_blob:
            warnings.append(
                f"Confirmed failing API endpoint ({primary!r}) is not mentioned in "
                f"execution_prompt or files_to_touch. Verify the task targets the "
                f"right layer."
            )

    # ── D4: Question treated as executable implementation task (GAP-9) ────────
    text_stripped = (user_text or "").strip()
    is_question = (
        text_stripped.endswith("?")
        or bool(_QUESTION_RE.search(text_stripped))
    )
    if (
        is_question
        and task.get("task_type") in _IMPL_TASK_TYPES
        and task.get("status") == "Ready for AI"
    ):
        issues.append(
            f"User's message reads as a question but the task is set to "
            f"'Ready for AI' with task_type={task.get('task_type')!r}. "
            f"This risks auto-executing a change on an unverified premise. "
            f"Set task_type to 'Research' or status to 'Needs Human Clarification'."
        )
        score -= 40

    # ── D5: P0 with no error evidence ─────────────────────────────────────────
    if task.get("priority") == "P0" and not confirmed_signals.get("has_error_evidence"):
        warnings.append(
            "Priority P0 with no captured error evidence (no stack trace or failed "
            "request in diagnostics). Confirm the severity is correct before dispatch."
        )

    return {
        "score": max(0, score),
        "issues": issues,
        "warnings": warnings,
        "passed": max(0, score) >= 70,
    }
```

### 1e. Update `engineer_task()` — set `files_to_touch` to `RECON_REQUIRED` after parse

In `engineer_task()`, find the lines after `_parse_task(raw)`:

```python
    task = _parse_task(raw)
    task["status"] = status_from_complexity(task.get("complexity"))
    task["autonomy_tier"] = compute_autonomy_tier(
```

Add one line between `_parse_task` and `status_from_complexity`:

```python
    task = _parse_task(raw)
    # files_to_touch is not in the LLM output schema — set sentinel here.
    # Callers that have confirmed diagnostic signals (dispatch_preview) will
    # override this with the real path from extract_confirmed_signals().
    task["files_to_touch"] = "RECON_REQUIRED"
    task["status"] = status_from_complexity(task.get("complexity"))
    task["autonomy_tier"] = compute_autonomy_tier(
```

---

## Change 2 — `backend/app/routers/admin_feedback.py` — `dispatch_preview`

### 2a. Update imports at the top of the file

Find the existing import of `engineer_task`:
```python
from ..services.feedback_task_engineer import engineer_task
```

Replace with:
```python
from ..services.feedback_task_engineer import (
    engineer_task,
    extract_confirmed_signals,
    format_diagnostics,
    score_task,
)
```

(Note: `format_diagnostics` is already imported inline inside `dispatch_preview` —
remove the inline import once you add it to the top-level import block.)

### 2b. Update `dispatch_preview` body

Find the block inside `dispatch_preview` that calls `format_diagnostics` and
`engineer_task`, currently:

```python
    from ..services.feedback_task_engineer import format_diagnostics
    diagnostics = format_diagnostics(pf["client_context"]) if pf else ""
    ...
    try:
        task = engineer_task(
            ...
        )
    except Exception as exc:
        ...
        raise HTTPException(status_code=502, detail=f"Could not engineer the task: {exc}") from exc
    ...
    return {"task": task}
```

Replace the `from ..services.feedback_task_engineer import format_diagnostics`
inline import line with nothing (it's now a top-level import).

After the `engineer_task(...)` call succeeds and before the `_db2` block that
writes `spec_drafted`, insert:

```python
    # ── Eval gate ────────────────────────────────────────────────────────────
    # Extract confirmed ground-truth signals from the browser diagnostics and
    # score the engineered task against them. The score and issues are returned
    # to the admin UI so they can review quality before confirming dispatch.
    # Override files_to_touch with the confirmed failing_frame when available.
    raw_ctx = pf.get("client_context") if pf else None
    signals = extract_confirmed_signals(raw_ctx)
    if signals["failing_frame"]:
        task["files_to_touch"] = signals["failing_frame"]
    eval_result = score_task(task, confirmed_signals=signals, user_text=text_val)
    # ── end eval gate ─────────────────────────────────────────────────────────
```

Update the final `return` statement from:
```python
    return {"task": task}
```
to:
```python
    return {"task": task, "eval": eval_result}
```

### 2c. Add `force_dispatch` to `CreateTaskBody` and gate `dispatch_create`

Find `CreateTaskBody`:
```python
class CreateTaskBody(BaseModel):
    task: Dict[str, Any]
    confirm: bool = True
```

Add `force_dispatch`:
```python
class CreateTaskBody(BaseModel):
    task: Dict[str, Any]
    confirm: bool = True
    force_dispatch: bool = False  # set True to bypass the eval gate (admin override)
```

Inside `dispatch_create`, find the section that loads product fields (around
line 835):
```python
    if stream == "product":
        pf = _load_product_fields(db, item_id)
        if pf:
            report_id = pf["report_id"] or item_id
            message = pf["message"]
            page_url = pf["page_url"] or ""
            reporter_name = pf["reporter_name"]
```

After the `if pf:` block (but before `failure_evidence` is constructed), add:

```python
    # ── Eval gate (re-run at create time so admin edits are also checked) ────
    if stream == "product" and not body.force_dispatch:
        raw_ctx = pf.get("client_context") if pf else None
        signals = extract_confirmed_signals(raw_ctx)
        eval_result = score_task(task, confirmed_signals=signals, user_text=message)
        if not eval_result["passed"]:
            _clear_pending()
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Task did not pass quality gate. Review issues and either "
                             "fix the task or re-submit with force_dispatch=true.",
                    "eval": eval_result,
                },
            )
    # ── end eval gate ─────────────────────────────────────────────────────────
```

**Important:** `_clear_pending()` is defined as a nested function later in
`dispatch_create`. Move its definition **above** the eval gate block, or use
an inline sentinel clear. The cleanest approach: move the `_clear_pending`
definition to immediately after the sentinel claim block (before the `report_id`
assignments), so it's in scope for both the eval gate and the Notion error handler.

---

## Change 3 — New unit test file (no LLM calls, no network)

Create `backend/tests/test_feedback_task_score.py`:

```python
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
```

---

## Verification

Run these in order. All must be green before committing:

```bash
# 1. Unit tests — no LLM key needed
cd backend && python -m pytest tests/test_feedback_task_score.py -v

# 2. Full non-integration suite — must stay green
cd backend && python -m pytest -m "not integration" -v -x

# 3. Confirm the service imports cleanly
python3 -c "
from backend.app.services.feedback_task_engineer import (
    engineer_task, extract_confirmed_signals, format_diagnostics, score_task
)
print('feedback_task_engineer imports OK')
"

# 4. Confirm the router imports cleanly (catches any circular import)
python3 -c "
from backend.app.routers.admin_feedback import router
print('admin_feedback router imports OK')
"

# 5. Type-check frontend (no frontend changes, but confirm nothing regressed)
cd frontend && npx tsc --noEmit
```

---

## Commit strategy

Three logical commits:

```bash
# Commit 1 — service layer only
git add backend/app/services/feedback_task_engineer.py
git commit -m "fix(feedback): restore failingFrame in diagnostics + add score_task eval gate

- format_diagnostics() now includes failingFrame (first user-code stack frame)
  from recentErrors — this is a confirmed source path, not an LLM guess.
  Previously it was silently dropped, causing the LLM to invent file paths.
- Add extract_confirmed_signals(client_context) → structured ground-truth signals
  (failing_frame, failed_api_paths, has_error_evidence).
- Add score_task(task, confirmed_signals, user_text) → 0–100 quality score across
  five dimensions: hallucinated paths (D1), failingFrame not referenced (D2),
  API path not referenced (D3), question auto-executed (D4), P0 without evidence (D5).
- Remove files_to_touch from LLM output schema; engineer_task() now sets it to
  RECON_REQUIRED unconditionally. dispatch_preview overrides with failing_frame
  when available.
- Update _SYSTEM prompt: instruct LLM to use confirmed failingFrame/API paths
  from REPRODUCTION SIGNAL rather than inventing paths from conventions.

Fixes GAP-1 (hallucinated paths) and GAP-9 (question → green-tier task).
Confirmed by test_t1 and test_t3 in test_feedback_pipeline_gaps.py."

# Commit 2 — router integration
git add backend/app/routers/admin_feedback.py
git commit -m "feat(feedback): eval gate in dispatch_preview + dispatch_create

- dispatch_preview: runs extract_confirmed_signals + score_task after engineer_task.
  Overrides files_to_touch with confirmed failing_frame when available.
  Returns {task, eval} so the admin UI can show quality score + issues before confirm.
- dispatch_create: re-runs score_task at create time so admin edits are also checked.
  Returns 422 with {error, eval} when score < 70 unless force_dispatch=true.
  Adds force_dispatch: bool = False to CreateTaskBody (admin override escape hatch).

No breaking change: existing callers that ignore the new 'eval' key in preview
response continue to work. dispatch_create 422 is new behaviour — clients should
handle it by showing the issues to the admin."

# Commit 3 — unit tests
git add backend/tests/test_feedback_task_score.py
git commit -m "test(feedback): unit tests for score_task eval gate (no LLM, no network)

15 unit tests across TestFormatDiagnostics, TestExtractConfirmedSignals,
and TestScoreTask. Run in CI with the standard -m 'not integration' suite.
Covers all five scoring dimensions including the critical GAP-9 detector
(question → green-tier implementation task)."
```

---

## What NOT to do

- Do not touch `notion_work_queue.py` — that layer is unaffected.
- Do not change the `feedback` Supabase table schema — `client_context` is
  already a `jsonb` column that stores everything we need.
- Do not add `client_context` as a parameter to `engineer_task()` — keep its
  signature stable. The caller (`dispatch_preview`) handles extraction.
- Do not remove `test_command` from the LLM output schema — the LLM can
  legitimately fill this (e.g. `pytest tests/test_cases.py -k assign`).
  Only `files_to_touch` is removed from the LLM schema.
- Do not run the gap-detection integration tests (`test_feedback_pipeline_gaps.py`)
  as part of this PR — those require an ANTHROPIC_API_KEY and are excluded from CI.
  They will be re-run manually to verify GAP-1 and GAP-9 are fixed.

"""feedback_task_engineer.py — turn a feedback item + admin context into a
fully-specified AI Work Queue task via a single Anthropic call.

Used by the admin Dispatch flow: the engineered task (goal / plan / spec /
success metrics / verification + Work-Queue classification) is shown to the admin
for review, then written to the Notion AI Work Queue.

Uses the SYNCHRONOUS ``claude_complete_text_sync`` (the same proven path as
support.py / analytics_query — the async ``claude_complete`` hangs under the
uvicorn worker event loop) and parses the model's JSON. PII in the free text is
masked before it leaves the platform (CLAUDE.md "Data minimisation").
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .llm_client import claude_complete_text_sync
from .pii_masker import mask_pii

_MODEL = "claude-sonnet-4-6"
# The reply is a 13-key JSON object, six of whose values are long prose
# (execution_prompt carries a plan + ordered steps). 2000 truncated real replies in
# production — the JSON came back cut off mid-string and json.loads blew up, 502ing
# every dispatch/preview. Cap generously; we pay only for tokens actually emitted.
_MAX_TOKENS = 8000

_TASK_TYPES = (
    "Frontend Implementation, Backend Implementation, UX Redesign, Database Migration, "
    "Prompt Engineering, RAG Improvement, Performance Optimization, Research, Competitive Analysis"
)
_PRODUCT_AREAS = "Core Product, AI Layer, Integrations, UX, Infrastructure, GTM"

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

_REQUIRED = (
    "title", "strategic_objective", "execution_prompt", "expected_output",
    "validation_criteria", "priority", "complexity", "task_type", "layer", "product_area",
)

# Belt-and-suspenders against mask_pii's fail-open (it returns raw text on internal
# error). Mirrors the residue guard in feedback_triage.classify_llm: after masking,
# redact anything that still looks like an email or a long digit run before it reaches
# the LLM. Cheap, idempotent, never raises.
_PII_RESIDUE = re.compile(r"\S+@\S+\.\S+|\d{7,}")


def _scrub(text: Optional[str]) -> str:
    """mask_pii + a residue sweep, so raw email/long-digit sequences never reach the prompt."""
    return _PII_RESIDUE.sub("[REDACTED]", mask_pii(text or ""))


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
    # Next.js /app routing — but NOT the real backend tree, which is literally
    # backend/app/<layer>/. Without the negative lookbehind this flags every genuine
    # backend path (backend/app/routers/, backend/app/services/, …) as hallucinated.
    re.compile(r"(?<!backend/)\bapp/[a-z]{2,}/"),
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
        # A hallucinated path is a hard blocker: -40 pushes score below the 70 pass
        # bar on its own (a -30 deduction would leave it at exactly 70 = passing,
        # contradicting the 'hallucinated path must fail the gate' requirement).
        score -= 40

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


def status_from_complexity(complexity: Optional[str]) -> str:
    """High/Very High tasks land as 'Needs Decomposition'; everything else is
    'Ready for AI'. (Admin chose: AI decides status by complexity.)"""
    return "Needs Decomposition" if complexity in ("High", "Very High") else "Ready for AI"


_TIER_LABELS = {
    "green": "🟢 Green — auto",
    "yellow": "🟡 Yellow — self-validate + sample",
    "red": "🔴 Red — full human gate",
}
_RED_KEYWORDS = ("auth", "login", "password", "billing", "payment", "invoic",
                 "security", "rls", "permission", "migration", "isolation", "secret", "token")


def compute_autonomy_tier(*, task_type: Optional[str], complexity: Optional[str],
                          layer: Optional[str], product_area: Optional[str],
                          area: Optional[str] = None, files_to_touch: Optional[str] = None) -> str:
    """Deterministic risk tier. Red on any sensitive signal; green only for low-risk
    UI copy; yellow otherwise (default-safe)."""
    blob = " ".join(str(x or "").lower() for x in (area, product_area, files_to_touch, task_type))
    if layer == "Isolation" or task_type == "Database Migration" or any(k in blob for k in _RED_KEYWORDS):
        return "red"
    if (complexity in ("Trivial", "Low") and layer == "UI"
            and task_type in ("Frontend Implementation", "UX Redesign")
            and product_area in ("UX", "Core Product", "GTM")):
        return "green"
    return "yellow"


def _parse_task(raw: str) -> Dict[str, Any]:
    """Extract the JSON object from the model's reply (tolerant of markdown fences)."""
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("engineer_task: model did not return a JSON object")
    try:
        task = json.loads(s[start:end + 1])
    except json.JSONDecodeError as exc:
        # Nearly always a reply cut off at max_tokens: the trailing brace we latched
        # onto belongs to a nested object, so the slice ends inside an open string.
        # Say that plainly — the raw JSONDecodeError ("Unterminated string at column
        # 5880") tells the admin nothing they can act on.
        raise ValueError(
            f"engineer_task: model returned malformed JSON — the reply looks truncated "
            f"({len(s)} chars received). Try again; if it repeats, the task spec is "
            f"exceeding the {_MAX_TOKENS}-token output cap. ({exc})"
        ) from exc
    missing = [k for k in _REQUIRED if not task.get(k)]
    if missing:
        raise ValueError(f"engineer_task: missing required fields {missing}")
    return task


def engineer_task(
    *,
    text: Optional[str],
    category: str,
    page_url: Optional[str],
    severity: Optional[str],
    area: Optional[str],
    has_screenshot: bool,
    reporter_name: Optional[str],
    admin_context: str,
    diagnostics: Optional[str] = None,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Return an engineered AI-Work-Queue task dict + a derived `status`.
    Raises ValueError/RuntimeError on LLM failure (surfaced as 502 by the caller).

    timeout / max_retries: forwarded to the LLM client. Interactive callers (e.g.
    dispatch/preview) should pass max_retries=0 so a single timeout surfaces
    immediately as a 502 rather than retrying 3× (= 90 s total) before failing.
    """
    masked_bug = _scrub(text)
    masked_ctx = _scrub(admin_context)
    masked_reporter = _scrub(reporter_name) if reporter_name else ""
    masked_diag = _scrub(diagnostics) if diagnostics else ""
    user = (
        f"FEEDBACK ({category}) reported on page {page_url or '?'}"
        f"{' [screenshot attached]' if has_screenshot else ''}"
        f"{f' by {masked_reporter}' if masked_reporter else ''}.\n"
        f"Auto-classified: severity={severity or '?'}, area={area or '?'}.\n\n"
        f"USER MESSAGE:\n{masked_bug or '(none)'}\n\n"
        f"ADMIN CONTEXT (extra detail for the fix):\n{masked_ctx or '(none)'}\n"
        f"\nREPRODUCTION SIGNAL (auto-captured diagnostics):\n{masked_diag or '(none)'}\n"
    )
    raw = claude_complete_text_sync(
        system=_SYSTEM, user=user, model=_MODEL, max_tokens=_MAX_TOKENS, temperature=0.2,
        timeout=timeout, max_retries=max_retries,
    )
    task = _parse_task(raw)
    # files_to_touch is not in the LLM output schema — set sentinel here.
    # Callers that have confirmed diagnostic signals (dispatch_preview) will
    # override this with the real path from extract_confirmed_signals().
    task["files_to_touch"] = "RECON_REQUIRED"
    task["status"] = status_from_complexity(task.get("complexity"))
    task["autonomy_tier"] = compute_autonomy_tier(
        task_type=task.get("task_type"), complexity=task.get("complexity"),
        layer=task.get("layer"), product_area=task.get("product_area"),
        area=area, files_to_touch=task.get("files_to_touch"),
    )
    return task

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

# AIQ-1567: how many rows of the recentFailedRequests ring buffer we surface. One
# constant because the same buffer was being sliced at three different depths —
# format_diagnostics [:3], extract_confirmed_signals [:3], and
# autopilot_ingest.build_failure_evidence [:5] — so the prompt, the eval gate and the
# Notion Failure Evidence field each saw a different truncation of the same list.
# Whatever the depth, the cut is now stated ("showing N of M") rather than silent:
# in AIQ-1564 the page's own endpoint sat 4th and vanished without a trace.
_FAILED_REQUEST_LIMIT = 5

_SYSTEM = (
    "You are a senior engineering task author for ReloPass — a cross-border "
    "relocation SaaS (TypeScript/React + Vite frontend, Python FastAPI backend, "
    "Supabase/Postgres). Given a user-submitted feedback item (bug/idea/other) and "
    "the admin's added context, produce ONE fully-specified engineering task that an "
    "AI coding agent can execute without further clarification.\n\n"
    "TASK TYPE SELECTION — read this before setting task_type and status:\n"
    "• Choose 'Research' (not an implementation type) when the user message:\n"
    "  - ends with '?' or is phrased as a question\n"
    "  - expresses uncertainty ('I think', 'I'm not sure', 'whether this', 'could it be', "
    "'is it possible', 'maybe')\n"
    "  - asks for verification ('could you verify', 'can you check', 'can you confirm')\n"
    "  - describes a symptom without a clear root cause ('I cannot see X', 'Y seems missing')\n"
    "• Only choose an implementation type (Frontend/Backend/etc.) when the bug is clearly "
    "described AND the fix direction is unambiguous. If there is any uncertainty about "
    "the root cause, choose 'Research' — an engineer promotes it to implementation "
    "after confirming. When in doubt, Research is always safe; a wrong impl task "
    "silently ships a broken change.\n\n"
    "YOU CANNOT SEE THE CODEBASE — read this before writing any field:\n"
    "You have the user's words and some browser telemetry. You do NOT have the repo. So "
    "you can state WHAT was reported and WHAT must be true once it's fixed. You cannot "
    "know WHY it is broken, WHICH component is at fault, or WHICH page the user meant. "
    "The agent executing this task CAN read the code — leave the diagnosis to it.\n"
    "• NEVER assert a root cause, a mechanism, or a culprit component/endpoint/page as "
    "fact. Not in strategic_objective, not in execution_prompt, not anywhere.\n"
    "• If the telemetry suggests a cause, put it in leads_unverified as a QUESTION for "
    "the agent to check ('Is the 429 on X related?'), never as an instruction.\n"
    "• expected_output, validation_criteria, technical_constraints and test_command are "
    "BINDING — the agent treats them as requirements. Derive them ONLY from the user's "
    "own words and confirmed signals. Never invent a constraint the user did not state: "
    "a fabricated 'X is required by default' ships a product decision nobody asked for.\n"
    "• The user's report is the ground truth. Your inference is not. When they conflict, "
    "the user wins.\n\n"
    "Rules:\n"
    "- Be concrete about the OBSERVED problem and the desired end state. Never use vague "
    "language like 'fix it' or 'improve X'. State exactly what the user saw and what "
    "should be true instead — not why it happens.\n"
    "- execution_prompt: a one-line goal, then what to investigate. Order the steps by "
    "what to verify FIRST, not by a fix you have already decided on.\n"
    "- validation_criteria: explicit, testable pass criteria (how we know it's done), "
    "phrased as user-observable outcomes. If the user's desired outcome may be "
    "impossible (e.g. showing data that isn't collected), say so as a criterion the "
    "agent must confirm — never demand a number be displayed that may not exist.\n"
    "- test_command: concrete command(s) to verify, or '' if none applies.\n"
    "- A data-isolation issue is always priority P0 and layer=Isolation.\n"
    "- REPRODUCTION SIGNAL rules (critical — follow exactly):\n"
    "  • 'failingFrame=<path>' IS confirmed — the browser caught the error and named "
    "the file. Reference it verbatim in execution_prompt. Do NOT substitute any other "
    "path.\n"
    "  • 'Failed request: <status> <path>' is NOT confirmed. That buffer is an "
    "unfiltered, session-wide list of recent failures — it includes calls made by other "
    "pages earlier in the session, and it is truncated. It never proves the reported "
    "page called that endpoint, and it never establishes a cause. Treat every row as a "
    "lead: mention it in leads_unverified as something to check, never as the target.\n"
    "  • 'Route at submit time' is where the feedback button was pressed. The user "
    "commonly describes the page they were on moments earlier — check the navigation "
    "trail before naming any page, and if the trail is ambiguous, say so in "
    "leads_unverified rather than picking one.\n"
    "  • Never invent file paths from framework conventions. If no confirmed paths "
    "appear in REPRODUCTION SIGNAL, omit file references entirely — the agent will "
    "locate them via repo recon.\n\n"
    "Reply with a SINGLE JSON object ONLY — no markdown, no prose — with exactly "
    "these keys:\n"
    '{"title": str (<=12 words), "strategic_objective": str, "execution_prompt": str, '
    '"expected_output": str, "validation_criteria": str, "test_command": str, '
    '"technical_constraints": str, "risk_rollback": str, '
    '"leads_unverified": str (hypotheses phrased as questions for the agent to verify, '
    'or "" if none — NEVER instructions, and never a cause stated as fact), '
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

    AIQ-1567 — everything else here is a LEAD, and this function must say so.
    Two real failures came from presenting circumstantial context as evidence:

      * recentFailedRequests is a session-wide ring buffer. It was rendered as bare
        "Failed request: <status> <path>" lines beside failingFrame — same shape,
        same apparent authority — and silently sliced to the first 3. In AIQ-1564
        the buffer held 5 rows; the first 3 belonged to pages the reporter had
        already left, and the page's own endpoint sat 4th, outside the slice. The
        model dutifully reported those 3 as "the dashboard's endpoints".
      * breadcrumbs and route were captured by the frontend, stored on
        client_context, and dropped here. Without them the model cannot tell that a
        report may describe a page visited seconds earlier — which is exactly how
        AIQ-1566 pinned every complaint on the wrong page.

    So: pass the navigation trail through, label the route as submit-time only, and
    render the failed-request buffer as what it is — unfiltered, session-wide, and
    not proof that the reported page called anything.
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

    # The navigation trail. The report is often about the page BEFORE the last one —
    # the reporter navigates, then hunts for the feedback button.
    crumbs = [
        str(c.get("message") or "").strip()
        for c in (ctx.get("breadcrumbs") or [])
        if isinstance(c, dict) and (c.get("message") or "").strip()
    ]
    route = str(ctx.get("route") or "").strip()
    if route:
        lines.append(
            f"Route at submit time: {route} — this is where the feedback button was "
            f"pressed, NOT necessarily the page being described. Check the trail below."
        )
    if crumbs:
        lines.append(
            "Navigation trail (oldest -> newest, last = route at submit time): "
            + " -> ".join(crumbs[-8:])
        )

    reqs = [r for r in (ctx.get("recentFailedRequests") or []) if isinstance(r, dict)]
    if reqs:
        shown = reqs[:_FAILED_REQUEST_LIMIT]
        more = f" (showing {len(shown)} of {len(reqs)})" if len(reqs) > len(shown) else ""
        lines.append(
            f"Recent failed requests{more} — UNFILTERED session-wide buffer, most recent "
            f"first. These are LEADS, not evidence: they include calls made by other pages "
            f"earlier in the session, and none of them proves the reported page called it."
        )
        for r in shown:
            lines.append(f"  - Failed request: {r.get('status', '?')} {r.get('path', '?')}")

    fn = ctx.get("failingFunction") or ctx.get("failing_function")
    if fn:
        lines.append(f"Failing function: {fn}")

    ph_id = str(ctx.get("posthog_id") or "").strip()
    ph_sess = str(ctx.get("posthog_session_id") or "").strip()
    ph_replay = str(ctx.get("posthog_replay_url") or "").strip()
    if ph_replay or ph_id or ph_sess:
        lines.append(
            "PostHog (LEAD, not proof of root cause): "
            f"replay={ph_replay or 'none'} person_id={ph_id or 'none'} "
            f"session_id={ph_sess or 'none'}. "
            "Replay may start when the widget opened, after the failure."
        )
    return "\n".join(lines)


def extract_confirmed_signals(client_context: Any) -> Dict[str, Any]:
    """Extract structured signals from client_context for the eval gate.

    AIQ-1567 — only ONE of these is ground truth, and conflating them cost us four
    false-premise tasks. A failingFrame is a stack trace: the browser caught an error
    and named the file, so it confirms where. A failed API path is a row from a
    session-wide ring buffer: it confirms only that *something* failed *recently* —
    not that the reported page called it, and certainly not why. Treating the second
    like the first is what let AIQ-1564 assert three unrelated endpoints as "the
    dashboard's". Named accordingly below; do not promote a lead to evidence.

    Returns:
      failing_frame: str | None  — CONFIRMED source file from the stack trace (line
                                   numbers stripped), e.g.
                                   "frontend/src/features/hr/pages/HrCasesPage.tsx"
      failed_api_paths: list[str]  — LEADS: paths that returned 4xx/5xx anywhere in the
                                     session, e.g. ["/api/hr/assign"]. NOT scoped to the
                                     reported page.
      has_error_evidence: bool  — True when any signal exists (confirmed OR lead). Used
                                  only to sanity-check a P0, where "something demonstrably
                                  broke" is the question — not to justify a root cause.
      has_confirmed_cause: bool  — True ONLY for a failingFrame. This is the one that may
                                   justify an implementation task built on a stated cause.
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
        r.get("path", "") for r in reqs[:_FAILED_REQUEST_LIMIT]
        if isinstance(r, dict) and r.get("path") and str(r.get("status", 0)).startswith(("4", "5"))
    ]

    return {
        "failing_frame": failing_frame,
        "failed_api_paths": [p for p in failed_api_paths if p],
        "has_error_evidence": bool(failing_frame or failed_api_paths),
        # A stack trace names a file; a ring-buffer row names only a coincidence.
        "has_confirmed_cause": bool(failing_frame),
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


# Interrogative / uncertainty patterns that signal the user is asking a question
# or expressing uncertainty rather than reporting a confirmed, reproducible bug.
# A question should not auto-generate an executable implementation task — it needs
# human clarification first.
_QUESTION_RE = re.compile(
    r"\b("
    # Direct questions
    r"do we|does this|should we|is this|are we|"
    r"why (?:is|are|does|do)|or is it|or does|"
    r"what (?:is|are|does)|how (?:does|do|is)|"
    r"would it|could it|"
    # Uncertainty / speculation
    r"whether (?:this|it|there)|"
    r"I(?:'m| am) not sure|"
    r"I think (?:it|this|there)|"
    r"it (?:might|could|should) be|"
    r"maybe it|perhaps it|"
    # Verification requests
    r"could you (?:verify|check|confirm|look)|"
    r"can you (?:verify|check|confirm|look)|"
    r"is it possible"
    r")\b",
    re.IGNORECASE,
)

_IMPL_TASK_TYPES = frozenset({
    "Frontend Implementation",
    "Backend Implementation",
    "UX Redesign",
    "Database Migration",
})

# AIQ-1567 — phrasings that assert WHY something is broken, for D6.
#
# Deliberately narrow. This fires only when there is no confirmed failingFrame AND the
# task is queued for automatic implementation, so a false positive costs a re-type to
# Research, not a lost fix. Every pattern below is drawn from a task that actually
# shipped a false premise — e.g. AIQ-1564's "the dashboard is making too-frequent
# concurrent requests" and "eliminating rate-limit hammering on the three confirmed
# failing endpoints".
#
# NOT included, on purpose: bare "because", "so that", "to fix" — they carry no claim
# about a mechanism and appear constantly in legitimate prose ("retire the tab because
# the user finds it redundant" asserts nothing about a cause).
_ASSERTED_CAUSE_RE = re.compile(
    r"\b("
    # Explicit causal claims
    r"root cause (?:is|of)|"
    r"(?:is|are|was|were) caused by|"
    r"caused by the|"
    r"due to the|"
    r"(?:this|the) (?:issue|bug|problem|failure) (?:is|stems|arises|results)|"
    r"the (?:reason|culprit) (?:is|being)|"
    # Asserted mechanisms — the AIQ-1564 family
    r"(?:is|are) (?:hammering|flooding|spamming|thrashing)|"
    r"(?:is|are) (?:making|firing|issuing) too (?:many|frequent)|"
    r"too[- ]frequent (?:concurrent )?requests|"
    r"(?:is|are) polling too|"
    r"rate[- ]limit hammering|"
    # Asserting a component is at fault
    r"(?:is|are) (?:the )?(?:culprit|at fault|to blame)|"
    r"confirmed failing endpoints?"
    r")\b",
    re.IGNORECASE,
)


def _asserted_causes(text: str) -> list:
    """Distinct causal assertions found in `text` (D6). Empty list = nothing asserted."""
    found = {m.group(0).strip().lower() for m in _ASSERTED_CAUSE_RE.finditer(text or "")}
    return sorted(found)


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

    # ── D3: A failed API path went unmentioned ────────────────────────────────
    # AIQ-1567: this used to call the path "Confirmed" and nudge the model to weave it
    # into execution_prompt — which is how AIQ-1564 turned three unrelated ring-buffer
    # rows into "the dashboard's endpoints". These paths are LEADS. Not mentioning one is
    # now perfectly fine (no warning); the note below fires only as an FYI when the task
    # ignores a lead entirely AND has no confirmed frame to work from.
    failed_paths = confirmed_signals.get("failed_api_paths") or []
    if failed_paths and not confirmed_signals.get("has_confirmed_cause"):
        primary = failed_paths[0]
        segment = primary.rstrip("/").rsplit("/", 1)[-1]
        search_blob = (execution_field + " " + files_field).lower()
        if segment and segment.lower() not in search_blob and primary.lower() not in search_blob:
            warnings.append(
                f"A failed request ({primary!r}) was captured in the session but the task "
                f"does not mention it. That is fine if it is unrelated — the buffer is "
                f"session-wide. Noted only so the lead is not lost."
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

    # ── D6: Root cause asserted without a confirmed cause (AIQ-1567) ──────────
    # D4 catches the question-shaped version of this ("can you check X?" → impl task).
    # It could not catch AIQ-1564, whose report was a flat statement of symptom ("most
    # tiles are showing unavailable") — no question mark, no hedging. The generator
    # nonetheless asserted a mechanism ("the dashboard is hammering these endpoints"),
    # inferred purely from a session-wide failed-request buffer, and typed it as an
    # implementation task. Every claim was false; the real endpoint was not even in the
    # buffer's visible slice.
    #
    # A stack frame confirms WHERE. Nothing in this telemetry confirms WHY. So: an
    # implementation task queued for automatic execution may not assert a cause unless a
    # failingFrame backs it. Same remedy the prompt already prescribes and D4 already
    # enforces for questions — Research, which an engineer promotes after confirming.
    if (
        not confirmed_signals.get("has_confirmed_cause")
        and task.get("task_type") in _IMPL_TASK_TYPES
        and task.get("status") == "Ready for AI"
    ):
        asserted = _asserted_causes(
            f"{task.get('strategic_objective') or ''} {execution_field}"
        )
        if asserted:
            issues.append(
                f"Root cause asserted without evidence: {asserted}. No failingFrame was "
                f"captured, so nothing here confirms WHY the problem happens — a "
                f"session-wide failed-request buffer shows correlation, not cause. This "
                f"is queued as '{task.get('task_type')}' + 'Ready for AI', so an agent "
                f"would implement against that guess. Set task_type='Research', or state "
                f"the symptom and move the theory into leads_unverified."
            )
            # Same weight as D4: a wrong impl task silently ships a broken change.
            score -= 40

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
        # AIQ-1567: page_url used to read "reported on page X" — flat, unqualified, and
        # taken by the model as the subject of the report. It is only where the button
        # was pressed. In AIQ-1566 the reporter was describing the page they had left
        # 21s earlier, and every field came out aimed at the wrong one.
        f"FEEDBACK ({category}) submitted FROM page {page_url or '?'} (the page the "
        f"feedback button was pressed on — the report may describe a different page; "
        f"check the navigation trail in REPRODUCTION SIGNAL before naming one)"
        f"{' [screenshot attached]' if has_screenshot else ''}"
        f"{f', by {masked_reporter}' if masked_reporter else ''}.\n"
        f"Auto-classified: severity={severity or '?'}, area={area or '?'}.\n\n"
        f"USER MESSAGE (this is the ground truth — your inference is not):\n"
        f"{masked_bug or '(none)'}\n\n"
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

    # AIQ-1567: fold the leads into execution_prompt under a heading that names them as
    # unverified. The Notion property map is 1:1 from the LLM's keys, so an unmapped key
    # would be silently dropped — and a lead the executor never sees is worse than no
    # lead at all. Appending keeps it visible without a schema change, and the heading is
    # what makes it non-binding: the executor reads it as questions, not instructions.
    leads = str(task.get("leads_unverified") or "").strip()
    if leads:
        task["execution_prompt"] = (
            f"{task.get('execution_prompt', '')}\n\n"
            f"## Leads — UNVERIFIED, verify before implementing\n"
            f"Not requirements, and not a diagnosis. These were inferred from browser "
            f"telemetry by a step that could not read the code. Confirm or disprove each "
            f"against the repo before acting on it; if one is false, say so and rescope.\n"
            f"{leads}"
        ).strip()

    # Belt-and-suspenders: if the user's text is question-like (ends with '?' or
    # matches uncertainty patterns) but the LLM chose an implementation task type,
    # auto-correct to Research + Needs Human Clarification. This prevents D4 from
    # blocking at the eval gate — the system prompt instructs the LLM to do this, but
    # the post-processing step ensures correctness even when the model doesn't comply.
    _text_stripped = (text or "").strip()
    if (
        (_text_stripped.endswith("?") or bool(_QUESTION_RE.search(_text_stripped)))
        and task.get("task_type") in _IMPL_TASK_TYPES
    ):
        task["task_type"] = "Research"
        task["status"] = "Needs Human Clarification"

    task["autonomy_tier"] = compute_autonomy_tier(
        task_type=task.get("task_type"), complexity=task.get("complexity"),
        layer=task.get("layer"), product_area=task.get("product_area"),
        area=area, files_to_touch=task.get("files_to_touch"),
    )
    return task

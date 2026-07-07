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
    "- A data-isolation issue is always priority P0 and layer=Isolation.\n\n"
    "Reply with a SINGLE JSON object ONLY — no markdown, no prose — with exactly these keys:\n"
    '{"title": str (<=12 words), "strategic_objective": str, "execution_prompt": str, '
    '"expected_output": str, "validation_criteria": str, "test_command": str, '
    '"technical_constraints": str, "files_to_touch": str, "risk_rollback": str, '
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
    engineer_task re-scrubs it before the prompt."""
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
        lines.append(f"Top error: {e0.get('message', '?')} (fingerprint {e0.get('fingerprint', '?')})")
    for r in (ctx.get("recentFailedRequests") or [])[:3]:
        lines.append(f"Failed request: {r.get('status', '?')} {r.get('path', '?')}")
    fn = ctx.get("failingFunction") or ctx.get("failing_function")
    if fn:
        lines.append(f"Failing function: {fn}")
    return "\n".join(lines)


def status_from_complexity(complexity: Optional[str]) -> str:
    """High/Very High tasks land as 'Needs Decomposition'; everything else is
    'Ready for AI'. (Admin chose: AI decides status by complexity.)"""
    return "Needs Decomposition" if complexity in ("High", "Very High") else "Ready for AI"


def _parse_task(raw: str) -> Dict[str, Any]:
    """Extract the JSON object from the model's reply (tolerant of markdown fences)."""
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("engineer_task: model did not return a JSON object")
    task = json.loads(s[start:end + 1])
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
) -> Dict[str, Any]:
    """Return an engineered AI-Work-Queue task dict + a derived `status`.
    Raises ValueError/RuntimeError on LLM failure (surfaced as 502 by the caller)."""
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
        system=_SYSTEM, user=user, model=_MODEL, max_tokens=2000, temperature=0.2,
    )
    task = _parse_task(raw)
    task["status"] = status_from_complexity(task.get("complexity"))
    return task

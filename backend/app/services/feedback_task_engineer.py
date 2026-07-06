"""feedback_task_engineer.py — turn a feedback item + admin context into a
fully-specified AI Work Queue task via a single Anthropic call (schema-forced).

Used by the admin Dispatch flow: the engineered task (goal / plan / spec /
success metrics / verification + Work-Queue classification) is shown to the admin
for review, then written to the Notion AI Work Queue.

PII in the free text is masked before it leaves the platform (CLAUDE.md
"Data minimisation — PII in AI prompts").
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .llm_client import claude_complete
from .pii_masker import mask_pii

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
    "- Infer priority (P0 highest), complexity, task_type, layer and product_area "
    "from the content. A data-isolation issue is always P0 and layer=Isolation.\n"
    "- Reply with valid JSON only, matching the provided schema."
)

# JSON Schema mirroring the Notion AI Work Queue properties we populate.
TASK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Concise task title, max 12 words"},
        "strategic_objective": {"type": "string", "description": "Why this matters — the goal"},
        "execution_prompt": {"type": "string", "description": "Goal + plan + precise ordered steps"},
        "expected_output": {"type": "string", "description": "What the agent should produce"},
        "validation_criteria": {"type": "string", "description": "Explicit, testable pass criteria"},
        "test_command": {"type": "string", "description": "Command(s) to verify, or ''"},
        "technical_constraints": {"type": "string"},
        "files_to_touch": {"type": "string"},
        "risk_rollback": {"type": "string"},
        "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
        "complexity": {"type": "string", "enum": ["Trivial", "Low", "Medium", "High", "Very High"]},
        "task_type": {
            "type": "string",
            "enum": [
                "Frontend Implementation", "Backend Implementation", "UX Redesign",
                "Database Migration", "Prompt Engineering", "RAG Improvement",
                "Performance Optimization", "Research", "Competitive Analysis",
            ],
        },
        "layer": {"type": "string", "enum": ["UI", "API", "Isolation", "Feature", "Infrastructure"]},
        "product_area": {
            "type": "string",
            "enum": ["Core Product", "AI Layer", "Integrations", "UX", "Infrastructure", "GTM"],
        },
    },
    "required": [
        "title", "strategic_objective", "execution_prompt", "expected_output",
        "validation_criteria", "priority", "complexity", "task_type", "layer", "product_area",
    ],
    "additionalProperties": False,
}


def status_from_complexity(complexity: Optional[str]) -> str:
    """High/Very High tasks land as 'Needs Decomposition'; everything else is
    'Ready for AI'. (Admin chose: AI decides status by complexity.)"""
    return "Needs Decomposition" if complexity in ("High", "Very High") else "Ready for AI"


async def engineer_task(
    *,
    text: Optional[str],
    category: str,
    page_url: Optional[str],
    severity: Optional[str],
    area: Optional[str],
    has_screenshot: bool,
    reporter_name: Optional[str],
    admin_context: str,
) -> Dict[str, Any]:
    """Return an engineered AI-Work-Queue task dict (schema above) + a derived
    `status`. Raises if the LLM is unavailable (surfaced as a 502 by the caller)."""
    masked_bug = mask_pii(text or "")
    masked_ctx = mask_pii(admin_context or "")
    user = (
        f"FEEDBACK ({category}) reported on page {page_url or '?'}"
        f"{' [screenshot attached]' if has_screenshot else ''}"
        f"{f' by {reporter_name}' if reporter_name else ''}.\n"
        f"Auto-classified: severity={severity or '?'}, area={area or '?'}.\n\n"
        f"USER MESSAGE:\n{masked_bug or '(none)'}\n\n"
        f"ADMIN CONTEXT (extra detail for the fix):\n{masked_ctx or '(none)'}\n"
    )
    result = await claude_complete(system=_SYSTEM, user=user, schema=TASK_SCHEMA)
    result["status"] = status_from_complexity(result.get("complexity"))
    return result

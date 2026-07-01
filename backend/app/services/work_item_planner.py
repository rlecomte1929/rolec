"""
Mission Control P3 — the planner.

Turns a triaged demand into a structured, human-reviewable plan
({summary, affected_files, approach, test_plan, risk, confidence, approved}) via the
shared LlmClient. The default client masks `user_message` with `mask_pii` before the
Anthropic call, so the demand text is PII-safe by construction. Robust JSON parse
with a conservative (risk=high) fallback so a bad model response never crashes the
endpoint. The human reviews/edits/approves the plan in the console before it can
feed the (deferred) multi-file agent.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .policy_assistant_llm_client import LlmClient, LlmRequest, get_default_client

_SYSTEM = (
    "You are a senior engineer planning a minimal fix for a software demand "
    "(bug / idea / quality issue) in a TypeScript/React + FastAPI codebase. "
    "Return ONLY JSON with exactly these keys: "
    '{"summary": "1-2 sentences", "affected_files": ["path", ...], "approach": "how to fix, minimal", '
    '"test_plan": "how to verify", "risk": "low|medium|high", "confidence": "low|medium|high"}. '
    "Be concrete and conservative. If you cannot plan it safely, set risk to \"high\" and say why in summary."
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
_LEVELS = ("low", "medium", "high")


def _parse_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    for candidate in (text, *(m.group(1) for m in _FENCE_RE.finditer(text))):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            continue
    m = _OBJ_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            pass
    return {}


def build_plan(
    title: str,
    body: str,
    triage: Dict[str, Any],
    *,
    client: Optional[LlmClient] = None,
) -> Dict[str, Any]:
    client = client or get_default_client()
    user = (
        f"DEMAND: {title}\n\n{body}\n\n"
        f"TRIAGE: kind={triage.get('kind')}, priority={triage.get('priority')}, "
        f"complexity={triage.get('complexity')}"
    )
    resp = client.complete(LlmRequest(system=_SYSTEM, user_message=user, max_tokens=800))
    plan = _parse_json((resp.get("text") or "").strip())

    files = plan.get("affected_files")
    return {
        "summary": plan.get("summary") or "",
        "affected_files": files if isinstance(files, list) else [],
        "approach": plan.get("approach") or "",
        "test_plan": plan.get("test_plan") or "",
        "risk": plan["risk"] if plan.get("risk") in _LEVELS else "high",
        "confidence": plan["confidence"] if plan.get("confidence") in _LEVELS else "low",
        "approved": False,
    }

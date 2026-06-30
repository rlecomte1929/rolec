"""
Mission Control P1 — demand triage.

Deterministic-first classification of a demand into {kind, priority, complexity,
auto_fixable, rationale, blocked}. Works with NO LLM key (keyword heuristics) so it
runs offline and is fully unit-testable; an LLM refinement step can be layered later
(mask_pii first, per the GDPR rule). `auto_fixable` mirrors the autofix blocklist:
only a trivial, non-sensitive demand is eligible to be handed to the agent.
"""
from typing import Dict, Optional

# Mirrors lib/autofix-blocklist.ts intent: never auto-touch these surfaces.
_BLOCKLIST_WORDS = (
    "auth", "login", "password", "billing", "payment", "invoice", "migration",
    "schema", "security", "secret", "token", "pii", "gdpr", "rls", "permission",
    ".github", "workflow", "cron", "deploy",
)

_BUG_WORDS = (
    "error", "crash", "broken", "bug", "fail", "doesn't work", "does not work",
    "can't", "cannot", "500", "404", "exception", "stuck", "freeze", "wrong page",
)
_IDEA_WORDS = (
    "idea", "feature", "would be nice", "suggest", "could you add", "it would be great",
    "please add", "wish", "request:", "enhancement",
)
_QUALITY_WORDS = (
    "incorrect", "inaccurate", "hallucinat", "wrong answer", "outdated", "misleading",
    "not grounded", "bad citation",
)
_P0_WORDS = ("down", "outage", "data loss", "everyone", "nobody can", "crash", "cannot log in", "can't log in")
_TRIVIAL_WORDS = ("typo", "copy", "wording", "label", "text says", "spelling", "spacing", "color", "colour", "alignment")
_HEAVY_WORDS = ("refactor", "architecture", "redesign", "rewrite", "migration", "schema")


def _infer_kind(text: str) -> str:
    if any(w in text for w in _QUALITY_WORDS):
        return "quality"
    if any(w in text for w in _BUG_WORDS):
        return "bug"
    if any(w in text for w in _IDEA_WORDS):
        return "idea"
    return "task"


def _infer_priority(text: str, kind: str) -> str:
    if any(w in text for w in _P0_WORDS):
        return "P0"
    if kind == "bug":
        return "P1" if any(w in text for w in ("broken", "error", "fail", "500")) else "P2"
    if kind == "idea":
        return "P3"
    return "P2"


def _infer_complexity(text: str) -> str:
    if any(w in text for w in _HEAVY_WORDS):
        return "high"
    if any(w in text for w in _TRIVIAL_WORDS):
        return "trivial"
    return "medium"


def classify_demand(
    title: str,
    body: str,
    *,
    kind_hint: Optional[str] = None,
) -> Dict[str, object]:
    text = f"{title or ''} {body or ''}".lower()
    kind = kind_hint or _infer_kind(text)
    priority = _infer_priority(text, kind)
    complexity = _infer_complexity(text)
    blocked = any(w in text for w in _BLOCKLIST_WORDS)
    auto_fixable = complexity == "trivial" and not blocked
    rationale = (
        f"{kind}/{priority}/{complexity}; "
        f"{'blocklisted surface — human only' if blocked else ('agent-eligible' if auto_fixable else 'needs a human plan')}"
    )
    return {
        "kind": kind,
        "priority": priority,
        "complexity": complexity,
        "auto_fixable": auto_fixable,
        "blocked": blocked,
        "rationale": rationale,
    }

"""Deterministic keyword-based feedback triage classifier — D-BugRoutine Slice-1.

``classify(text, category)`` inspects the submission text with a simple
priority-ordered keyword scan and returns severity + area labels.

Rules (applied top-to-bottom; first match wins within each dimension):

Area rules (highest specificity first):
  isolation  — "leak", "isolation", "cross-company", "cross company",
                "tenant", "another company", "other company"
  ui         — "spinner", "layout", "button", "display", "render",
                "visual", "style", "css", "modal", "tooltip", "icon",
                "overlap", "alignment", "responsive"
  api        — "500", "error", "exception", "request", "endpoint",
                "api", "http", "auth", "token", "timeout", "response"
  feature    — "feature", "request", "enhancement", "wishlist",
                "suggestion", "improve", "add support", "would like"
  other      — (default)

Severity rules:
  critical   — area is isolation (data isolation breach = always critical)
  high       — "crash", "can't", "cannot", "broken", "500", "error",
                "exception", "fails", "failure", "lost", "down", "unavailable"
  medium     — category is "bug" (explicit bug report but not high-severity)
  low        — (default)

No LLM calls, no network I/O, no PII egress.
"""
from __future__ import annotations

import re

_ISOLATION_WORDS = re.compile(
    r"\b(leak|isolation|cross[- ]company|another company|other company|tenant)\b",
    re.IGNORECASE,
)
_UI_WORDS = re.compile(
    r"\b(spinner|layout|button|display|render|visual|style|css|modal|tooltip|"
    r"icon|overlap|alignment|responsive)\b",
    re.IGNORECASE,
)
_API_WORDS = re.compile(
    r"\b(500|error|exception|endpoint|api|http|auth|token|timeout|response)\b",
    re.IGNORECASE,
)
_FEATURE_WORDS = re.compile(
    r"\b(feature|request|enhancement|wishlist|suggestion|would like|add support)\b",
    re.IGNORECASE,
)
_HIGH_WORDS = re.compile(
    r"\b(crashes?|can't|cannot|broken|500|error|exception|fails?|failure|"
    r"lost|down|unavailable)\b",
    re.IGNORECASE,
)

_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_VALID_AREAS = {"ui", "api", "isolation", "feature", "other"}


def classify(text: str, category: str | None) -> dict:
    """Classify a feedback submission.

    Args:
        text: The user-supplied message (may be empty).
        category: Submission category ("bug", "idea", "other", or None).

    Returns:
        ``{"severity": str, "area": str}`` — both values are always present.
    """
    t = (text or "").lower()

    # ── Area (highest specificity first) ────────────────────────────────────
    if _ISOLATION_WORDS.search(t):
        area = "isolation"
    elif _UI_WORDS.search(t):
        area = "ui"
    elif _FEATURE_WORDS.search(t):
        area = "feature"
    elif _API_WORDS.search(t):
        area = "api"
    else:
        area = "other"

    # ── Severity ────────────────────────────────────────────────────────────
    if area == "isolation":
        severity = "critical"
    elif _HIGH_WORDS.search(t):
        severity = "high"
    elif category == "bug":
        severity = "medium"
    else:
        severity = "low"

    return {"severity": severity, "area": area}

"""Feedback triage classifiers — D-BugRoutine Slice-1 + L1 LLM extension.

``classify(text, category)`` — deterministic keyword scan, no network I/O.
``classify_llm(text, category, *, client=None)`` — optional LLM path with
  mandatory PII masking and deterministic fallback on any error.
``classify_best(text, category, *, db=None, client=None)`` — dispatcher:
  uses classify_llm when the ``feedback_llm_triage`` flag is truthy,
  otherwise classify().  Default is OFF — no behaviour change.

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
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

from .pii_masker import mask_pii  # module-level so tests can monkeypatch feedback_triage.mask_pii

log = logging.getLogger(__name__)

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

# PII-residue check — compiled once for efficiency.
# pii_masker.mask_pii catches its own exceptions and returns the RAW input on
# failure (it does not raise), so the surrounding try/except in classify_llm
# cannot catch the silent-failure path.  After masking, we scan the result for
# PII-shaped content that must not survive masking: an email-like token and a
# run of 7+ consecutive digits (covers phone numbers, SSNs, passport numbers,
# etc.).  If either fires, masking clearly did not work → refuse to call the
# LLM and fall back to the deterministic classifier.
# NOTE: do NOT use `masked == text` as the failure signal — most clean feedback
# ("the button is broken") contains no PII, so mask_pii correctly returns it
# unchanged; treating equality as failure would disable the LLM for the common
# case.
_PII_RESIDUE: re.Pattern = re.compile(r"\S+@\S+\.\S+|\d{7,}")


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


# ---------------------------------------------------------------------------
# L1 LLM-assisted path
# ---------------------------------------------------------------------------

_TRIAGE_SYSTEM = (
    "You are a product-feedback triage assistant. "
    "Classify the user feedback into severity (critical/high/medium/low) "
    "and area (ui/api/isolation/feature/other). "
    "Return JSON only, exactly matching the schema."
)

_TRIAGE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
        "area": {"type": "string", "enum": ["ui", "api", "isolation", "feature", "other"]},
    },
    "required": ["severity", "area"],
    "additionalProperties": False,
}


def classify_llm(
    text: str,
    category: Optional[str],
    *,
    client: Optional[Callable[..., Any]] = None,
) -> dict:
    """LLM-assisted classifier with mandatory PII masking and deterministic fallback.

    Args:
        text:     Raw user-supplied feedback text.  PII is masked before egress.
        category: Submission category ("bug", "idea", "other", or None).
        client:   Optional callable(**kwargs) → dict replacing complete_sync.
                  Accepts the same keyword arguments: system, user, schema.
                  Inject a fake callable in tests to avoid network calls.

    Returns:
        ``{"severity": str, "area": str}`` — always present, always in-enum.
        Falls back to ``classify(text, category)`` on any error (fail-open).
    """
    try:
        masked = mask_pii(text or "")

        # Guard against the masker's silent-failure path: mask_pii returns the
        # raw text (without raising) when it hits an internal error.  If
        # PII-shaped content survives — an email-like token or a 7+-digit run —
        # the masking failed; fall back instead of leaking raw PII to the LLM.
        if _PII_RESIDUE.search(masked):
            log.warning(
                "classify_llm: PII residue detected in masked text; "
                "masker may have failed silently — falling back to deterministic"
            )
            return classify(text, category)

        _call = client
        if _call is None:
            from .llm_client import complete_sync  # lazy — no API key needed at import
            _call = complete_sync

        result = _call(
            system=_TRIAGE_SYSTEM,
            user=f"Category: {category or 'other'}\nFeedback: {masked}",
            schema=_TRIAGE_SCHEMA,
        )

        # Validate result is in-enum before trusting it.
        if (
            isinstance(result, dict)
            and result.get("severity") in _VALID_SEVERITIES
            and result.get("area") in _VALID_AREAS
        ):
            return {"severity": result["severity"], "area": result["area"]}

        log.warning(
            "classify_llm out-of-enum response severity=%r area=%r; falling back",
            result.get("severity") if isinstance(result, dict) else None,
            result.get("area") if isinstance(result, dict) else None,
        )
        return classify(text, category)

    except Exception as exc:  # noqa: BLE001
        log.warning("classify_llm failed (%s); falling back to deterministic", exc)
        return classify(text, category)


def classify_best(
    text: str,
    category: Optional[str],
    *,
    db: Any = None,
    client: Optional[Callable[..., Any]] = None,
) -> dict:
    """Dispatcher: use LLM triage when the flag is enabled, else deterministic.

    The flag is the ``feedback_llm_triage`` platform setting
    (env var ``FEEDBACK_LLM_TRIAGE``).  Default is "0" (OFF) — no LLM call,
    no behaviour change from the original ``classify()`` path.

    Args:
        text:     Feedback text.
        category: Submission category.
        db:       SQLAlchemy session for DB settings lookup (pass None to skip).
        client:   Injectable LLM callable for tests (forwarded to classify_llm).

    Returns:
        ``{"severity": str, "area": str}`` — always; never raises.
    """
    try:
        from .platform_settings import get_setting

        flag = get_setting(
            "feedback_llm_triage",
            env_var="FEEDBACK_LLM_TRIAGE",
            default="0",
            db=db,
        )
        if flag and flag.lower() not in ("0", "false", "off", ""):
            return classify_llm(text, category, client=client)
    except Exception as exc:  # noqa: BLE001
        log.warning("classify_best flag check failed (%s); using deterministic", exc)

    return classify(text, category)

"""
Policy LLM feature flags.

Two environment variables control how policy-side LLM calls behave at runtime:

- RELOPASS_POLICY_LLM_DISABLED (truthy: 1/true/yes/on) — every policy LLM
  call short-circuits without network egress, returning `LLMDisabled(reason=...)`
  in place of a real client. Callers must check `isinstance(client, LLMDisabled)`
  and route to the deterministic fallback (typically setting review_required=True).
- RELOPASS_POLICY_LLM_TEMPERATURE (float) — value passed to
  `chat.completions.create(..., temperature=...)` when LLM is enabled.
  Defaults to 0.0 for audit-grade determinism.

Audit reference: Prompt 0 GAP-006; Prompt A §1 ground rule 1.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class LLMDisabled:
    """
    Returned in place of an OpenAI client when the policy LLM is disabled.
    Callers route to the deterministic fallback via
    `isinstance(client, LLMDisabled)`. The `reason` is a human-readable
    string the caller can surface on review_required document rows.
    """

    reason: str

    def __bool__(self) -> bool:  # pragma: no cover — convenience for `if client:`
        return False


def policy_llm_disabled() -> bool:
    """True if policy-side LLM calls should be skipped entirely."""
    raw = os.environ.get("RELOPASS_POLICY_LLM_DISABLED", "")
    return raw.strip().lower() in _TRUTHY


def policy_llm_temperature(default: float = 0.0) -> float:
    """
    Temperature to pass through to chat.completions.create. Returns the
    `default` (0.0 unless overridden by caller) when the env var is unset
    or unparseable, so we never silently send a non-zero temperature
    during an audit run.
    """
    raw = os.environ.get("RELOPASS_POLICY_LLM_TEMPERATURE")
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default

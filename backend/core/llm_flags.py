"""
Policy LLM feature flags.

Two environment variables control how policy-side LLM calls behave at runtime:

- RELOPASS_POLICY_LLM_DISABLED (truthy: 1/true/yes/on) — every policy LLM
  call short-circuits without network egress and returns a deterministic
  empty result. Callers MUST treat this as "no LLM contribution" and route
  to the deterministic fallback (and typically set review_required=True).
- RELOPASS_POLICY_LLM_TEMPERATURE (float, default 0.0) — value passed to
  `chat.completions.create(..., temperature=...)` when LLM is enabled.
  0.0 gives audit-grade determinism; the product default is also 0.0.

Neither flag has a global on-switch equivalent (i.e. turning the LLM ON
when the customer hasn't configured OPENAI_API_KEY). The existing behavior
— "if OPENAI_API_KEY is absent the services never attempt HTTP" — is
intentionally preserved.

Audit reference: Prompt 0 GAP-006; Prompt A §1 ground rule 1.
"""
from __future__ import annotations

import os
from typing import Final


class _LLMDisabledSentinel:
    """
    Returned in place of an OpenAI client when the policy LLM is disabled
    by env. Attribute access intentionally has no useful behavior — callers
    must short-circuit on `isinstance(client, _LLMDisabledSentinel)` or
    `client is LLMDisabled` before touching it.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "<LLMDisabled>"

    def __bool__(self) -> bool:
        # Falsy so `if client:` branches into the deterministic path.
        return False


LLMDisabled: Final = _LLMDisabledSentinel()

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def policy_llm_disabled() -> bool:
    """True if policy-side LLM calls should be skipped entirely."""
    raw = os.getenv("RELOPASS_POLICY_LLM_DISABLED", "")
    return raw.strip().lower() in _TRUTHY


def policy_llm_temperature() -> float:
    """
    Temperature to pass through to chat.completions.create. Returns 0.0
    when the env var is unset or unparseable so we never silently send
    a non-zero temperature during an audit run.
    """
    raw = os.getenv("RELOPASS_POLICY_LLM_TEMPERATURE", "")
    if not raw:
        return 0.0
    try:
        return float(raw.strip())
    except ValueError:
        return 0.0

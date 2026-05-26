"""
Policy Assistant RAG (Sprint B): LLM client abstraction.

Two implementations:

  - AnthropicClient: real Claude calls. Used in production behind
    ANTHROPIC_API_KEY. Lazy-imports the `anthropic` package so test
    environments don't need it installed.

  - MockClient: returns canned responses based on input pattern. Used
    in tests. Lets us assert system-prompt / user-message shape and
    validator behavior without spending tokens.

Selection via factory get_default_client() based on env:
  - POLICY_ASSISTANT_LLM=mock   → MockClient (forces mock even if key set)
  - POLICY_ASSISTANT_LLM=anthropic → AnthropicClient (errors at construct
    if no key)
  - Default: Anthropic when ANTHROPIC_API_KEY present, Mock otherwise

Both clients return a uniform response shape:
  {
    "text": str,
    "model": str,
    "stop_reason": str,
    "usage": { "input_tokens": int, "output_tokens": int },
  }

Cost estimate available via estimate_cost_usd(usage, model).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

log = logging.getLogger(__name__)


# Model IDs we support. The default is Sonnet 4.6 per the design doc;
# Haiku 4.5 is a cost-aware fallback.
DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODEL = "claude-haiku-4-5-20251001"

# Pricing per 1M tokens, as of 2026-04. Used for the per-question cost
# estimate written to the audit log. Update if Anthropic publishes
# new pricing.
_PRICING_USD_PER_1M = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}


@dataclass
class LlmRequest:
    """Inputs to the LLM. Kept dataclass-shaped so tests + production
    use the same type."""

    system: str
    user_message: str
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 500


class LlmClient(Protocol):
    name: str

    def complete(self, req: LlmRequest) -> Dict[str, Any]: ...


# --- Anthropic real client -------------------------------------------------

class AnthropicClient:
    name = "anthropic"

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set; cannot use AnthropicClient")
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed; pip install anthropic or fall back to MockClient"
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, req: LlmRequest) -> Dict[str, Any]:
        # [P5-9 H1] Mask PII patterns in user_message before crossing the
        # Anthropic API trust boundary. We do NOT mask `system` — that's
        # template text we control, not user input. The masker is
        # idempotent so this is safe even if the caller already masked.
        from .pii_masker import mask_pii
        masked_user_message = mask_pii(req.user_message)

        resp = self._client.messages.create(
            model=req.model,
            system=req.system,
            messages=[{"role": "user", "content": masked_user_message}],
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        # The Anthropic SDK returns a Message object; the text content
        # lives in resp.content[0].text. Defensive: tolerate empty
        # content blocks.
        text = ""
        for block in (resp.content or []):
            if getattr(block, "type", "") == "text":
                text += getattr(block, "text", "")
        usage = getattr(resp, "usage", None)
        return {
            "text": text,
            "model": getattr(resp, "model", req.model),
            "stop_reason": getattr(resp, "stop_reason", "end_turn"),
            "usage": {
                "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            },
        }


# --- Mock client for tests -------------------------------------------------

class MockClient:
    """
    Deterministic mock. Tests inject canned responses keyed by a
    substring of the user message. Falls back to a generic refusal-style
    answer if no match. Lets unit tests cover the validator + retry +
    refusal-on-failure paths without real LLM calls.
    """

    name = "mock"

    def __init__(
        self,
        responses_by_pattern: Optional[Dict[str, str]] = None,
        default_response: str = "I don't see this in your company's policy. Check with your HR team.",
    ) -> None:
        self._patterns = responses_by_pattern or {}
        self._default = default_response
        self.calls: List[LlmRequest] = []  # for test inspection

    def complete(self, req: LlmRequest) -> Dict[str, Any]:
        self.calls.append(req)
        text = self._default
        for pattern, response in self._patterns.items():
            if pattern.lower() in req.user_message.lower():
                text = response
                break
        # Approximate token counts (4 chars ≈ 1 token).
        return {
            "text": text,
            "model": req.model,
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": (len(req.system) + len(req.user_message)) // 4,
                "output_tokens": len(text) // 4,
            },
        }


# --- Factory + cost helper -------------------------------------------------

def get_default_client() -> LlmClient:
    forced = (os.environ.get("POLICY_ASSISTANT_LLM") or "").strip().lower()
    if forced == "mock":
        return MockClient()
    if forced == "anthropic":
        return AnthropicClient()
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicClient()
        except Exception as e:
            log.warning("AnthropicClient unavailable (%s); falling back to MockClient.", e)
            return MockClient()
    return MockClient()


def estimate_cost_usd(usage: Dict[str, int], model: str) -> float:
    """Estimate per-call cost in USD. Returns 0.0 for unknown models so
    audit logging never fails on a model_id we haven't priced."""
    rates = _PRICING_USD_PER_1M.get(model)
    if not rates:
        return 0.0
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return (
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"]
    )


# --- Output validation utilities -------------------------------------------

# Citations look like [chunk:abc123-456] or [chunk:b-1].
CHUNK_CITATION_RE = re.compile(r"\[chunk:([a-zA-Z0-9_\-]+)\]")

# Phrases the assistant should never produce — surfacing them means the
# system prompt is leaking or the LLM is meta-talking. Trip the validator.
_FORBIDDEN_PHRASES = (
    "as an ai",
    "i cannot reveal",
    "my instructions",
    "ignore previous instructions",
    "system prompt",
    "i am claude",
    "i am an ai assistant",
)


def extract_cited_chunk_ids(answer_text: str) -> List[str]:
    """Pull every [chunk:<id>] reference from the answer, deduplicated,
    preserving order of first appearance."""
    seen = set()
    out = []
    for m in CHUNK_CITATION_RE.finditer(answer_text or ""):
        cid = m.group(1)
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def contains_forbidden_phrase(answer_text: str) -> Optional[str]:
    """Return the first forbidden phrase found, or None. Validator uses
    this to reject + retry."""
    lower = (answer_text or "").lower()
    for p in _FORBIDDEN_PHRASES:
        if p in lower:
            return p
    return None

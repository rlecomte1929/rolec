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
  - Default: Anthropic when ANTHROPIC_API_KEY present, Mock otherwise.
    In production (RENDER / ENV=production) the Mock fallback is DISABLED:
    a missing/broken key raises instead of silently returning canned
    refusals (see get_default_client).

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

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

log = logging.getLogger(__name__)


# Model IDs we support. The default is Sonnet 4.6 per the design doc;
# Haiku 4.5 is a cost-aware fallback.
#
# AIQ-1488: claude-sonnet-5 is wired (priced below) but NOT the merge-time default —
# the default stays sonnet-4-6 so prod behaviour and the sonnet-4-6 test suite are
# unchanged. Activate sonnet-5 by setting RELOPASS_LLM_ASSISTANT_MODEL=claude-sonnet-5
# (env-gated, no forced prod swap). This constant also feeds roadmap_generator, which
# is exactly why the swap is env-gated rather than a code-default flip.
DEFAULT_MODEL = os.environ.get("RELOPASS_LLM_ASSISTANT_MODEL", "claude-sonnet-4-6")
FALLBACK_MODEL = "claude-haiku-4-5-20251001"

# Pricing per 1M tokens, as of 2026-04. Used for the per-question cost
# estimate written to the audit log. Update if Anthropic publishes
# new pricing.
_PRICING_USD_PER_1M = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    # Claude Fable 5 (AIQ-1219) — policy-document ingestion model. 1M context.
    # $10 / $50 per 1M input/output tokens (provider pricing, 2026-06). Mirrors
    # the costs.yaml entry so cost_usd_estimated is correct on whichever path
    # prices a Fable-5 call.
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    # Claude Sonnet 5 (AIQ-1488) — 1M context, 128k output. INTRODUCTORY pricing
    # $2 / $10 per 1M input/output tokens, valid through 2026-08-31; revert to
    # standard pricing after. Mirrors the costs.yaml entry.
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
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
    # Optional Anthropic tool-use. When `tools` is set the client passes the
    # schema(s) to the API and returns the first tool_use block's `.input`
    # under the response's `tool_use` key — letting structured callers (e.g.
    # the roadmap generator) read a validated object instead of parsing text.
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Dict[str, Any]] = None


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
        # AIQ-401 documented exception: this is the policy-assistant's dedicated
        # client (Anthropic sonnet default + haiku fallback, per-call PII masking
        # before egress, and structured usage/cost accounting). It intentionally
        # stays separate from the generic llm_client wrapper; unifying would lose
        # the masking + fallback + usage contract its callers depend on.
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

        # W3-5: enable Anthropic prompt caching on the (large, static, reused)
        # system prompt. Passing it as a cache_control block lets repeated calls
        # (every immigration answer + grounding/factual verifier reuses the same
        # system text) read it from cache instead of re-billing input tokens.
        # Harmless if the block is below the model's min-cacheable size.
        system_param = (
            [{"type": "text", "text": req.system, "cache_control": {"type": "ephemeral"}}]
            if req.system
            else req.system
        )

        create_kwargs: Dict[str, Any] = dict(
            model=req.model,
            system=system_param,
            messages=[{"role": "user", "content": masked_user_message}],
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        if req.tools:
            create_kwargs["tools"] = req.tools
            if req.tool_choice:
                create_kwargs["tool_choice"] = req.tool_choice
        resp = self._client.messages.create(**create_kwargs)
        # The Anthropic SDK returns a Message object. Text lives in `text`
        # blocks; a (forced) tool call lives in a `tool_use` block whose
        # `.input` is the already-structured object — no text parsing needed.
        # Defensive: tolerate empty content blocks.
        text = ""
        tool_use = None
        for block in (resp.content or []):
            btype = getattr(block, "type", "")
            if btype == "text":
                text += getattr(block, "text", "")
            elif btype == "tool_use" and tool_use is None:
                tool_use = getattr(block, "input", None)
        usage = getattr(resp, "usage", None)
        return {
            "text": text,
            "tool_use": tool_use,
            "model": getattr(resp, "model", req.model),
            "stop_reason": getattr(resp, "stop_reason", "end_turn"),
            "usage": {
                "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
                # W3-5: surface cache accounting so savings are observable.
                "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) if usage else 0,
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) if usage else 0,
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
        out: Dict[str, Any] = {
            "text": text,
            "model": req.model,
            "stop_reason": "end_turn",
            # Approximate token counts (4 chars ≈ 1 token).
            "usage": {
                "input_tokens": (len(req.system) + len(req.user_message)) // 4,
                "output_tokens": len(text) // 4,
            },
        }
        # When the caller requested tools, mirror the real client: surface the
        # canned response (which tool-using tests supply as the tool's JSON
        # input) as a tool_use block so the tool path is exercised end to end.
        if req.tools:
            try:
                out["tool_use"] = json.loads(text)
                out["stop_reason"] = "tool_use"
            except (json.JSONDecodeError, ValueError):
                out["tool_use"] = None
        return out


# --- Factory + cost helper -------------------------------------------------

def _is_production() -> bool:
    """Match the project-wide prod signal (see db_config.py)."""
    return bool(os.environ.get("RENDER") or os.environ.get("ENV") == "production")


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
            # In prod, NEVER silently degrade to MockClient. Its default
            # response is the verbatim REFUSAL_TEXT and it echoes the real
            # model id into traces, so a broken key masquerades as a
            # legitimate "out of policy" refusal — invisible in monitoring.
            # Fail loud so the misconfiguration surfaces instead.
            if _is_production():
                raise RuntimeError(
                    f"AnthropicClient unavailable in production ({e}); refusing to "
                    "fall back to MockClient (would silently return canned refusals). "
                    "Check ANTHROPIC_API_KEY / the anthropic package."
                ) from e
            log.warning("AnthropicClient unavailable (%s); falling back to MockClient.", e)
            return MockClient()
    # No key configured at all.
    if _is_production():
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set in production; refusing to fall back to "
            "MockClient (would silently return canned refusals for every question). "
            "Set ANTHROPIC_API_KEY, or set POLICY_ASSISTANT_LLM=mock to opt in explicitly."
        )
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

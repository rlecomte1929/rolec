"""Vendor completers for the relopass LLM router (AIQ-1780).

``backend/relopass/llm/router.py`` decides WHICH model a task class gets and what it
costs; it deliberately contains no vendor SDK code. The actual calls live in
completers registered here at boot — the module both router docstrings already point
at (they name ``backend/services/llm_router_clients.py``, written here in the
canonical ``app/services/`` tree per backend/CLAUDE.md).

**This module was never written, and the consequence was total.** ``_get_completer``
raises ``LLMRoutingError`` for an unregistered model; ``_common.call_llm_with_retry``
catches it and returns ``LLMCallResult.empty()``. So in production every LLM-based
extraction agent — marriage, birth, foster-care, diploma, visa-permit, the three tax
certs, employment contract — ran to completion against an EMPTY payload, wrote an
``rce.agent_runs`` row stamped ``llm_model_used="(none — LLM unrouted)"``, and emitted
zero fields. Silently, because every layer on that path is fail-soft.

PII posture — EXEMPT, decided 2026-08-10, recorded in
``backend/tests/test_llm_client_caller_allowlist.py``: this is a transport. The
payloads are document-extraction prompts whose entire purpose is reading the
document's own text, so masking would replace the very names, IDs and dates the
agents exist to extract — the same argument already accepted for
``policy_canonical_extraction`` ("masking would corrupt extraction grounding") and
``ocr_passport_extractor`` ("PII lives in the image"). Note this widens when
MISTRAL_API_KEY lands and non-passport OCR starts producing real text.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Tuple

from backend.relopass.llm import register_completer
from backend.relopass.llm.router import CompletionResult

log = logging.getLogger(__name__)

# The only models ROUTING_TABLE can request. Every one is priced in
# backend/relopass/llm/costs.yaml — route_llm fail-fasts on an unpriced model, so
# registering a model absent from that file would trade one failure for another.
_OPENAI_MODELS: Tuple[str, ...] = ("gpt-4o-mini", "gpt-4o")
_ANTHROPIC_MODELS: Tuple[str, ...] = ("claude-sonnet-4-6",)

# claude-fable-5 is reachable only when POLICY_PARSING_FABLE5 is set (router
# ROUTING_TABLE escalation for policy_clause_extraction).
_FABLE_MODEL = "claude-fable-5"


def _openai_completer(model: str):
    async def _completer(prompt: str, **kwargs: Any) -> CompletionResult:
        from .llm_client import complete_text_with_usage

        text, tokens_in, tokens_out = await complete_text_with_usage(
            system="",
            user=prompt,
            model=model,
            max_tokens=kwargs.get("max_tokens"),
        )
        return CompletionResult(text=text, tokens_in=tokens_in, tokens_out=tokens_out)

    return _completer


def _anthropic_completer(model: str):
    async def _completer(prompt: str, **kwargs: Any) -> CompletionResult:
        from .llm_client import claude_complete_text

        text = await claude_complete_text(
            system="",
            user=prompt,
            model=model,
            max_tokens=int(kwargs.get("max_tokens") or 1024),
        )
        # claude_complete_text does not surface usage. Anthropic is the ESCALATION
        # target only (field_extraction retries once on validator failure), so this
        # under-reports cost on a minority path rather than the common one. Wiring
        # real Anthropic usage is a follow-up; reporting 0 is honest-but-incomplete,
        # and strictly better than the current state of not calling Anthropic at all.
        return CompletionResult(text=text, tokens_in=0, tokens_out=0)

    return _completer


def install_router_completers() -> Dict[str, str]:
    """Register vendor completers for every model the router can route to.

    Idempotent, no network, cheap — it only stuffs closures into a dict — so it is
    safe to call from both app entry points and needs no startup-timeout wrapper.

    **Registration is conditional on the API key being present**, and that is
    load-bearing rather than tidiness. ``call_llm_with_retry`` catches only
    ``LLMRoutingError``; a completer that raised ``RuntimeError("OPENAI_API_KEY … not
    set")`` would escape it and turn today's quiet "zero fields" into an exception
    inside the extraction pipeline. Leaving the model unregistered keeps the existing,
    already-handled degradation.

    One consequence of per-vendor conditionality worth knowing, because it is a
    behaviour change rather than a bug: if OpenAI registers but Anthropic does not,
    a validator failure on ``field_extraction`` escalates to ``claude-sonnet-4-6``,
    finds it unregistered, and ``call_llm_with_retry`` raises ``ExtractionRuntimeError``
    instead of degrading to an empty payload. The orchestrator's fail-soft still
    catches it — the document records ``status='failed'`` rather than ``'OK'`` with
    zero fields, which is arguably the more honest of the two. Production sets both
    keys, so this is the single-vendor corner; ``test_partial_keys_*`` pins it.

    Returns {model_name: status} for logging/tests — "registered" or why it was skipped.
    """
    out: Dict[str, str] = {}

    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    for model in _OPENAI_MODELS:
        if has_openai:
            register_completer(model, _openai_completer(model))
            out[model] = "registered"
        else:
            out[model] = "skipped: OPENAI_API_KEY unset"

    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    anthropic_models = list(_ANTHROPIC_MODELS)
    if os.environ.get("POLICY_PARSING_FABLE5"):
        anthropic_models.append(_FABLE_MODEL)
    for model in anthropic_models:
        if has_anthropic:
            register_completer(model, _anthropic_completer(model))
            out[model] = "registered"
        else:
            out[model] = "skipped: ANTHROPIC_API_KEY unset"

    registered = sorted(m for m, s in out.items() if s == "registered")
    skipped = sorted(m for m, s in out.items() if s != "registered")
    log.info(
        "llm_router_clients: registered=%s skipped=%s",
        ",".join(registered) or "(none)", ",".join(skipped) or "(none)",
    )
    return out

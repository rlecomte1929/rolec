"""
LLM-powered HR policy extraction — AIQ-285.

Additive layer on top of the deterministic regex extractor in
``policy_extractor.py``. When the Anthropic SDK is configured (``ANTHROPIC_API_KEY``
present in the environment) and the document text is non-trivial, this module
calls Claude with a structured tool_use schema to extract a relocation policy
into the same flat list-of-benefits shape that the regex layer produces.

Design notes:

* **Fallback is silent and total.** If the API key is missing, the SDK is not
  installed, the call raises, the call returns malformed JSON, or the document
  is empty, this module returns ``None``. Callers should treat ``None`` as
  "LLM unavailable; fall back to regex."

* **Tool-use, not plain JSON prompting.** The Anthropic SDK's
  ``tools=[...]`` plus ``tool_choice={"type":"tool","name":"..."}`` guarantees
  the model emits a single ``tool_use`` block with a schema-validated input
  shape. Plain-prompt JSON is fragile across model versions; tool_use is the
  canonical pattern.

* **Same return shape as regex.** Each extracted benefit matches the
  ``benefits[]`` shape consumed by ``db.replace_policy_benefits``: ``{
  service_category, benefit_key, benefit_label, eligibility, limits, notes,
  source_section, source_quote, confidence }``. This lets the orchestrator
  (``policy_extractor.extract_policy_with_diff``) overlay the two results
  cleanly.

* **HR confirmation is gated upstream.** This module returns extracted data;
  the orchestrator returns a 3-way diff; the new ``/extract-preview`` endpoint
  surfaces that diff to the Policy Builder UI without auto-saving. The
  existing ``/extract`` endpoint that auto-saves is left in place for
  back-compat.

Configuration:

* ``ANTHROPIC_API_KEY`` — required. Absence → returns None.
* ``RELOPASS_LLM_POLICY_MODEL`` — optional. Defaults to ``claude-sonnet-4-6``
  to match existing usage in ``support.py`` / ``analytics_query.py``.
* ``RELOPASS_LLM_POLICY_MAX_INPUT_CHARS`` — optional. Defaults to 12000.
  Truncates document text before sending so large policy PDFs don't blow
  the context window.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tool schema — keeps the model's output structurally aligned with the regex
# benefits[] shape. Adding a field here is a coordinated change with both the
# regex extractor and the policy_benefits DB schema.
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_POLICY_TOOL: Dict[str, Any] = {
    "name": "record_extracted_policy",
    "description": (
        "Record a structured extraction of an HR relocation policy. Each "
        "benefit_key may appear at most once. Set fields to null when the "
        "policy does not state a value — do not guess."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "policy_meta": {
                "type": "object",
                "properties": {
                    "title": {"type": ["string", "null"]},
                    "version": {"type": ["string", "null"]},
                    "effective_date": {
                        "type": ["string", "null"],
                        "description": "ISO YYYY-MM-DD when present in the policy.",
                    },
                },
                "required": ["title"],
                "additionalProperties": False,
            },
            "benefits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_category": {
                            "type": "string",
                            "enum": [
                                "housing",
                                "movers",
                                "schools",
                                "immigration",
                                "travel",
                                "settling_in",
                                "tax",
                                "spouse",
                                "integration",
                                "repatriation",
                                "home_sale",
                            ],
                        },
                        "benefit_key": {
                            "type": "string",
                            "enum": [
                                "temporary_housing",
                                "rental_deposit",
                                "shipment",
                                "education_support",
                                "visa_support",
                                "travel_host",
                                "settling_in_allowance",
                                "tax_assistance",
                                "spousal_support",
                                "language_training",
                                "repatriation",
                                "scouting_trip",
                                "home_sale_purchase",
                            ],
                        },
                        "benefit_label": {"type": "string"},
                        "eligibility": {
                            "type": ["object", "null"],
                            "description": (
                                "Free-form key/value bag — common keys: bands "
                                "(e.g. ['B1','B2']), assignment_types "
                                "(['permanent','long_term','short_term']), "
                                "min_contract_months, employee_levels."
                            ),
                        },
                        "limits": {
                            "type": ["object", "null"],
                            "description": (
                                "Free-form key/value bag — common keys: days, "
                                "percent, cap (object keyed by currency), "
                                "monthly_cap (same)."
                            ),
                        },
                        "notes": {"type": ["string", "null"]},
                        "source_section": {
                            "type": ["string", "null"],
                            "description": "Heading or section anchor where the benefit is stated.",
                        },
                        "source_quote": {
                            "type": ["string", "null"],
                            "description": (
                                "Verbatim quote (≤ 200 chars) from the policy "
                                "that supports the extraction. Helps HR audit."
                            ),
                        },
                        "confidence": {
                            "type": "number",
                            "description": (
                                "0.0-1.0 confidence. Use 0.9+ when the policy "
                                "states the value explicitly, 0.6-0.8 when "
                                "inferred from context, and < 0.5 when "
                                "speculative — those should typically be omitted."
                            ),
                        },
                    },
                    "required": [
                        "service_category",
                        "benefit_key",
                        "benefit_label",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["policy_meta", "benefits"],
        "additionalProperties": False,
    },
}


SYSTEM_PROMPT = (
    "You are an expert HR mobility analyst extracting structured relocation "
    "benefits from a company policy document. Be conservative: only record a "
    "benefit when the policy clearly states it. When a value is ambiguous, "
    "set the field to null and lower the confidence score. Never invent "
    "amounts or eligibility rules. Always cite the relevant phrase in "
    "source_quote when possible."
)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def extract_policy_with_llm(
    lines: List[str], company_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Run LLM extraction over already-parsed document lines.

    Args:
        lines: Output of ``policy_extractor._extract_text_from_docx`` /
            ``_extract_text_from_pdf`` — a list of normalized, non-empty
            text lines.

    Returns:
        A dict matching the regex extractor's contract::

            {
                "policy_meta": {"title": ..., "version": ..., "effective_date": ...},
                "benefits": [
                    {"service_category": ..., "benefit_key": ..., ...},
                    ...
                ],
                "extracted_at": "2026-05-26T12:34:56.789",
                "extracted_by": "ai",
            }

        Or ``None`` when the LLM layer is unavailable for any reason. The
        ``extracted_by`` key is unique to the LLM path so the orchestrator
        can distinguish provenance.
    """
    if not lines:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info(
            "llm_policy_extractor: ANTHROPIC_API_KEY not set; falling back to regex."
        )
        return None

    # AIQ-401 documented exception: this extractor drives Anthropic tool-use with
    # a domain-specific tool (record_extracted_policy) + prompt-version management
    # and bespoke tool_use-block handling. The generic llm_client.claude_complete
    # forces a single "structured_output" tool, so it can't carry this faithfully.
    try:
        import anthropic  # type: ignore
    except ImportError:
        logger.warning(
            "llm_policy_extractor: anthropic SDK not installed; falling back to regex."
        )
        return None

    # Prompt registry (Parker Step D). Best-effort: when the registry is absent
    # or empty, `active` is None and we fall back to the literal constants below
    # — behavior is byte-for-byte identical to pre-registry.
    active = None
    try:
        from .prompt_registry import get_active_prompt, render_user_message
        active = get_active_prompt("policy_extraction")
    except Exception:  # noqa: BLE001 — registry must never block extraction
        active = None

    # Model precedence: explicit env override (operator escape hatch) → registry
    # → literal default.
    env_model = os.environ.get("RELOPASS_LLM_POLICY_MODEL")
    if env_model:
        model = env_model
    elif active is not None:
        model = active.model_name
    else:
        model = "claude-sonnet-4-6"

    system_prompt = active.system_prompt if active is not None else SYSTEM_PROMPT
    max_tokens = active.max_tokens if active is not None else 4096
    prompt_version_id = active.id if active is not None else None
    canary_arm = active.canary_arm if active is not None else None

    try:
        max_chars = int(os.environ.get("RELOPASS_LLM_POLICY_MAX_INPUT_CHARS", "12000"))
    except ValueError:
        max_chars = 12000

    document_text = "\n".join(lines)
    if len(document_text) > max_chars:
        document_text = document_text[:max_chars]
        truncated = True
    else:
        truncated = False

    rendered = (
        render_user_message(active.user_template, {"truncated": truncated, "document_text": document_text})
        if (active is not None and active.user_template)
        else None
    )
    user_prompt = rendered if rendered is not None else (
        "Extract the relocation policy from the document below. Use the "
        "record_extracted_policy tool to record every benefit you find. If a "
        "field is not stated, set it to null. Do not invent values.\n\n"
        f"DOCUMENT (truncated={truncated}):\n{document_text}"
    )

    call_started_at = time.time()
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=[EXTRACT_POLICY_TOOL],
            tool_choice={"type": "tool", "name": EXTRACT_POLICY_TOOL["name"]},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — defensive fallback
        logger.warning(
            "llm_policy_extractor: Anthropic API call failed (%s); falling back to regex.",
            exc.__class__.__name__,
        )
        _forward_to_langsmith(
            model=model,
            document_chars=len(document_text),
            truncated=truncated,
            latency_ms=int((time.time() - call_started_at) * 1000),
            success=False,
            error=exc.__class__.__name__,
            benefits_count=0,
        )
        return None
    call_latency_ms = int((time.time() - call_started_at) * 1000)

    tool_input = _first_tool_input(message)
    if tool_input is None:
        logger.warning(
            "llm_policy_extractor: model returned no tool_use block; falling back to regex."
        )
        return None

    meta = tool_input.get("policy_meta") or {}
    benefits_raw = tool_input.get("benefits") or []
    if not isinstance(benefits_raw, list):
        logger.warning(
            "llm_policy_extractor: benefits field was not a list; falling back to regex."
        )
        return None

    # Deduplicate by benefit_key (the tool schema allows the model to emit
    # duplicates — last-write-wins per the audit's "single entry per benefit"
    # convention).
    seen: Dict[str, Dict[str, Any]] = {}
    for raw in benefits_raw:
        if not isinstance(raw, dict):
            continue
        key = raw.get("benefit_key")
        if not isinstance(key, str):
            continue
        seen[key] = _normalize_benefit(raw)

    result = {
        "policy_meta": {
            "title": meta.get("title") or "Relocation Policy",
            "version": meta.get("version"),
            "effective_date": meta.get("effective_date"),
        },
        "benefits": list(seen.values()),
        "extracted_at": datetime.utcnow().isoformat(),
        "extracted_by": "ai",
        "model": model,
        "truncated": truncated,
        "prompt_version_id": prompt_version_id,
        "canary_arm": canary_arm,
    }
    _forward_to_langsmith(
        model=model,
        document_chars=len(document_text),
        truncated=truncated,
        latency_ms=call_latency_ms,
        success=True,
        error=None,
        benefits_count=len(result["benefits"]),
    )
    # Unit-economics trace (Parker Step G). Only on the success path — the
    # fallback/early-return paths above incur no LLM cost. Best-effort: never
    # block extraction.
    try:
        from .ai_trace_logger import TraceSession

        tracer = TraceSession(
            session_id=None,
            query="<policy extraction>",  # hashed to query_hash; carries no document content
            company_id=company_id or "unknown",
            feature_key="policy_extraction",
        )
        tracer.record_llm_call(
            model=model,
            input_tokens=int(getattr(message.usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(message.usage, "output_tokens", 0) or 0),
            latency_ms=call_latency_ms,
        )
        tracer.set_prompt_attribution(prompt_version_id, canary_arm)
        tracer.flush()
    except Exception:  # noqa: BLE001 — tracing must never break extraction
        logger.debug("policy_extraction tracer flush failed", exc_info=True)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


def _first_tool_input(message: Any) -> Optional[Dict[str, Any]]:
    """Find the first ``tool_use`` block in the response and return its input."""
    content = getattr(message, "content", None)
    if not content:
        return None
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            tool_input = getattr(block, "input", None)
            if isinstance(tool_input, dict):
                return tool_input
    return None


def _normalize_benefit(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce the model's tool_input into the regex-extractor benefit shape."""
    return {
        "service_category": raw.get("service_category"),
        "benefit_key": raw.get("benefit_key"),
        "benefit_label": raw.get("benefit_label"),
        "eligibility": raw.get("eligibility") if isinstance(raw.get("eligibility"), dict) else None,
        "limits": raw.get("limits") if isinstance(raw.get("limits"), dict) else None,
        "notes": raw.get("notes"),
        "source_section": raw.get("source_section"),
        "source_quote": raw.get("source_quote"),
        "confidence": _clamp_confidence(raw.get("confidence")),
    }


def _clamp_confidence(value: Any) -> float:
    """Coerce model confidence into [0, 1]."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    if f < 0:
        return 0.0
    if f > 1:
        return 1.0
    return f


# ─────────────────────────────────────────────────────────────────────────────
# Langsmith tracing (AIQ-285-followup)
#
# Defensive, fire-and-forget. Never raises. Skips silently when:
#   - LANGSMITH_API_KEY is unset (most environments)
#   - langsmith package is not installed
#   - the Client.create_run call itself errors
#
# Same idiom as ai_trace_logger._forward_to_langsmith() — no LangChain
# dependency, no global state, no rate-limiting concerns. We capture only
# operational metadata: model, document size, truncation flag, latency,
# success, benefit count. Raw policy text is NEVER sent (PII guardrail).
# ─────────────────────────────────────────────────────────────────────────────


def _forward_to_langsmith(
    *,
    model: str,
    document_chars: int,
    truncated: bool,
    latency_ms: int,
    success: bool,
    error: Optional[str],
    benefits_count: int,
) -> None:
    """Push a single ``policy_extraction`` run to LangSmith.

    All keyword args. Silent no-op when LANGSMITH_API_KEY is unset or the
    SDK is missing. Failures inside the call are logged at DEBUG so the
    main extraction flow is never blocked.
    """
    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        return

    project = os.environ.get(
        "LANGSMITH_PROJECT", "relopass-policy-extraction"
    ).strip() or "relopass-policy-extraction"

    try:
        from langsmith import Client  # type: ignore
    except ImportError:
        logger.debug(
            "llm_policy_extractor: langsmith SDK not installed; tracing skipped."
        )
        return

    try:
        client = Client(api_key=api_key)
        now = datetime.now(timezone.utc)
        client.create_run(
            id=uuid.uuid4(),
            name="policy_extraction",
            run_type="llm",
            project_name=project,
            inputs={
                "document_chars": document_chars,
                "truncated": truncated,
                "model": model,
            },
            outputs={
                "success": success,
                "benefits_count": benefits_count,
                "latency_ms": latency_ms,
                "error": error,
            },
            start_time=now,
            end_time=now,
            extra={"metadata": {"task_id": "AIQ-285"}},
        )
    except Exception:  # noqa: BLE001 — tracing must never block extraction
        logger.debug("llm_policy_extractor: langsmith forward failed", exc_info=True)

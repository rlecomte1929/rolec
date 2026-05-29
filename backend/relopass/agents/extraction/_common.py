"""Shared utilities for the per-document-type Extraction Agents (C1-05c–f).

Every agent in this sub-package follows the same shape:

* Load a prompt (or multiple, keyed by jurisdiction)
* Register an :class:`ExtractionAgent` via the C1-05a runtime
* Run a hybrid extraction (deterministic primitives + LLM via C1-13 router)
* Emit :class:`ExtractedField` rows + an agent_runs entry

The helpers here factor out the boilerplate — JSON parsing, graceful
degradation when the LLM router has no completer, ExtractedField row
construction — so each agent module stays focused on its document-type
specifics (annualization rules, ISCED inference, residence-purpose mapping).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Tuple
from uuid import UUID

from backend.relopass.llm import LLMRoutingError, route_llm

from ..models import ExtractedField
from ..runtime import ExtractionRuntimeError

logger = logging.getLogger(__name__)


def parse_llm_json(raw: str) -> Dict[str, Any]:
    """Parse a JSON object out of an LLM response.

    Tolerates markdown fences (```json … ```) and the Anthropic
    tool-use ``{"input": {...}}`` wrapper.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionRuntimeError(f"LLM output was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionRuntimeError(
            f"LLM output JSON must be an object, got {type(data).__name__}"
        )
    if "input" in data and isinstance(data["input"], dict):
        return dict(data["input"])
    return dict(data)


@dataclass(frozen=True)
class LLMCallResult:
    """The result of an LLM call done by an agent. Convenience bundle for
    the per-agent callers that don't want to thread the same five values
    through every code path.
    """

    payload: Mapping[str, Any]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    inputs_digest: str
    output_digest: str

    @classmethod
    def empty(cls) -> "LLMCallResult":
        return cls(
            payload={},
            model_name="(none — LLM unrouted)",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            inputs_digest="",
            output_digest="",
        )


async def call_llm_with_retry(
    prompt: str,
    *,
    required_keys: Tuple[str, ...] = (),
    case_id: Optional[str] = None,
    task_class: str = "field_extraction",
) -> LLMCallResult:
    """Call the LLM via the C1-13 router with a single-retry escalation on
    validator failure. Returns an :class:`LLMCallResult.empty()` if no
    completer is registered (graceful degradation — the deterministic
    layers in each agent are the primary value).
    """
    try:
        handle = route_llm(task_class)
    except LLMRoutingError as exc:
        logger.warning("LLM routing failed (task=%s): %s", task_class, exc)
        return LLMCallResult.empty()

    try:
        raw = await handle.complete(prompt, max_tokens=handle.token_budget, case_id=case_id)
    except LLMRoutingError as exc:
        # No completer registered for the chosen model.
        logger.warning("No completer for %s — LLM skipped (%s)", handle.model_name, exc)
        return LLMCallResult.empty()

    payload = parse_llm_json(raw)
    missing = tuple(k for k in required_keys if k not in payload)
    if missing:
        # One retry on the escalated model.
        try:
            handle = route_llm(task_class, validator_failed=True)
            raw = await handle.complete(prompt, max_tokens=handle.token_budget, case_id=case_id)
        except LLMRoutingError:
            raise ExtractionRuntimeError(
                f"LLM output missing required keys {missing} and escalation not available"
            )
        payload = parse_llm_json(raw)
        missing = tuple(k for k in required_keys if k not in payload)
        if missing:
            raise ExtractionRuntimeError(
                f"LLM output missing required keys after retry: {missing}"
            )

    return LLMCallResult(
        payload=payload,
        model_name=handle.model_name,
        tokens_in=handle.tokens_in,
        tokens_out=handle.tokens_out,
        cost_usd=handle.cost_usd,
        inputs_digest=handle.inputs_digest,
        output_digest=handle.output_digest,
    )


def make_field(
    *,
    document_id: UUID,
    agent_run_id: UUID,
    key: str,
    value: Any,
    source: str,
    confidence: float = 0.9,
    canonical_extras: Optional[Mapping[str, Any]] = None,
    bbox_page: Optional[int] = None,
    bbox: Optional[Tuple[int, int, int, int]] = None,
    resolution_status: Optional[str] = None,
) -> Optional[ExtractedField]:
    """Standardised ExtractedField row builder.

    Returns ``None`` when ``value`` is None / empty — callers can filter
    them out with a single ``[f for f in (...) if f is not None]`` pass.
    """
    if value is None or value == "":
        return None
    canonical: Dict[str, Any] = {"source": source}
    if canonical_extras:
        canonical.update(canonical_extras)
    if isinstance(value, (list, dict)):
        value_raw = json.dumps(value, ensure_ascii=False)
        canonical["structured"] = value
    else:
        value_raw = str(value)
    x0 = y0 = x1 = y1 = None
    if bbox is not None:
        x0, y0, x1, y1 = bbox
    return ExtractedField(
        document_id=document_id,
        field_key=key,
        value_raw=value_raw,
        value_canonical=canonical,
        confidence=max(0.0, min(1.0, confidence)),
        bbox_page=bbox_page,
        bbox_x0=x0,
        bbox_y0=y0,
        bbox_x1=x1,
        bbox_y1=y1,
        agent_run_id=agent_run_id,
        resolution_status=resolution_status,  # type: ignore[arg-type]
    )

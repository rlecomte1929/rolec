"""
LLM Client wrapper — AUDIT-B5
==============================
Single entry-point for all LLM calls in the backend.

Features:
  - Configurable timeout + exponential backoff on 429 / 5xx
  - Schema-validated JSON output (OpenAI structured outputs / Anthropic tool use)
  - Structured logging: request_id, latency, token counts

Public API
----------
  await complete(*, system, user, schema, ...)        — OpenAI  (gpt-4o default)
  await claude_complete(*, system, user, schema, ...) — Anthropic (claude-sonnet-4-6 default)

Both functions return the parsed dict produced by the model.

Security: never pass raw user-controlled text into the *system* parameter.
The *system* arg must be a static template. User-supplied values belong in
*user* only, and callers are responsible for any PII masking before the call.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_OPENAI_DEFAULT_MODEL = "gpt-4o"
_ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3

# HTTP status codes that are transient and warrant a retry
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _jitter(attempt: int) -> float:
    """Full-jitter exponential backoff: random(0, min(30, 2^attempt))."""
    return random.uniform(0, min(30.0, 2 ** attempt))


def _http_status(exc: Exception) -> Optional[int]:
    """Extract the HTTP status code from an SDK exception, if available."""
    for attr in ("status_code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    response = getattr(exc, "response", None)
    if response is not None:
        for attr in ("status_code", "status"):
            val = getattr(response, attr, None)
            if isinstance(val, int):
                return val
    return None


# ---------------------------------------------------------------------------
# OpenAI — async complete
# ---------------------------------------------------------------------------

async def complete(
    *,
    system: str,
    user: str,
    schema: Dict[str, Any],
    image_url: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    model: str = _OPENAI_DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    Call OpenAI with structured JSON output and automatic retry.

    Args:
        system:      Static system prompt (never interpolate user input here).
        user:        User message text.
        schema:      JSON Schema dict for the response. When non-empty, uses
                     OpenAI structured outputs (``response_format`` json_schema).
                     Pass ``{}`` to fall back to free-form json_object mode.
        image_url:   Optional base64 data URL or HTTPS URL for vision calls.
        timeout:     Per-request timeout in seconds.
        max_retries: Number of additional attempts after the first on 429/5xx.
        model:       OpenAI model ID.

    Returns:
        Parsed JSON dict from the model.

    Raises:
        RuntimeError: OPENAI_API_KEY not set or openai not installed.
        ValueError:   Response could not be parsed as JSON.
        Exception:    Propagated after all retries exhausted.
    """
    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError:
        raise RuntimeError("openai package is not installed — run: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    request_id = str(uuid.uuid4())
    client = AsyncOpenAI(api_key=api_key)

    # Build the user content block (text only, or text + image for vision)
    if image_url:
        user_content: Any = [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
        ]
    else:
        user_content = user

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})

    # Decide response_format
    if schema:
        response_format: Any = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "strict": True,
                "schema": schema,
            },
        }
    else:
        response_format = {"type": "json_object"}

    last_exc: Exception = RuntimeError("No attempts were made")
    for attempt in range(max_retries + 1):
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                ),
                timeout=timeout,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            usage = response.usage
            log.info(
                "llm_complete ok request_id=%s model=%s attempt=%d "
                "latency_ms=%d input_tokens=%s output_tokens=%s",
                request_id, model, attempt, latency_ms,
                getattr(usage, "prompt_tokens", "?"),
                getattr(usage, "completion_tokens", "?"),
            )

            raw = response.choices[0].message.content or "{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                log.error(
                    "llm_complete json_parse_error request_id=%s raw_prefix=%.200s",
                    request_id, raw,
                )
                raise ValueError(f"LLM returned non-JSON: {raw[:200]}") from exc

        except asyncio.TimeoutError:
            latency_ms = int((time.monotonic() - t0) * 1000)
            log.warning(
                "llm_complete timeout request_id=%s model=%s attempt=%d latency_ms=%d",
                request_id, model, attempt, latency_ms,
            )
            last_exc = TimeoutError(f"OpenAI request timed out after {timeout}s")

        except Exception as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            status = _http_status(exc)
            if status in _RETRY_STATUS_CODES:
                log.warning(
                    "llm_complete retryable request_id=%s model=%s "
                    "attempt=%d status=%s latency_ms=%d error=%s",
                    request_id, model, attempt, status, latency_ms, exc,
                )
                last_exc = exc
            else:
                log.error(
                    "llm_complete fatal request_id=%s model=%s "
                    "attempt=%d status=%s latency_ms=%d error=%s",
                    request_id, model, attempt, status, latency_ms, exc,
                )
                raise

        if attempt < max_retries:
            delay = _jitter(attempt)
            log.info(
                "llm_complete retry request_id=%s attempt=%d next_in=%.2fs",
                request_id, attempt, delay,
            )
            await asyncio.sleep(delay)

    raise last_exc


# ---------------------------------------------------------------------------
# Anthropic — async claude_complete
# ---------------------------------------------------------------------------

async def claude_complete(
    *,
    system: str,
    user: str,
    schema: Dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    model: str = _ANTHROPIC_DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    Call Anthropic Claude with structured JSON output via tool use, with retry.

    Uses Anthropic's ``tool_use`` feature with ``tool_choice`` forced to the
    single schema tool so the model always returns a conforming JSON object.

    Args:
        system:      Static system prompt.
        user:        User message text.
        schema:      JSON Schema dict for the response (used as input_schema
                     for the tool).
        timeout:     Per-request timeout in seconds.
        max_retries: Number of additional attempts on 429/5xx.
        model:       Anthropic model ID.

    Returns:
        Parsed JSON dict from the tool_use block.

    Raises:
        RuntimeError: ANTHROPIC_API_KEY not set or anthropic not installed.
        ValueError:   No tool_use block or unparseable content returned.
        Exception:    Propagated after all retries exhausted.
    """
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise RuntimeError("anthropic package is not installed — run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

    request_id = str(uuid.uuid4())
    # The anthropic SDK is synchronous; wrap in asyncio.to_thread
    sync_client = anthropic.Anthropic(api_key=api_key)

    tool_def = {
        "name": "structured_output",
        "description": "Return the answer as a structured JSON object exactly matching the schema.",
        "input_schema": schema or {"type": "object", "properties": {}, "additionalProperties": True},
    }

    last_exc: Exception = RuntimeError("No attempts were made")
    for attempt in range(max_retries + 1):
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    sync_client.messages.create,
                    model=model,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    max_tokens=4096,
                    tools=[tool_def],
                    tool_choice={"type": "tool", "name": "structured_output"},
                ),
                timeout=timeout,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            usage = getattr(response, "usage", None)
            log.info(
                "claude_complete ok request_id=%s model=%s attempt=%d "
                "latency_ms=%d input_tokens=%s output_tokens=%s",
                request_id, model, attempt, latency_ms,
                getattr(usage, "input_tokens", "?") if usage else "?",
                getattr(usage, "output_tokens", "?") if usage else "?",
            )

            # Extract the tool_use block input (the structured JSON)
            tool_input: Optional[Dict[str, Any]] = None
            for block in (response.content or []):
                if getattr(block, "type", "") == "tool_use":
                    raw_input = getattr(block, "input", None)
                    if isinstance(raw_input, dict):
                        tool_input = raw_input
                    elif isinstance(raw_input, str):
                        try:
                            tool_input = json.loads(raw_input)
                        except json.JSONDecodeError:
                            pass
                    if tool_input is not None:
                        break

            # Fallback: try a text block if tool_use wasn't present
            if tool_input is None:
                for block in (response.content or []):
                    if getattr(block, "type", "") == "text":
                        try:
                            tool_input = json.loads(getattr(block, "text", "{}"))
                            break
                        except json.JSONDecodeError:
                            pass

            if tool_input is None:
                raise ValueError(
                    "Anthropic response contained no tool_use block with structured output."
                )

            return tool_input

        except asyncio.TimeoutError:
            latency_ms = int((time.monotonic() - t0) * 1000)
            log.warning(
                "claude_complete timeout request_id=%s model=%s attempt=%d latency_ms=%d",
                request_id, model, attempt, latency_ms,
            )
            last_exc = TimeoutError(f"Anthropic request timed out after {timeout}s")

        except Exception as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            status = _http_status(exc)
            if status in _RETRY_STATUS_CODES:
                log.warning(
                    "claude_complete retryable request_id=%s model=%s "
                    "attempt=%d status=%s latency_ms=%d error=%s",
                    request_id, model, attempt, status, latency_ms, exc,
                )
                last_exc = exc
            else:
                log.error(
                    "claude_complete fatal request_id=%s model=%s "
                    "attempt=%d status=%s latency_ms=%d error=%s",
                    request_id, model, attempt, status, latency_ms, exc,
                )
                raise

        if attempt < max_retries:
            delay = _jitter(attempt)
            log.info(
                "claude_complete retry request_id=%s attempt=%d next_in=%.2fs",
                request_id, attempt, delay,
            )
            await asyncio.sleep(delay)

    raise last_exc

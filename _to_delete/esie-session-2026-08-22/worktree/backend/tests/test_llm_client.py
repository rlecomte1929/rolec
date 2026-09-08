"""
Tests for backend/app/services/llm_client.py — AUDIT-B5

Coverage:
  1. complete() succeeds on first attempt → returns parsed dict
  2. complete() retries on 429 → succeeds on second attempt
  3. complete() raises ValueError when the model returns non-JSON
  4. claude_complete() succeeds (tool_use block returned)
  5. claude_complete() raises ValueError when no tool_use block
  6. complete() raises TimeoutError after all retries exhausted on timeout
  7. Malformed JSON at the wrapper boundary is rejected before callers see it
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers — fake OpenAI response shape
# ---------------------------------------------------------------------------

def _make_openai_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _openai_status_error(status: int) -> Exception:
    """Create a minimal fake openai.APIStatusError."""
    exc = Exception(f"HTTP {status}")
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


# ---------------------------------------------------------------------------
# Tests — complete() (OpenAI)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_success():
    """Returns parsed dict on a clean first-call response."""
    payload = {"surname": "SMITH", "given_names": "JOHN"}
    fake_resp = _make_openai_response(json.dumps(payload))

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("openai.AsyncOpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create = AsyncMock(return_value=fake_resp)

            from backend.app.services.llm_client import complete
            result = await complete(
                system="You are a test assistant.",
                user="Extract passport data.",
                schema={},
            )

    assert result == payload


@pytest.mark.asyncio
async def test_complete_retries_on_429_then_succeeds():
    """First call raises a 429, second call succeeds — retry logic works."""
    payload = {"answer": "ok"}
    fake_resp = _make_openai_response(json.dumps(payload))
    rate_limit_err = _openai_status_error(429)

    call_count = {"n": 0}

    async def side_effect(**kwargs: Any):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise rate_limit_err
        return fake_resp

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("openai.AsyncOpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create = side_effect

            # Patch sleep to avoid real delays in tests
            with patch("asyncio.sleep", new_callable=AsyncMock):
                from backend.app.services import llm_client
                import importlib
                importlib.reload(llm_client)
                result = await llm_client.complete(
                    system="",
                    user="test",
                    schema={},
                    max_retries=2,
                )

    assert result == payload
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_complete_raises_on_non_json():
    """Malformed JSON from the model is rejected at the wrapper — not propagated raw."""
    fake_resp = _make_openai_response("This is definitely not JSON <><>")

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("openai.AsyncOpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create = AsyncMock(return_value=fake_resp)

            from backend.app.services.llm_client import complete
            with pytest.raises(ValueError, match="non-JSON"):
                await complete(system="", user="test", schema={})


@pytest.mark.asyncio
async def test_complete_raises_after_all_retries_on_timeout():
    """If every attempt times out, TimeoutError is raised after max_retries+1 tries."""
    async def always_timeout(**kwargs: Any):
        raise asyncio.TimeoutError()

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("openai.AsyncOpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create = always_timeout

            with patch("asyncio.sleep", new_callable=AsyncMock):
                from backend.app.services import llm_client
                import importlib
                importlib.reload(llm_client)
                with pytest.raises(TimeoutError):
                    await llm_client.complete(
                        system="",
                        user="test",
                        schema={},
                        max_retries=1,
                    )


# ---------------------------------------------------------------------------
# Tests — claude_complete() (Anthropic)
# ---------------------------------------------------------------------------

def _make_anthropic_tool_response(input_data: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_data
    usage = MagicMock()
    usage.input_tokens = 8
    usage.output_tokens = 4
    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
    return resp


@pytest.mark.asyncio
async def test_claude_complete_success():
    """Returns the tool_use block's input dict on success."""
    expected = {"status": "GREEN", "score": 85}
    fake_resp = _make_anthropic_tool_response(expected)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("anthropic.Anthropic") as MockAnthropic:
            instance = MockAnthropic.return_value
            # messages.create is synchronous; we'll mock asyncio.to_thread
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=fake_resp):
                from backend.app.services.llm_client import claude_complete
                result = await claude_complete(
                    system="You are a test assistant.",
                    user="What is the readiness status?",
                    schema={"type": "object", "properties": {}},
                )

    assert result == expected


@pytest.mark.asyncio
async def test_claude_complete_raises_when_no_tool_use():
    """If Anthropic returns no tool_use block, ValueError is raised at the wrapper."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is my answer in prose."
    resp = MagicMock()
    resp.content = [text_block]
    resp.usage = MagicMock()

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("anthropic.Anthropic"):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=resp):
                from backend.app.services.llm_client import claude_complete
                with pytest.raises(ValueError, match="tool_use"):
                    await claude_complete(
                        system="",
                        user="test",
                        schema={"type": "object", "properties": {}},
                    )


# ---------------------------------------------------------------------------
# Boundary: malformed JSON is rejected before it reaches the caller
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_json_never_reaches_caller():
    """
    The wrapper must intercept bad JSON so callers never see a raw unparsed
    string. ValueError with a meaningful message is the contract.
    """
    fake_resp = _make_openai_response("}{broken json}{")

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("openai.AsyncOpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create = AsyncMock(return_value=fake_resp)

            from backend.app.services.llm_client import complete
            try:
                await complete(system="", user="test", schema={})
                assert False, "Should have raised ValueError"
            except ValueError as exc:
                # The error message must be human-readable, not a raw trace
                assert "non-JSON" in str(exc) or "JSON" in str(exc)
                # The raw payload should not silently propagate as a return value

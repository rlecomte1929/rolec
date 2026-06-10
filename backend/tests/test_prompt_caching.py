"""
W3-5 — Anthropic prompt caching. The (large, static, reused) system prompt is
sent as a cache_control block so repeated calls read it from cache instead of
re-billing input tokens; cache accounting is surfaced in usage.
"""
from __future__ import annotations

from backend.app.services import policy_assistant_llm_client as C


class _Usage:
    input_tokens = 10
    output_tokens = 5
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 128


class _Block:
    type = "text"
    text = "answer"


class _Resp:
    content = [_Block()]
    model = "claude-sonnet-4-6"
    stop_reason = "end_turn"
    usage = _Usage()


def test_system_prompt_sent_as_cache_control_block_and_usage_surfaced():
    captured = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Resp()

    class _FakeClient:
        messages = _FakeMessages()

    client = object.__new__(C.AnthropicClient)  # bypass __init__ (no key/SDK needed)
    client._client = _FakeClient()

    out = client.complete(
        C.LlmRequest(system="A LARGE STATIC SYSTEM PROMPT", user_message="q", model="claude-sonnet-4-6")
    )

    system = captured["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[0]["text"] == "A LARGE STATIC SYSTEM PROMPT"
    assert out["usage"]["cache_read_input_tokens"] == 128
    assert out["usage"]["cache_creation_input_tokens"] == 0


def test_empty_system_not_wrapped():
    captured = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Resp()

    class _FakeClient:
        messages = _FakeMessages()

    client = object.__new__(C.AnthropicClient)
    client._client = _FakeClient()
    client.complete(C.LlmRequest(system="", user_message="q", model="claude-sonnet-4-6"))
    assert captured["system"] == ""  # nothing to cache; passed through unchanged

"""Tests for the free-text + sync llm_client variants (AUDIT-B5-followup / AIQ-401).

Mocks the OpenAI/Anthropic SDKs so no network or keys are needed. Covers the
text passthrough, the sync bridges (including the running-loop branch), and the
shared retry-on-429 path.
"""
import asyncio
import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from backend.app.services import llm_client  # noqa: E402


# ── Fakes ──────────────────────────────────────────────────────────────────
class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _OpenAIResp:
    def __init__(self, content):
        self.choices = [_Choice(content)]
        self.usage = None


class _FakeCompletions:
    def __init__(self, content="hello", fail_times=0, status=429):
        self._content = content
        self._fail_times = fail_times
        self._status = status
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self._fail_times:
            exc = Exception("transient")
            exc.status_code = self._status
            raise exc
        return _OpenAIResp(self._content)


def _make_openai(content="hello", fail_times=0):
    comps = _FakeCompletions(content, fail_times)

    class _Chat:
        completions = comps

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = _Chat()

    return _FakeAsyncOpenAI, comps


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _ClaudeResp:
    def __init__(self, text):
        self.content = [_Block(text)]
        self.usage = None


def _make_anthropic(text="world"):
    class _Messages:
        def create(self, **kwargs):  # sync — wrapped in asyncio.to_thread
            return _ClaudeResp(text)

    class _FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    return _FakeAnthropic


# ── Tests ──────────────────────────────────────────────────────────────────
def test_complete_text_returns_content(monkeypatch):
    fake, _ = _make_openai("the answer")
    monkeypatch.setattr("openai.AsyncOpenAI", fake)
    out = asyncio.run(llm_client.complete_text(system="s", user="u"))
    assert out == "the answer"


def test_complete_text_sync_bridge(monkeypatch):
    fake, _ = _make_openai("sync answer")
    monkeypatch.setattr("openai.AsyncOpenAI", fake)
    out = llm_client.complete_text_sync(system="s", user="u", temperature=0.0)
    assert out == "sync answer"


def test_complete_text_json_object_flag(monkeypatch):
    fake, comps = _make_openai('{"k": 1}')
    monkeypatch.setattr("openai.AsyncOpenAI", fake)
    out = llm_client.complete_text_sync(system="s", user="u", json_object=True)
    assert out == '{"k": 1}'


def test_complete_text_retries_on_429(monkeypatch):
    fake, comps = _make_openai("recovered", fail_times=1)
    monkeypatch.setattr("openai.AsyncOpenAI", fake)
    monkeypatch.setattr(llm_client, "_jitter", lambda attempt: 0.0)
    out = asyncio.run(llm_client.complete_text(system="s", user="u", max_retries=2))
    assert out == "recovered"
    assert comps.calls == 2  # failed once, succeeded on retry


def test_claude_complete_text_joins_blocks(monkeypatch):
    monkeypatch.setattr("anthropic.Anthropic", _make_anthropic("claude says hi"))
    out = asyncio.run(llm_client.claude_complete_text(system="s", user="u"))
    assert out == "claude says hi"


def test_claude_complete_text_sync_bridge(monkeypatch):
    monkeypatch.setattr("anthropic.Anthropic", _make_anthropic("sync claude"))
    out = llm_client.claude_complete_text_sync(system="s", user="u", max_tokens=256)
    assert out == "sync claude"


def test_sync_bridge_works_inside_running_loop(monkeypatch):
    """complete_text_sync must not raise when a loop is already running."""
    fake, _ = _make_openai("loop-safe")
    monkeypatch.setattr("openai.AsyncOpenAI", fake)

    async def _driver():
        # We're inside a running loop here; the bridge must offload to a thread.
        return llm_client.complete_text_sync(system="s", user="u")

    assert asyncio.run(_driver()) == "loop-safe"

"""AIQ-571 — Langfuse trace emission must be fail-soft + env-gated.

The one invariant that matters: tracing NEVER breaks or changes an LLM call. When
LANGFUSE_* keys are unset (the default in dev/CI), tracing is a silent no-op and the
decorated function returns exactly what it would without the decorator.
"""
from __future__ import annotations

import asyncio
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app.services.llm_tracing as t


def _reset_client():
    t._init_done = False
    t._client = None


def test_disabled_when_keys_unset(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    _reset_client()
    assert t.langfuse_enabled() is False


def test_decorator_is_transparent_passthrough_when_disabled(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    _reset_client()

    @t.traced_generation("openai")
    async def fake(*, system, user, model):
        return "ok:" + user

    assert asyncio.run(fake(system="s", user="hello", model="gpt-4o")) == "ok:hello"


def test_decorator_propagates_exceptions_when_disabled(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    _reset_client()

    @t.traced_generation("anthropic")
    async def boom(*, system, user, model):
        raise ValueError("boom")

    try:
        asyncio.run(boom(system="s", user="u", model="m"))
        assert False, "exception should propagate"
    except ValueError as e:
        assert str(e) == "boom"

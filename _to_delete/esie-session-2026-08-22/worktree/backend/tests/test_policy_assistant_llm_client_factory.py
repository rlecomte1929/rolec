"""
Tests for get_default_client() in policy_assistant_llm_client.py.

Regression guard for the silent-fallback incident: when ANTHROPIC_API_KEY
was missing/broken in production, the factory quietly returned MockClient,
whose default response is the verbatim REFUSAL_TEXT. That made a broken key
indistinguishable from a legitimate "out of policy" refusal — and the mock
even echoed the real model id into traces. Result: the Policy Assistant
refused *every* question in prod while looking completely normal.

The fix: in production (RENDER set, or ENV=production), the factory must
FAIL LOUD rather than degrade to canned refusals. Outside production the
mock fallback is preserved (tests + local dev rely on it).
"""
from __future__ import annotations

import pytest

from backend.app.services import policy_assistant_llm_client as C


# All env keys the factory reads — clear them so each test starts clean.
_FACTORY_ENV = ("POLICY_ASSISTANT_LLM", "ANTHROPIC_API_KEY", "RENDER", "ENV")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _FACTORY_ENV:
        monkeypatch.delenv(k, raising=False)
    yield


# --- Non-production: mock fallback preserved -------------------------------

def test_no_key_outside_prod_returns_mock(monkeypatch):
    """Local/dev with no key still degrades to MockClient (unchanged)."""
    client = C.get_default_client()
    assert isinstance(client, C.MockClient)


def test_forced_mock_returns_mock_even_in_prod(monkeypatch):
    """Explicit POLICY_ASSISTANT_LLM=mock is an escape hatch in any env."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("POLICY_ASSISTANT_LLM", "mock")
    assert isinstance(C.get_default_client(), C.MockClient)


# --- Production: fail loud, never silently mock ----------------------------

def test_no_key_in_prod_raises(monkeypatch):
    """RENDER set + no key → RuntimeError, NOT a silent MockClient."""
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        C.get_default_client()


def test_env_production_no_key_raises(monkeypatch):
    """ENV=production + no key → RuntimeError too (RENDER not the only signal)."""
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError):
        C.get_default_client()


def test_broken_client_in_prod_raises(monkeypatch):
    """Key present but AnthropicClient construction fails in prod → raise,
    not fall through to MockClient."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-broken")

    def _boom():
        raise RuntimeError("anthropic package not installed")

    monkeypatch.setattr(C, "AnthropicClient", _boom)
    with pytest.raises(RuntimeError):
        C.get_default_client()


def test_broken_client_outside_prod_still_mocks(monkeypatch):
    """Same broken construction, but local → MockClient fallback preserved."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-broken")

    def _boom():
        raise RuntimeError("anthropic package not installed")

    monkeypatch.setattr(C, "AnthropicClient", _boom)
    assert isinstance(C.get_default_client(), C.MockClient)

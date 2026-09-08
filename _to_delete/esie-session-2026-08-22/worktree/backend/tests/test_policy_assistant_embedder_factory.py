"""
Tests for get_default_embedder() in policy_assistant_embedder.py (W0-1).

Regression guard for the silent-degradation footgun: when OPENAI_API_KEY was
missing/broken in production, the factory quietly returned HashEmbedder, whose
non-semantic vectors get written to and queried against pgvector with NO error.
That silently poisons retrieval — a broken key looks identical to a healthy one.

The fix mirrors the LLM-client factory (see test_policy_assistant_llm_client_factory):
in production (RENDER set, or ENV=production) the embedder factory FAILS LOUD
rather than degrading to the hash embedder. Outside production the hash fallback
is preserved (tests + local dev rely on it). An explicit
POLICY_ASSISTANT_EMBEDDER=hash override opts into hash in any env.
"""
from __future__ import annotations

import pytest

from backend.app.services import policy_assistant_embedder as E


# All env keys the factory reads — clear them so each test starts clean.
_FACTORY_ENV = ("POLICY_ASSISTANT_EMBEDDER", "OPENAI_API_KEY", "RENDER", "ENV")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _FACTORY_ENV:
        monkeypatch.delenv(k, raising=False)
    yield


# --- Non-production: hash fallback preserved -------------------------------

def test_no_key_outside_prod_returns_hash(monkeypatch):
    """Local/dev with no key still degrades to HashEmbedder (unchanged)."""
    assert isinstance(E.get_default_embedder(), E.HashEmbedder)


def test_forced_hash_returns_hash_even_in_prod(monkeypatch):
    """Explicit POLICY_ASSISTANT_EMBEDDER=hash is an escape hatch in any env."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("POLICY_ASSISTANT_EMBEDDER", "hash")
    assert isinstance(E.get_default_embedder(), E.HashEmbedder)


# --- Production: fail loud, never silently hash ----------------------------

def test_no_key_in_prod_raises(monkeypatch):
    """RENDER set + no key → RuntimeError, NOT a silent HashEmbedder."""
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        E.get_default_embedder()


def test_env_production_no_key_raises(monkeypatch):
    """ENV=production + no key → RuntimeError too (RENDER not the only signal)."""
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError):
        E.get_default_embedder()


def test_broken_embedder_in_prod_raises(monkeypatch):
    """Key present but OpenAIEmbedder construction fails in prod → raise,
    not fall through to HashEmbedder."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-broken")

    def _boom():
        raise RuntimeError("openai package not installed")

    monkeypatch.setattr(E, "OpenAIEmbedder", _boom)
    with pytest.raises(RuntimeError):
        E.get_default_embedder()


def test_broken_embedder_outside_prod_still_hashes(monkeypatch):
    """Same broken construction, but local → HashEmbedder fallback preserved."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-broken")

    def _boom():
        raise RuntimeError("openai package not installed")

    monkeypatch.setattr(E, "OpenAIEmbedder", _boom)
    assert isinstance(E.get_default_embedder(), E.HashEmbedder)

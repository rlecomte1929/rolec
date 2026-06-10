"""Tests for E-PIPE-5b entity-resolution AI helpers (embedding + LLM resolver).

OpenAI is never called: the no-key degrade path is exercised directly, and the
client constructor is monkeypatched for the happy paths. Verifies the fail-soft
contract — no key / error → embedding None, verdict no-match — so the resolver
falls back to deterministic stages.
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.relopass.agents.entity_resolution import AnnHit, CanonicalPerson, ExtractedPerson
from backend.app.services import rce_entity_resolution_ai as ai


def _person(**kw):
    base = dict(
        case_id="case-1", surname_main="ERIKSSON", surname_normalized="ERIKSSON",
        given_names_main="Anna Maria", given_names_normalized="ANNA MARIA",
        dob_iso="1974-08-12", nationality_iso3="UTO",
    )
    base.update(kw)
    return ExtractedPerson(**base)


def _hit(cid="ce-1", sim=0.88):
    cp = CanonicalPerson(
        canonical_entity_id=cid, case_id="case-1",
        surname_main="ERIKSON", surname_normalized="ERIKSON",
        given_names_main="Anna", given_names_normalized="ANNA",
        dob_iso="1974-08-12", nationality_iso3="UTO",
    )
    return AnnHit(canonical_entity_id=cid, cosine_sim=sim, canonical=cp)


# ── embed_person_768 ────────────────────────────────────────────────────────────


def test_embed_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ai.embed_person_768(_person()) is None


def test_embed_returns_none_on_api_error(monkeypatch):
    class _Boom:
        @property
        def embeddings(self):
            raise RuntimeError("network down")

    monkeypatch.setattr(ai, "_openai_client", lambda: _Boom())
    assert ai.embed_person_768(_person()) is None


def test_embed_requests_768_dims(monkeypatch):
    captured = {}

    class _Client:
        class embeddings:
            @staticmethod
            def create(model, input, dimensions):
                captured["model"] = model
                captured["dimensions"] = dimensions
                return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 768)])

    monkeypatch.setattr(ai, "_openai_client", lambda: _Client())
    out = ai.embed_person_768(_person())
    assert out == [0.1] * 768
    assert captured["model"] == "text-embedding-3-small"
    assert captured["dimensions"] == 768


# ── OpenAILLMResolver ─────────────────────────────────────────────────────────


def test_resolver_no_match_without_key(monkeypatch):
    monkeypatch.setattr(ai, "_openai_client", lambda: None)
    verdict = ai.OpenAILLMResolver().resolve(_person(), [_hit()])
    assert verdict.match is None
    assert verdict.confidence == 0.0


def test_resolver_no_match_when_no_hits(monkeypatch):
    # Even with a client, an empty hit list short-circuits to no-match.
    monkeypatch.setattr(ai, "_openai_client", lambda: object())
    verdict = ai.OpenAILLMResolver().resolve(_person(), [])
    assert verdict.match is None


def test_resolver_parses_match(monkeypatch):
    import json

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(model, messages, response_format):
                    content = json.dumps({"match": "ce-1", "confidence": 0.91, "reasoning": "same person"})
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setattr(ai, "_openai_client", lambda: _Client())
    verdict = ai.OpenAILLMResolver().resolve(_person(), [_hit()])
    assert verdict.match == "ce-1"
    assert verdict.confidence == 0.91

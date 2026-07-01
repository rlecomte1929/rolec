# WS-C — unit tests for the policy-RAG groundedness gate (deliverable 1).
"""Covers the two behaviors the gate must guarantee:

  * gate OFF (default)  -> an ungrounded answer is returned UNCHANGED (fail-open).
  * gate ON             -> the same ungrounded answer is replaced with the
                            canonical refusal.

Fully offline: the LLM client, retriever, and grounding verifier are all stubbed,
so no network is touched.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.app.services import policy_assistant_rag_engine as engine
from backend.app.services.policy_assistant_rag_engine import REFUSAL_TEXT


class _FakeClient:
    """Minimal LlmClient: always returns a grounded-looking, citing answer."""

    def __init__(self, text: str):
        self._text = text

    def complete(self, req) -> Dict[str, Any]:
        return {
            "text": self._text,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "mock-model",
        }


_CHUNKS: List[Dict[str, Any]] = [
    {
        "id": "h1",
        "chunk_text": "The monthly housing allowance cap is EUR 2,500.",
        "source_type": "company_policy",
        "source_ref": "company_policy.h1",
    }
]

# A well-formed answer that passes _validate_answer (cites a real chunk id).
_ANSWER = "The monthly housing allowance cap is EUR 2,500. [chunk:h1]"


@pytest.fixture
def _patched(monkeypatch):
    """Stub the retriever and force verify_grounding to report 'ungrounded'."""
    monkeypatch.setattr(
        engine.policy_chunk_retriever, "retrieve",
        lambda *, company_id, query, top_k: list(_CHUNKS),
    )
    monkeypatch.setattr(
        engine, "verify_grounding",
        lambda answer_text, chunks, client=None: {
            "verdict": "ungrounded",
            "grounding_score": 0.1,
            "unsupported_claims": ["everything"],
            "verification_skipped": False,
            "model": "mock-verifier",
            "latency_ms": 1,
        },
    )


def _ask():
    return engine.answer_policy_question(
        company_id="acme",
        user_id="u1",
        question="What is the housing cap?",
        client=_FakeClient(_ANSWER),
    )


def test_gate_off_returns_ungrounded_answer_unchanged(_patched, monkeypatch):
    monkeypatch.delenv("POLICY_RAG_GROUNDEDNESS_GATE", raising=False)
    result = _ask()
    assert result["answer_kind"] == "answer"
    assert result["answer_text"] == _ANSWER
    assert result["grounding_verdict"] == "ungrounded"


def test_gate_on_refuses_ungrounded_answer(_patched, monkeypatch):
    monkeypatch.setenv("POLICY_RAG_GROUNDEDNESS_GATE", "1")
    result = _ask()
    assert result["answer_kind"] == "refusal_validation_failed"
    assert result["answer_text"] == REFUSAL_TEXT
    assert result["cited_chunks"] == []


def test_gate_on_low_score_refuses(monkeypatch):
    monkeypatch.setattr(
        engine.policy_chunk_retriever, "retrieve",
        lambda *, company_id, query, top_k: list(_CHUNKS),
    )
    # Verdict is 'grounded' but the score is below the default 0.5 min -> refuse.
    monkeypatch.setattr(
        engine, "verify_grounding",
        lambda answer_text, chunks, client=None: {
            "verdict": "grounded", "grounding_score": 0.2,
            "verification_skipped": False, "latency_ms": 1,
        },
    )
    monkeypatch.setenv("POLICY_RAG_GROUNDEDNESS_GATE", "1")
    result = _ask()
    assert result["answer_kind"] == "refusal_validation_failed"
    assert result["answer_text"] == REFUSAL_TEXT


def test_gate_on_grounded_answer_passes(monkeypatch):
    monkeypatch.setattr(
        engine.policy_chunk_retriever, "retrieve",
        lambda *, company_id, query, top_k: list(_CHUNKS),
    )
    monkeypatch.setattr(
        engine, "verify_grounding",
        lambda answer_text, chunks, client=None: {
            "verdict": "grounded", "grounding_score": 0.9,
            "verification_skipped": False, "latency_ms": 1,
        },
    )
    monkeypatch.setenv("POLICY_RAG_GROUNDEDNESS_GATE", "1")
    result = _ask()
    assert result["answer_kind"] == "answer"
    assert result["answer_text"] == _ANSWER


def test_gate_on_verifier_skipped_fails_open(monkeypatch):
    monkeypatch.setattr(
        engine.policy_chunk_retriever, "retrieve",
        lambda *, company_id, query, top_k: list(_CHUNKS),
    )
    # Verifier errored (verification_skipped) -> must NOT gate even when ON.
    monkeypatch.setattr(
        engine, "verify_grounding",
        lambda answer_text, chunks, client=None: {
            "verdict": None, "grounding_score": None,
            "verification_skipped": True, "latency_ms": 1,
        },
    )
    monkeypatch.setenv("POLICY_RAG_GROUNDEDNESS_GATE", "1")
    result = _ask()
    assert result["answer_kind"] == "answer"
    assert result["answer_text"] == _ANSWER

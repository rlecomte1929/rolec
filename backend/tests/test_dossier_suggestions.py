"""[P3-02 / AIQ-1087] Tests for the RAG dossier suggestion service.

No DB, no network: retrieval is monkeypatched and the LLM is the in-repo
MockClient (which surfaces injected JSON as a tool_use block).
"""
from __future__ import annotations

import json

from backend.app.services import dossier_suggestion_service as svc
from backend.app.services.policy_assistant_llm_client import MockClient


_CHUNKS = [
    {"chunk_id": "us_fr_lsv_passport", "text": "A passport valid 3 months beyond stay is required.",
     "source_url": "https://france-visas.gouv.fr/passport"},
    {"chunk_id": "us_fr_lsv_proof_funds", "text": "Proof of sufficient funds is required for the long-stay visa.",
     "source_url": "https://france-visas.gouv.fr/funds"},
    {"chunk_id": "us_fr_lsv_accommodation", "text": "Proof of accommodation in France is required.",
     "source_url": None},
]


def test_corridor_for_case_builds_iso2_arrow():
    draft = {"relocationBasics": {"originCountry": "United States", "destCountry": "France"}}
    assert svc.corridor_for_case(draft) == "US→FR"
    # ISO2 inputs pass through
    assert svc.corridor_for_case({"relocationBasics": {"originCountry": "IN", "destCountry": "DE"}}) == "IN→DE"
    # missing origin/dest -> None
    assert svc.corridor_for_case({"relocationBasics": {"destCountry": "FR"}}) is None
    assert svc.corridor_for_case({}) is None


def test_happy_path_returns_structured_questions_with_source_ids(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: list(_CHUNKS))
    canned = json.dumps({
        "questions": [
            {"question_text": "Does your passport stay valid 3+ months beyond your visa?",
             "source_ids": ["us_fr_lsv_passport"], "rationale": "passport validity rule"},
            {"question_text": "Can you show proof of sufficient funds?",
             "source_ids": ["us_fr_lsv_proof_funds", "us_fr_lsv_accommodation"], "rationale": "funds + accommodation"},
        ]
    })
    client = MockClient(default_response=canned)

    out = svc.suggest_questions("US→FR", {"relocationBasics": {"purpose": "Employment"}}, client=client)

    assert len(out) == 2
    first = out[0]
    assert first["question_text"].startswith("Does your passport")
    assert first["answer_type"] == "text"
    assert first["sources"] == [{"chunk_id": "us_fr_lsv_passport", "url": "https://france-visas.gouv.fr/passport"}]
    # second question cites two chunks; the URL-less one still maps
    second_ids = {s["chunk_id"] for s in out[1]["sources"]}
    assert second_ids == {"us_fr_lsv_proof_funds", "us_fr_lsv_accommodation"}

    # the LLM prompt included the retrieved chunk texts as context (>=3)
    assert len(client.calls) == 1
    um = client.calls[0].user_message
    assert "us_fr_lsv_passport" in um and "us_fr_lsv_proof_funds" in um and "us_fr_lsv_accommodation" in um


def test_empty_corpus_fallback_returns_empty(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: [])
    client = MockClient(default_response=json.dumps({"questions": [{"question_text": "x", "source_ids": []}]}))
    out = svc.suggest_questions("ZZ→YY", {"relocationBasics": {}}, client=client)
    assert out == []
    # no LLM call when there's no corpus
    assert client.calls == []


def test_no_corridor_returns_empty():
    out = svc.suggest_questions(None, {"relocationBasics": {}})
    assert out == []


def test_malformed_llm_output_is_handled(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: list(_CHUNKS))
    client = MockClient(default_response="not json")  # tool_use parse fails -> None
    out = svc.suggest_questions("US→FR", {"relocationBasics": {}}, client=client)
    assert out == []

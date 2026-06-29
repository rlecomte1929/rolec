"""
Phase 1, Slice 2 — the live-pipeline hooks that feed ai_replay_store.

Asserts that rag_pipeline.generate_roadmap persists exactly one replay record per
generation (feature_key='rag_roadmap'), capturing the result, approval, corridor,
and retrieved chunk ids — for both the OK and the RULE_NOT_FOUND paths. The
retriever boundary is patched with fixtures and the LLM is a MockClient, so the
test is deterministic and needs no DB / ANTHROPIC_API_KEY.

The persist call is captured (not run against a DB) — masking itself is already
covered by test_ai_replay_store.py; here we only verify the wiring passes the
right data.
"""
from __future__ import annotations

import json
import os
import sys
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_LLM"] = "mock"

from backend.app.services import (  # noqa: E402
    immigration_answer_engine,
    immigration_retriever,
    rag_pipeline,
)
from backend.app.services.immigration_retriever import (  # noqa: E402
    PathClassification,
    UserProfile,
)
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402

_TOK_A = "[genA]"

_FR_NO_CHUNKS = [
    {
        "id": "fr-no-eea-01",
        "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
        "chunk_text": "EEA nationals moving to Norway for more than three months must register.",
        "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
        "score": 0.91,
    },
]


def _ok_roadmap_json():
    return json.dumps({
        "result": "OK",
        "corridor": "FR→NO",
        "pathway_type": "eu_free_movement",
        "refusal_reason": None,
        "summary": "Register under the EEA scheme.",
        "steps": [{
            "order": 1,
            "title": f"Complete EEA registration {_TOK_A}",
            "description": "Register with the Norwegian police under the EEA scheme.",
            "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
            "source_chunk_id": "fr-no-eea-01",
            "confidence": "high",
            "requires_expert_review": False,
        }],
    })


def _mock_client():
    return MockClient(responses_by_pattern={
        _TOK_A: json.dumps({"supported": True, "evidence_chunk_ids": ["fr-no-eea-01"], "reason": "ok"}),
        "FR→NO": _ok_roadmap_json(),
    })


def _profile():
    return UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)


def _classification(corridor="FR→NO"):
    return PathClassification(pathway_type="eu_free_movement", corridor=corridor)


def test_ok_roadmap_persists_one_replay_record_with_chunks():
    captured = []
    with mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=_FR_NO_CHUNKS), \
         mock.patch.object(rag_pipeline, "get_default_client", return_value=_mock_client()), \
         mock.patch.object(rag_pipeline, "persist_replay_record",
                           side_effect=lambda **kw: captured.append(kw)):
        result = rag_pipeline.generate_roadmap(profile=_profile(), classification=_classification())

    assert result["result"] == "OK"
    assert len(captured) == 1
    rec = captured[0]
    assert rec["feature_key"] == "rag_roadmap"
    assert rec["corridor"] == "FR→NO"
    assert rec["result"] == "OK"
    assert rec["approved"] is True
    assert rec["retrieved_chunk_ids"] == ["fr-no-eea-01"]
    # The output handed to the store carries the generated steps for grading.
    assert "EEA registration" in json.dumps(rec["output"])


def test_rule_not_found_still_persists_a_replay_record():
    captured = []
    with mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=[]), \
         mock.patch.object(rag_pipeline, "get_default_client", return_value=_mock_client()), \
         mock.patch.object(rag_pipeline, "persist_replay_record",
                           side_effect=lambda **kw: captured.append(kw)):
        result = rag_pipeline.generate_roadmap(
            profile=UserProfile(nationality="JP", origin_country="JP", destination_country="NO", is_eea=False),
            classification=PathClassification(pathway_type="skilled_worker_permit", corridor="JP→NO"),
        )

    assert result["result"] == "RULE_NOT_FOUND"
    assert len(captured) == 1
    rec = captured[0]
    assert rec["feature_key"] == "rag_roadmap"
    assert rec["result"] == "RULE_NOT_FOUND"
    assert rec["approved"] is False
    assert rec["retrieved_chunk_ids"] == []


# --- immigration_answer_engine hook --------------------------------------- #

def _answer_chunk(url="https://www.udi.no/en/want-to-apply/"):
    return {"id": "imm-01", "source_url": url, "source_ref": url,
            "chunk_text": "A residence permit is required for stays over 90 days.",
            "trust_tier": 1, "fetched_at": "2026-06-06T00:00:00+00:00", "corridor": "FR_NO"}


def _answer_payload(chunks):
    return {"chunks": chunks, "all_stale_warning": False,
            "oldest_fetched_at": chunks[0]["fetched_at"] if chunks else None}


def test_immigration_answer_persists_replay_record():
    captured = []
    url = "https://www.udi.no/en/want-to-apply/"
    mockc = MockClient(default_response=f"You need a residence permit [source: {url}].")
    with mock.patch("backend.app.services.ai_trace_logger._write_to_db"), \
         mock.patch.object(immigration_answer_engine, "persist_replay_record",
                           side_effect=lambda **kw: captured.append(kw)):
        res = immigration_answer_engine.generate_immigration_answer(
            _answer_payload([_answer_chunk(url)]), "What documents are required?", "FR→NO", client=mockc)

    assert res["answer_kind"] == "answer"
    assert len(captured) == 1
    rec = captured[0]
    assert rec["feature_key"] == "immigration_answer"
    assert rec["corridor"] == "FR→NO"
    assert rec["result"] == "answer"
    assert rec["retrieved_chunk_ids"] == ["imm-01"]


def test_immigration_answer_refusal_still_persists_replay_record():
    captured = []
    mockc = MockClient(default_response="should never be used")
    with mock.patch("backend.app.services.ai_trace_logger._write_to_db"), \
         mock.patch.object(immigration_answer_engine, "persist_replay_record",
                           side_effect=lambda **kw: captured.append(kw)):
        res = immigration_answer_engine.generate_immigration_answer(
            _answer_payload([]), "anything", "ZZ→XX", client=mockc)

    assert res["answer_kind"] == "refusal_insufficient_context"
    assert len(captured) == 1
    rec = captured[0]
    assert rec["feature_key"] == "immigration_answer"
    assert rec["result"] == "refusal_insufficient_context"
    assert rec["retrieved_chunk_ids"] == []

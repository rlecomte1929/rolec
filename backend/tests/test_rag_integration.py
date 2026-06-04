"""
Golden integration test for the immigration RAG pipeline (P1-01e / AIQ-630).

This is the deterministic regression lock for the whole pipeline
(retriever P1-01a → generator P1-01b → verifier P1-01c → orchestrator P1-01d).
It drives the orchestrator endpoint with the **Marc Bouchard** golden fixture
(FR→NO, EEA free movement), a pinned FR→NO corpus, and pinned mocked LLM
responses, then asserts the assembled CaseRoadmap matches a documented golden
output and conforms to the per-step schema.

Everything is pinned and offline (no network, no ANTHROPIC_API_KEY):
  - `_GOLDEN_FR_NO_CORPUS`     — the retrieved chunks (retriever boundary patched)
  - `_PINNED_GENERATOR_OUTPUT` — the emit_case_roadmap JSON the generator "returns"
  - `_PINNED_VERIFIER_VERDICTS`— the per-step verdicts the verifier "returns"
  - `_GOLDEN_ROADMAP`          — the documented expected pipeline output

The CI `backend-tests` job runs this file (see .github/workflows/ci.yml). The
real-LLM run against the live FR→NO corpus is a nightly/manual step, blocked on
P0-05 corridor ingestion + an API key.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_LLM"] = "mock"

from backend.app.routers import rag_roadmap  # noqa: E402
from backend.app.services import immigration_retriever, rag_pipeline  # noqa: E402
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402

_ADMIN = {"id": "admin-1", "is_admin": True, "role": "ADMIN"}

# Required keys on every emitted step, per the P1-01b emit_case_roadmap schema.
_REQUIRED_STEP_KEYS = {
    "order", "title", "description", "source_url", "source_chunk_id",
    "confidence", "requires_expert_review",
}

# --- Marc Bouchard golden fixture: FR→NO, EEA free movement ------------------

_MARC_BOUCHARD = dict(
    nationality="FR", origin_country="FR", destination_country="NO",
    pathway_type="eu_free_movement", is_eea=True, corridor="FR→NO",
)

_GOLDEN_FR_NO_CORPUS = [
    {
        "id": "fr-no-eea-01",
        "source_ref": "immigration_rule.fr-no-eea-01",
        "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
        "chunk_text": "EEA nationals moving to Norway for more than three months must register with the police under the EEA registration scheme.",
        "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
        "score": 0.91,
    },
    {
        "id": "fr-no-eea-02",
        "source_ref": "immigration_rule.fr-no-eea-02",
        "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
        "chunk_text": "After EEA registration, report the move to the National Registry to receive a national identity number.",
        "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
        "score": 0.88,
    },
]

# Pinned generator output (stands in for the Sonnet emit_case_roadmap tool call).
_PINNED_GENERATOR_OUTPUT = json.dumps({
    "result": "OK",
    "corridor": "FR→NO",
    "pathway_type": "eu_free_movement",
    "refusal_reason": None,
    "summary": "As an EEA national, complete EEA registration with the police, then report the move to the National Registry.",
    "steps": [
        {
            "order": 1,
            "title": "Complete EEA registration with the police",
            "description": "Register under the EEA registration scheme with the Norwegian police for stays over three months.",
            "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
            "source_chunk_id": "fr-no-eea-01",
            "confidence": "high",
            "requires_expert_review": False,
        },
        {
            "order": 2,
            "title": "Report the move to the National Registry",
            "description": "Report the move to Folkeregisteret and attend an ID check to receive a national identity number.",
            "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
            "source_chunk_id": "fr-no-eea-02",
            "confidence": "high",
            "requires_expert_review": False,
        },
    ],
})

# Pinned verifier verdicts, keyed on the per-step "claimed source_chunk_id:"
# line — a string unique to each verifier call that never appears in the
# generator's CONTEXT message (so the MockClient routes generation vs.
# verification unambiguously, and realistic step titles can't collide with
# chunk text).
_PINNED_VERIFIER_VERDICTS = {
    "claimed source_chunk_id: fr-no-eea-01": json.dumps(
        {"supported": True, "evidence_chunk_ids": ["fr-no-eea-01"], "reason": "Chunk states EEA registration is required."}
    ),
    "claimed source_chunk_id: fr-no-eea-02": json.dumps(
        {"supported": True, "evidence_chunk_ids": ["fr-no-eea-02"], "reason": "Chunk states the move must be reported."}
    ),
}

# The documented golden pipeline output (latency_ms is asserted separately — it
# is the only non-deterministic field).
_GOLDEN_ROADMAP = {
    "result": "OK",
    "corridor": "FR→NO",
    "pathway_type": "eu_free_movement",
    "refusal_reason": None,
    "summary": "As an EEA national, complete EEA registration with the police, then report the move to the National Registry.",
    "approved": True,
    "retrieved_chunk_count": 2,
    "steps": [
        {
            "order": 1,
            "title": "Complete EEA registration with the police",
            "description": "Register under the EEA registration scheme with the Norwegian police for stays over three months.",
            "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
            "source_chunk_id": "fr-no-eea-01",
            "confidence": "high",
            "requires_expert_review": False,
            "verification": {"supported": True, "citation_ok": True, "evidence_chunk_ids": ["fr-no-eea-01"]},
        },
        {
            "order": 2,
            "title": "Report the move to the National Registry",
            "description": "Report the move to Folkeregisteret and attend an ID check to receive a national identity number.",
            "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
            "source_chunk_id": "fr-no-eea-02",
            "confidence": "high",
            "requires_expert_review": False,
            "verification": {"supported": True, "citation_ok": True, "evidence_chunk_ids": ["fr-no-eea-02"]},
        },
    ],
}


def _pinned_client():
    """MockClient with the generator output (keyed on the corridor in its
    CONTEXT) and the per-step verifier verdicts (keyed on step titles)."""
    patterns = dict(_PINNED_VERIFIER_VERDICTS)
    # "CONTEXT (retrieved chunks)" appears only in the generator's message,
    # never in a verifier message ("RETRIEVED CHUNKS ...").
    patterns["CONTEXT (retrieved chunks)"] = _PINNED_GENERATOR_OUTPUT
    return MockClient(responses_by_pattern=patterns)


def _run_pipeline(corpus, body):
    client = _pinned_client()
    with mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=corpus), \
         mock.patch.object(rag_pipeline, "get_default_client", return_value=client):
        return rag_roadmap.generate_roadmap(
            body=rag_roadmap.GenerateRoadmapBody(**body), user=_ADMIN
        )


class RagIntegrationGoldenTests(unittest.TestCase):
    def test_marc_bouchard_matches_golden_output(self):
        result = _run_pipeline(_GOLDEN_FR_NO_CORPUS, _MARC_BOUCHARD)

        # latency_ms is the only non-deterministic field.
        self.assertIsInstance(result.pop("latency_ms"), int)
        self.assertEqual(result, _GOLDEN_ROADMAP)

    def test_golden_output_conforms_to_step_schema(self):
        result = _run_pipeline(_GOLDEN_FR_NO_CORPUS, _MARC_BOUCHARD)

        self.assertEqual(result["result"], "OK")
        self.assertTrue(result["approved"])
        self.assertTrue(result["steps"])
        for step in result["steps"]:
            self.assertTrue(_REQUIRED_STEP_KEYS.issubset(step.keys()),
                            f"step missing schema keys: {step}")
            self.assertIn(step["confidence"], {"high", "medium", "low"})
            self.assertTrue(step["source_url"])  # never null on an OK roadmap
            # Verifier confirmed grounding for every released step.
            self.assertTrue(step["verification"]["supported"])
            self.assertTrue(step["verification"]["evidence_chunk_ids"])

    def test_uncovered_corridor_golden_is_rule_not_found(self):
        # Japan→Norway: the retriever covers no chunks → documented refusal.
        result = _run_pipeline([], dict(
            nationality="JP", origin_country="JP", destination_country="NO",
            pathway_type="skilled_worker_permit", is_eea=False, corridor="JP→NO",
        ))
        self.assertEqual(result["result"], "RULE_NOT_FOUND")
        self.assertEqual(result["steps"], [])
        self.assertFalse(result["approved"])
        self.assertEqual(result["retrieved_chunk_count"], 0)
        self.assertIsInstance(result["refusal_reason"], str)


if __name__ == "__main__":
    unittest.main()

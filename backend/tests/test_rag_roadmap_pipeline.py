"""
Pipeline + endpoint tests for the RAG roadmap orchestrator (P1-01d / AIQ-629).

Wires retriever (P1-01a) → generator (P1-01b prompt) → verifier (P1-01c) behind
POST /api/internal/rag/generate-roadmap. Like the rest of the pipeline suite,
this is fully deterministic: the retriever boundary is patched with FR→NO /
JP→NO fixtures and the LLM is a MockClient driven by canned emit_case_roadmap +
verifier-verdict JSON. No network, no ANTHROPIC_API_KEY.

The router handler is invoked directly with a fake admin user — the same
pattern as test_specialist_review_router.py — so no HTTP/auth machinery is
needed. Dual-layer router registration (backend.main + backend.app.main) is
verified separately via the CLAUDE.md route-presence check.

Asserts the P1-01d validation criteria:
  - Marc Bouchard (FR→NO) → complete CaseRoadmap, result=OK, no RULE_NOT_FOUND,
    every step's source_url populated, pipeline approved.
  - JP→NO (uncovered) → RULE_NOT_FOUND, no steps, no LLM call.
  - A step the verifier rejects taints the whole roadmap (approved=False).
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

_FR_NO_CHUNKS = [
    {
        "id": "fr-no-eea-01",
        "source_ref": "immigration_rule.fr-no-eea-01",
        "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
        "chunk_text": "EEA nationals moving to Norway for more than three months must register with the police.",
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

# Sentinel tokens in step titles so the MockClient can key a verifier verdict to
# each step (they never appear in the generator's CONTEXT message).
_TOK_A = "[genA]"
_TOK_B = "[genB]"


def _ok_roadmap_json():
    return json.dumps({
        "result": "OK",
        "corridor": "FR→NO",
        "pathway_type": "eu_free_movement",
        "refusal_reason": None,
        "summary": "Complete EEA registration, then report the move to the National Registry.",
        "steps": [
            {
                "order": 1,
                "title": f"Complete EEA registration {_TOK_A}",
                "description": "Register with the Norwegian police under the EEA scheme.",
                "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
                "source_chunk_id": "fr-no-eea-01",
                "confidence": "high",
                "requires_expert_review": False,
            },
            {
                "order": 2,
                "title": f"Report the move to the National Registry {_TOK_B}",
                "description": "Report to Folkeregisteret and attend an ID check.",
                "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
                "source_chunk_id": "fr-no-eea-02",
                "confidence": "high",
                "requires_expert_review": False,
            },
        ],
    })


def _verdict(supported, evidence):
    return json.dumps({"supported": supported, "evidence_chunk_ids": evidence, "reason": "canned"})


def _mock_client(verdict_b=True, evidence_b=("fr-no-eea-02",)):
    """Generator returns the OK roadmap (keyed on the corridor in its CONTEXT);
    the verifier returns a per-step verdict keyed on the step title token."""
    return MockClient(responses_by_pattern={
        _TOK_A: _verdict(True, ["fr-no-eea-01"]),
        _TOK_B: _verdict(verdict_b, list(evidence_b)),
        "FR→NO": _ok_roadmap_json(),
    })


def _body(**over):
    base = dict(
        nationality="FR", origin_country="FR", destination_country="NO",
        pathway_type="eu_free_movement", is_eea=True, corridor="FR→NO",
    )
    base.update(over)
    return rag_roadmap.GenerateRoadmapBody(**base)


class RagRoadmapPipelineTests(unittest.TestCase):
    def test_fr_no_marc_bouchard_returns_complete_approved_roadmap(self):
        client = _mock_client()
        with mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=_FR_NO_CHUNKS), \
             mock.patch.object(rag_pipeline, "get_default_client", return_value=client):
            result = rag_roadmap.generate_roadmap(body=_body(), user=_ADMIN)

        self.assertEqual(result["result"], "OK")
        self.assertNotEqual(result["result"], "RULE_NOT_FOUND")
        self.assertTrue(result["approved"])
        self.assertEqual(result["retrieved_chunk_count"], 2)
        self.assertEqual(len(result["steps"]), 2)
        for step in result["steps"]:
            self.assertTrue(step["source_url"], "every step must have a source_url")
            self.assertTrue(step["verification"]["supported"])
            self.assertTrue(step["verification"]["evidence_chunk_ids"])

    def test_jp_no_uncovered_returns_rule_not_found_with_no_llm_call(self):
        client = _mock_client()
        with mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=[]), \
             mock.patch.object(rag_pipeline, "get_default_client", return_value=client):
            result = rag_roadmap.generate_roadmap(
                body=_body(nationality="JP", origin_country="JP",
                           pathway_type="skilled_worker_permit", is_eea=False, corridor="JP→NO"),
                user=_ADMIN,
            )

        self.assertEqual(result["result"], "RULE_NOT_FOUND")
        self.assertEqual(result["steps"], [])
        self.assertFalse(result["approved"])
        self.assertEqual(result["retrieved_chunk_count"], 0)
        # Empty context short-circuits the generator → no tokens spent anywhere.
        self.assertEqual(client.calls, [])

    def test_verifier_rejection_taints_whole_roadmap(self):
        # Step 2's verifier verdict says unsupported with no evidence.
        client = _mock_client(verdict_b=False, evidence_b=())
        with mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=_FR_NO_CHUNKS), \
             mock.patch.object(rag_pipeline, "get_default_client", return_value=client):
            result = rag_roadmap.generate_roadmap(body=_body(), user=_ADMIN)

        self.assertEqual(result["result"], "OK")
        self.assertFalse(result["approved"])  # one unsupported step fails the roadmap
        self.assertFalse(result["steps"][1]["verification"]["supported"])
        self.assertTrue(result["steps"][0]["verification"]["supported"])


if __name__ == "__main__":
    unittest.main()

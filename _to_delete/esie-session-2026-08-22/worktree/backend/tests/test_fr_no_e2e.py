"""P2-01e — FR→NO end-to-end: the user-facing GET /api/cases/{id}/roadmap, for an
allowlisted account, returns a complete, citation-backed, confidence-gated AI
roadmap with no RULE_NOT_FOUND. Uncovered corridors fall back to the
deterministic roadmap.

Deterministic like the rest of the RAG suite: the retriever boundary is patched
with FR→NO fixtures and the LLM is a MockClient driven by canned JSON — no
network, no API key. Mirrors test_rag_roadmap_pipeline's fixtures.
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ["POLICY_ASSISTANT_LLM"] = "mock"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.routers import cases_read
from backend.app.services import feature_flags, immigration_retriever, rag_pipeline
from backend.app.services import roadmap_confidence_gate as gate
from backend.app.services.policy_assistant_llm_client import MockClient

_TOK_A, _TOK_B = "[genA]", "[genB]"

_FR_NO_CHUNKS = [
    {"id": "fr-no-eea-01", "source_ref": "immigration_rule.fr-no-eea-01",
     "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
     "chunk_text": "EEA nationals moving to Norway for more than three months must register with the police.",
     "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"}, "score": 0.91},
    {"id": "fr-no-eea-02", "source_ref": "immigration_rule.fr-no-eea-02",
     "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
     "chunk_text": "After EEA registration, report the move to the National Registry for a national identity number.",
     "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"}, "score": 0.88},
]


def _ok_roadmap_json():
    return json.dumps({
        "result": "OK", "corridor": "FR→NO", "pathway_type": "eu_free_movement",
        "refusal_reason": None, "summary": "Register under the EEA scheme, then report the move.",
        "steps": [
            {"order": 1, "title": f"Complete EEA registration {_TOK_A}",
             "description": "Register with the Norwegian police under the EEA scheme.",
             "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
             "source_chunk_id": "fr-no-eea-01", "confidence": "high", "requires_expert_review": False},
            {"order": 2, "title": f"Report the move to the National Registry {_TOK_B}",
             "description": "Report to Folkeregisteret and attend an ID check.",
             "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
             "source_chunk_id": "fr-no-eea-02", "confidence": "high", "requires_expert_review": False},
        ],
    })


def _verdict(supported, evidence):
    return json.dumps({"supported": supported, "evidence_chunk_ids": list(evidence), "reason": "canned"})


def _mock_client():
    return MockClient(responses_by_pattern={
        _TOK_A: _verdict(True, ["fr-no-eea-01"]),
        _TOK_B: _verdict(True, ["fr-no-eea-02"]),
        "FR→NO": _ok_roadmap_json(),
    })


class FrNoEndToEndTests(unittest.TestCase):
    TABLES = [models.RoadmapReviewStatus, models.FeatureFlag, models.FeatureFlagAccount]

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        models.Base.metadata.create_all(self.engine, tables=[t.__table__ for t in self.TABLES])
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(models.FeatureFlag(key=feature_flags.LIVE_EEA_ROADMAP_FLAG, enabled=True))
            db.add(models.FeatureFlagAccount(flag_key=feature_flags.LIVE_EEA_ROADMAP_FLAG, account_id="marc"))
            db.commit()

    def _get_roadmap(self, draft, *, chunks, account="marc"):
        case = SimpleNamespace(status="created", draft_json=json.dumps(draft))
        with mock.patch.object(cases_read, "SessionLocal", self.Session), \
                mock.patch.object(cases_read.crud, "get_case", return_value=case), \
                mock.patch.object(cases_read, "_assert_case_access", lambda *a, **k: None), \
                mock.patch.object(feature_flags, "SessionLocal", self.Session), \
                mock.patch.object(gate, "SessionLocal", self.Session), \
                mock.patch.object(immigration_retriever, "retrieve_for_profile", return_value=chunks), \
                mock.patch.object(rag_pipeline, "get_default_client", return_value=_mock_client()):
            return cases_read.get_case_roadmap("case-1", user={"id": account})

    def test_marc_bouchard_fr_no_complete_citation_backed_roadmap(self):
        draft = {"relocationBasics": {"originCountry": "FR", "destCountry": "NO", "nationality": "FR"}}
        res = self._get_roadmap(draft, chunks=_FR_NO_CHUNKS)

        self.assertEqual(res["result"], "OK")
        self.assertNotEqual(res["result"], "RULE_NOT_FOUND")
        self.assertTrue(res["ai_roadmap_eligible"])
        # Complete: both high-confidence steps shown (not withheld), each cited.
        self.assertEqual(len(res["steps"]), 2)
        for step in res["steps"]:
            self.assertTrue(step["source_url"], "every step must carry a source citation")
        self.assertFalse(res["requires_specialist_review"])  # all HIGH
        self.assertIn("has_stale_sources", res)

    def test_uncovered_corridor_falls_back_to_deterministic(self):
        # JP→NO: retriever returns nothing → pipeline RULE_NOT_FOUND → fall back.
        draft = {"relocationBasics": {"originCountry": "JP", "destCountry": "NO", "nationality": "JP"}}
        res = self._get_roadmap(draft, chunks=[])
        self.assertNotIn("result", res)            # deterministic roadmap, not the AI shape
        self.assertNotIn("ai_roadmap_eligible", res)


if __name__ == "__main__":
    unittest.main()

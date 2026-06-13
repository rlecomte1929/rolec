"""AIQ-1003 (follow-up to #687) — the generator must unwrap the tool-call envelope.

#687 fixed max_tokens + a balanced-brace JSON extractor, but still read top-level
``result``. The prompt is authored for tool-use and its exemplars emit
``{"name": "emit_case_roadmap", "input": {result, steps, ...}}``; run through the
no-tools text seam the model echoes that envelope, so ``result`` lives under
``input`` → "invalid roadmap shape" refusal. These tests drive the REAL
generate() with the envelope shape (the existing suite never did).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import roadmap_generator  # noqa: E402
from backend.app.services.immigration_retriever import PathClassification, UserProfile  # noqa: E402
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402

_CHUNKS = [{
    "id": "fr-no-eea-01",
    "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
    "chunk_text": "EEA nationals moving to Norway for >3 months must register with the police.",
    "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
    "score": 0.9,
}]
_PROFILE = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
_CLASS = PathClassification(pathway_type="eu_free_movement", corridor="FR→NO")
_INPUT = {
    "result": "OK", "corridor": "FR→NO", "pathway_type": "eu_free_movement",
    "refusal_reason": None, "summary": "Register under the EEA scheme.",
    "steps": [{
        "order": 1, "title": "Complete EEA registration",
        "description": "Register under the EEA scheme with the Norwegian police.",
        "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
        "source_chunk_id": "fr-no-eea-01", "confidence": "high", "requires_expert_review": False,
    }],
}


def _gen(text: str):
    client = MockClient(responses_by_pattern={"FR→NO": text}, default_response="{}")
    return roadmap_generator.generate(profile=_PROFILE, classification=_CLASS, chunks=_CHUNKS, client=client)


class RoadmapEnvelopeTests(unittest.TestCase):
    def test_tool_call_envelope_unwrapped_to_OK(self):
        res = _gen(json.dumps({"name": "emit_case_roadmap", "input": _INPUT}))
        self.assertEqual(res.roadmap["result"], "OK")
        self.assertEqual(len(res.roadmap["steps"]), 1)
        self.assertEqual(res.roadmap["steps"][0]["source_chunk_id"], "fr-no-eea-01")

    def test_fenced_envelope_unwrapped(self):
        res = _gen("```json\n" + json.dumps({"name": "emit_case_roadmap", "input": _INPUT}) + "\n```")
        self.assertEqual(res.roadmap["result"], "OK")
        self.assertEqual(len(res.roadmap["steps"]), 1)

    def test_bare_object_still_parses(self):
        res = _gen(json.dumps(_INPUT))
        self.assertEqual(res.roadmap["result"], "OK")
        self.assertEqual(len(res.roadmap["steps"]), 1)

    def test_rule_not_found_envelope_refuses_no_steps(self):
        rnf = {"name": "emit_case_roadmap", "input": {
            "result": "RULE_NOT_FOUND", "corridor": "FR→NO", "pathway_type": "eu_free_movement",
            "refusal_reason": "uncovered", "summary": None, "steps": []}}
        res = _gen(json.dumps(rnf))
        self.assertEqual(res.roadmap["result"], "RULE_NOT_FOUND")
        self.assertEqual(res.roadmap["steps"], [])


if __name__ == "__main__":
    unittest.main()

"""AIQ-1003 — roadmap generator must parse the tool-call envelope the prompt emits.

The generator prompt is authored for Anthropic tool-use; its exemplars show the
model emitting ``{"name": "emit_case_roadmap", "input": {...}}``. But the
generator calls the LLM with NO tools (text seam), so the model echoes that
envelope as text. The original `_parse_roadmap` read top-level ``result`` →
which lives under ``input`` → so EVERY corridor fell through to a RULE_NOT_FOUND
refusal ("malformed roadmap JSON" / "invalid roadmap shape").

These tests drive the REAL `roadmap_generator.generate()` (the existing
test_roadmap_generator_prompt.py never did — it parsed canned text itself, which
is why the bug shipped) via a MockClient returning the envelope shape.
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

_CHUNKS = [
    {
        "id": "fr-no-eea-01",
        "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
        "chunk_text": "EEA nationals moving to Norway for >3 months must register with the police.",
        "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
        "score": 0.9,
    },
]
_PROFILE = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
_CLASS = PathClassification(pathway_type="eu_free_movement", corridor="FR→NO")

_INPUT_OBJ = {
    "result": "OK",
    "corridor": "FR→NO",
    "pathway_type": "eu_free_movement",
    "refusal_reason": None,
    "summary": "Register with the police under the EEA scheme.",
    "steps": [
        {
            "order": 1,
            "title": "Complete EEA registration",
            "description": "Register under the EEA scheme with the Norwegian police.",
            "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
            "source_chunk_id": "fr-no-eea-01",
            "confidence": "high",
            "requires_expert_review": False,
        }
    ],
}


def _gen(canned_text: str):
    client = MockClient(responses_by_pattern={"FR→NO": canned_text}, default_response="{}")
    return roadmap_generator.generate(
        profile=_PROFILE, classification=_CLASS, chunks=_CHUNKS, client=client
    )


class RoadmapEnvelopeParseTests(unittest.TestCase):
    def test_tool_call_envelope_is_unwrapped_to_OK(self):
        # The exact shape the prompt's exemplars emit — the bug repro.
        envelope = json.dumps({"name": "emit_case_roadmap", "input": _INPUT_OBJ})
        res = _gen(envelope)
        self.assertEqual(res.roadmap["result"], "OK")
        self.assertEqual(res.roadmap["corridor"], "FR→NO")
        self.assertEqual(len(res.roadmap["steps"]), 1)
        self.assertEqual(res.roadmap["steps"][0]["source_chunk_id"], "fr-no-eea-01")

    def test_bare_object_still_parses(self):
        res = _gen(json.dumps(_INPUT_OBJ))
        self.assertEqual(res.roadmap["result"], "OK")
        self.assertEqual(len(res.roadmap["steps"]), 1)

    def test_fenced_envelope_parses(self):
        fenced = "```json\n" + json.dumps({"name": "emit_case_roadmap", "input": _INPUT_OBJ}) + "\n```"
        res = _gen(fenced)
        self.assertEqual(res.roadmap["result"], "OK")
        self.assertEqual(len(res.roadmap["steps"]), 1)

    def test_rule_not_found_envelope_refuses_with_no_steps(self):
        rnf = json.dumps({"name": "emit_case_roadmap", "input": {
            "result": "RULE_NOT_FOUND", "corridor": "FR→NO", "pathway_type": "eu_free_movement",
            "refusal_reason": "uncovered", "summary": None, "steps": []}})
        res = _gen(rnf)
        self.assertEqual(res.roadmap["result"], "RULE_NOT_FOUND")
        self.assertEqual(res.roadmap["steps"], [])

    def test_truly_malformed_output_still_refuses(self):
        res = _gen("I'm sorry, I cannot produce that.")
        self.assertEqual(res.roadmap["result"], "RULE_NOT_FOUND")
        self.assertTrue(res.roadmap["refusal_reason"])

    def test_empty_chunks_short_circuits_without_llm(self):
        client = MockClient(default_response="{}")
        res = roadmap_generator.generate(
            profile=_PROFILE, classification=_CLASS, chunks=[], client=client
        )
        self.assertEqual(res.roadmap["result"], "RULE_NOT_FOUND")
        self.assertFalse(res.called_llm)
        self.assertEqual(len(client.calls), 0)


if __name__ == "__main__":
    unittest.main()

"""
Deterministic validation for the roadmap generator prompt (P1-01b / AIQ-627).

`prompts/roadmap_generator_v1.txt` is the generation stage of the immigration
RAG pipeline: it turns the chunks returned by `immigration_retriever` (P1-01a)
into a schema-valid CaseRoadmap, and refuses with the RULE_NOT_FOUND sentinel
when the corridor is uncovered.

The real FR→NO corpus does not exist in the repo yet (blocked on P0-05), so —
exactly like test_immigration_retriever.py — this test does NOT call a live
LLM. Instead it:

  1. Loads the prompt file and asserts the contract it documents is internally
     consistent (the tool name, the RULE_NOT_FOUND sentinel, the per-step
     source_url / confidence / requires_expert_review fields all present).
  2. Builds the CONTEXT user message the way the orchestrator (P1-01d) will,
     from deterministic fixture chunks shaped like immigration_retriever output.
  3. Drives a MockClient (the same test seam used across the policy_assistant
     suite) with canned `emit_case_roadmap` tool-call JSON, and validates the
     output against the schema the prompt declares:
        - FR→NO (populated context) → result=OK, ≥1 step, every step's
          source_url copied from a supplied chunk, no fabricated citations.
        - JP→NO (empty context)     → result=RULE_NOT_FOUND, steps == [], no
          hallucinated steps.

Live-corpus runs (5×FR→NO + 1×JP→NO against claude-sonnet-4-6) are a reviewer
step documented in prompts/roadmap_generator_v1.eval.md.

No network, no ANTHROPIC_API_KEY required.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_retriever import (  # noqa: E402
    PathClassification,
    UserProfile,
    corridor_key,
)
from backend.app.services.policy_assistant_llm_client import (  # noqa: E402
    LlmRequest,
    MockClient,
)

_PROMPT_PATH = os.path.join(_REPO_ROOT, "prompts", "roadmap_generator_v1.txt")

# Required keys on every step object, per the prompt's tool-use schema.
_REQUIRED_STEP_KEYS = {
    "order",
    "title",
    "description",
    "source_url",
    "source_chunk_id",
    "confidence",
    "requires_expert_review",
}


# --- Fixture chunks, shaped like immigration_retriever.retrieve_for_profile() output ---

_FR_NO_CHUNKS = [
    {
        "id": "fr-no-eea-01",
        "source_ref": "immigration_rule.fr-no-eea-01",
        "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
        "chunk_text": (
            "EEA nationals moving to Norway for more than three months must "
            "register with the police under the EEA registration scheme."
        ),
        "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
        "score": 0.91,
    },
    {
        "id": "fr-no-eea-02",
        "source_ref": "immigration_rule.fr-no-eea-02",
        "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
        "chunk_text": (
            "After EEA registration, report the move to the National Registry "
            "and attend an ID check to receive a national identity number."
        ),
        "chunk_metadata": {"corridor": "FR→NO", "pathway_type": "eu_free_movement"},
        "score": 0.88,
    },
]

# JP→NO: the retriever returns an empty list for an uncovered corridor.
_JP_NO_CHUNKS: list = []


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _build_context_message(profile: UserProfile, classification: PathClassification, chunks) -> str:
    """Mirror how the orchestrator (P1-01d) will render the CONTEXT block."""
    corridor = classification.corridor or corridor_key(
        profile.origin_country, profile.destination_country
    )
    lines = [
        "SUBJECT:",
        f"  profile: nationality={profile.nationality}, origin={profile.origin_country}, "
        f"destination={profile.destination_country}, is_eea={str(profile.is_eea).lower()}",
        f"  classification: pathway_type={classification.pathway_type}, corridor={corridor}",
        "",
        "CONTEXT (retrieved chunks):",
    ]
    if not chunks:
        lines.append("  (empty — the retriever returned no chunks for this corridor)")
    else:
        for c in chunks:
            lines.append(
                f"  [chunk:{c['id']}] (source_url: {c['source_url']})\n    {c['chunk_text']}"
            )
    return "\n".join(lines)


def _canned_ok_roadmap(corridor: str, chunks) -> str:
    """A schema-shaped emit_case_roadmap tool-call JSON for a covered corridor,
    citing only the supplied chunks. Stands in for the model's output."""
    steps = [
        {
            "order": i + 1,
            "title": f"Step {i + 1}",
            "description": "Action grounded in the cited chunk.",
            "source_url": c["source_url"],
            "source_chunk_id": c["id"],
            "confidence": "high",
            "requires_expert_review": False,
        }
        for i, c in enumerate(chunks)
    ]
    return json.dumps(
        {
            "result": "OK",
            "corridor": corridor,
            "pathway_type": "eu_free_movement",
            "refusal_reason": None,
            "summary": "EEA registration then National Registry move report.",
            "steps": steps,
        }
    )


def _canned_rule_not_found(corridor: str) -> str:
    return json.dumps(
        {
            "result": "RULE_NOT_FOUND",
            "corridor": corridor,
            "pathway_type": "skilled_worker_permit",
            "refusal_reason": f"No retrieved immigration rules cover the {corridor} corridor.",
            "summary": None,
            "steps": [],
        }
    )


class RoadmapGeneratorPromptContractTests(unittest.TestCase):
    """The prompt file must document the contract this pipeline relies on."""

    def setUp(self):
        self.prompt = _load_prompt()

    def test_prompt_file_exists_and_nonempty(self):
        self.assertTrue(os.path.isfile(_PROMPT_PATH))
        self.assertGreater(len(self.prompt), 1000)

    def test_declares_emit_case_roadmap_tool(self):
        self.assertIn('"name": "emit_case_roadmap"', self.prompt)
        self.assertIn('"input_schema"', self.prompt)

    def test_declares_rule_not_found_sentinel(self):
        self.assertIn("RULE_NOT_FOUND", self.prompt)
        # The guard must instruct an empty steps array on refusal.
        self.assertIn("steps` to `[]`", self.prompt)

    def test_declares_per_step_citation_fields(self):
        for field in ("source_url", "confidence", "requires_expert_review"):
            self.assertIn(field, self.prompt, f"prompt missing step field {field}")

    def test_forbids_free_text_and_cross_corridor_substitution(self):
        lower = self.prompt.lower()
        self.assertIn("never reply in free text", lower)
        self.assertIn("never substitute another corridor", lower)

    def test_tool_schema_is_valid_json(self):
        # Extract the first ```json ... ``` fenced block that contains the tool.
        blocks = re.findall(r"```json\s*(\{.*?\})\s*```", self.prompt, re.DOTALL)
        tool_blocks = [b for b in blocks if '"emit_case_roadmap"' in b]
        self.assertTrue(tool_blocks, "no emit_case_roadmap json block found")
        schema = json.loads(tool_blocks[0])
        self.assertEqual(schema["name"], "emit_case_roadmap")
        props = schema["input_schema"]["properties"]
        self.assertEqual(set(props["result"]["enum"]), {"OK", "RULE_NOT_FOUND"})
        step_props = set(props["steps"]["items"]["properties"])
        self.assertTrue(_REQUIRED_STEP_KEYS.issubset(step_props))


class RoadmapGeneratorBehaviourTests(unittest.TestCase):
    """Drive a MockClient with canned tool-call JSON and validate the output
    against the schema the prompt declares — the deterministic stand-in for the
    live FR→NO / JP→NO runs that are blocked on P0-05."""

    def setUp(self):
        self.system = _load_prompt()
        self.marc = UserProfile(
            nationality="FR", origin_country="FR", destination_country="NO", is_eea=True
        )
        self.marc_path = PathClassification(pathway_type="eu_free_movement", corridor="FR→NO")
        self.taro = UserProfile(
            nationality="JP", origin_country="JP", destination_country="NO", is_eea=False
        )
        self.taro_path = PathClassification(
            pathway_type="skilled_worker_permit", corridor="JP→NO"
        )

    def _run(self, profile, classification, chunks, canned_text):
        client = MockClient(
            responses_by_pattern={classification.corridor: canned_text},
            default_response="{}",
        )
        user_message = _build_context_message(profile, classification, chunks)
        resp = client.complete(
            LlmRequest(system=self.system, user_message=user_message, temperature=0.0)
        )
        # The MockClient hands back the canned tool-call JSON as `text`.
        return json.loads(resp["text"]), client

    def _assert_step_schema(self, step):
        self.assertTrue(_REQUIRED_STEP_KEYS.issubset(step.keys()))
        self.assertIn(step["confidence"], ("high", "medium", "low"))
        self.assertIsInstance(step["requires_expert_review"], bool)
        self.assertTrue(step["source_url"])  # non-null, non-empty

    def test_fr_no_produces_schema_valid_case_roadmap(self):
        roadmap, _ = self._run(
            self.marc,
            self.marc_path,
            _FR_NO_CHUNKS,
            _canned_ok_roadmap("FR→NO", _FR_NO_CHUNKS),
        )
        self.assertEqual(roadmap["result"], "OK")
        self.assertEqual(roadmap["corridor"], "FR→NO")
        self.assertIsNone(roadmap["refusal_reason"])
        self.assertGreaterEqual(len(roadmap["steps"]), 1)

        allowed_urls = {c["source_url"] for c in _FR_NO_CHUNKS}
        allowed_ids = {c["id"] for c in _FR_NO_CHUNKS}
        for step in roadmap["steps"]:
            self._assert_step_schema(step)
            # Every citation must trace to a supplied chunk — no fabrication.
            self.assertIn(step["source_url"], allowed_urls)
            self.assertIn(step["source_chunk_id"], allowed_ids)

    def test_fr_no_context_message_includes_only_fr_no_chunks(self):
        msg = _build_context_message(self.marc, self.marc_path, _FR_NO_CHUNKS)
        self.assertIn("FR→NO", msg)
        self.assertIn("fr-no-eea-01", msg)
        self.assertNotIn("JP→NO", msg)

    def test_jp_no_returns_rule_not_found_with_no_steps(self):
        roadmap, _ = self._run(
            self.taro,
            self.taro_path,
            _JP_NO_CHUNKS,
            _canned_rule_not_found("JP→NO"),
        )
        self.assertEqual(roadmap["result"], "RULE_NOT_FOUND")
        self.assertEqual(roadmap["corridor"], "JP→NO")
        # The whole point of the guard: zero hallucinated steps.
        self.assertEqual(roadmap["steps"], [])
        self.assertTrue(roadmap["refusal_reason"])

    def test_jp_no_context_message_is_empty_corpus(self):
        msg = _build_context_message(self.taro, self.taro_path, _JP_NO_CHUNKS)
        self.assertIn("empty", msg.lower())
        self.assertNotIn("[chunk:", msg)

    def test_system_prompt_was_passed_to_client(self):
        _, client = self._run(
            self.marc,
            self.marc_path,
            _FR_NO_CHUNKS,
            _canned_ok_roadmap("FR→NO", _FR_NO_CHUNKS),
        )
        self.assertEqual(len(client.calls), 1)
        self.assertIn("emit_case_roadmap", client.calls[0].system)


if __name__ == "__main__":
    unittest.main()

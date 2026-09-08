"""
Deterministic tests for the factual verifier (P1-01c / AIQ-628).

`factual_verifier` is the third stage of the immigration RAG pipeline: it
re-checks every generated roadmap step against the *actual* retrieved chunks
with a second Claude pass, so a fabricated or unsupported step never reaches a
caseworker.

Like test_immigration_retriever.py (P1-01a) and test_roadmap_generator_prompt.py
(P1-01b), this does NOT call a live LLM. It drives a MockClient (the
policy_assistant test seam) with canned verdict JSON keyed by a sentinel token
in each step's title, and asserts the verifier's two contractual guarantees:

  - A deliberately injected hallucinated step (no source) is flagged
    supported=false, and the roadmap is not approved.
  - Legitimate steps are marked supported=true with non-empty
    evidence_chunk_ids.

Plus the safety properties the implementation adds: evidence ids are filtered
to real retrieved chunks (the verifier can't invent support), an empty chunk
set short-circuits without an LLM call, and citation_ok is a deterministic
lookup independent of the LLM.

No network, no ANTHROPIC_API_KEY required.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force the mock LLM client so nothing tries to reach Anthropic.
os.environ["POLICY_ASSISTANT_LLM"] = "mock"

from backend.app.services import factual_verifier  # noqa: E402
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402


# --- Fixtures: chunks shaped like immigration_retriever.retrieve_for_profile() ---

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

# Sentinel tokens embedded in step titles so the MockClient can key a canned
# verdict to each step. Chosen not to collide with any chunk text.
_TOK_LEGIT_A = "[stepA]"
_TOK_LEGIT_B = "[stepB]"
_TOK_HALLUC = "[stepH]"
_TOK_GHOST = "[stepG]"


def _legit_steps():
    return [
        {
            "order": 1,
            "title": f"Complete EEA registration {_TOK_LEGIT_A}",
            "description": "Register with the Norwegian police under the EEA scheme.",
            "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
            "source_chunk_id": "fr-no-eea-01",
            "confidence": "high",
            "requires_expert_review": False,
        },
        {
            "order": 2,
            "title": f"Report the move to the National Registry {_TOK_LEGIT_B}",
            "description": "Report to Folkeregisteret and attend an ID check.",
            "source_url": "https://www.skatteetaten.no/en/person/national-registry/moving/",
            "source_chunk_id": "fr-no-eea-02",
            "confidence": "high",
            "requires_expert_review": False,
        },
    ]


def _hallucinated_step():
    """A fabricated step with no source — the canonical thing the verifier
    must catch."""
    return {
        "order": 3,
        "title": f"Pay the mandatory relocation tax {_TOK_HALLUC}",
        "description": "Pay a 5% relocation tax to the Norwegian tax office.",
        "source_url": "",
        "source_chunk_id": "",
        "confidence": "high",
        "requires_expert_review": False,
    }


def _verdict_json(supported, evidence_chunk_ids, reason="canned"):
    return json.dumps(
        {"supported": supported, "evidence_chunk_ids": evidence_chunk_ids, "reason": reason}
    )


def _mock_client():
    """MockClient that returns a supporting verdict for each legit step, an
    unsupported verdict for the hallucinated step, and (for the ghost case) a
    verdict citing a chunk id that was never retrieved."""
    return MockClient(
        responses_by_pattern={
            _TOK_LEGIT_A: _verdict_json(True, ["fr-no-eea-01"]),
            _TOK_LEGIT_B: _verdict_json(True, ["fr-no-eea-02"]),
            _TOK_HALLUC: _verdict_json(False, [], reason="No chunk mentions a relocation tax."),
            _TOK_GHOST: _verdict_json(True, ["ghost-chunk-999"]),
        },
        # Default (no pattern match) is non-JSON → exercises the unparseable path.
        default_response="I cannot find this in the retrieved chunks.",
    )


class FactualVerifierTests(unittest.TestCase):
    # --- Validation Criterion 2: legitimate steps get non-empty evidence ---

    def test_legitimate_steps_have_nonempty_evidence(self):
        result = factual_verifier.verify_roadmap(
            steps=_legit_steps(), chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        self.assertTrue(result.approved)
        self.assertEqual(len(result.verdicts), 2)
        for v in result.verdicts:
            self.assertTrue(v.supported, f"{v.title} should be supported")
            self.assertTrue(v.citation_ok, f"{v.title} cites a real chunk")
            self.assertTrue(v.evidence_chunk_ids, f"{v.title} must have evidence")

    # --- Validation Criterion 1: injected hallucinated step → supported=false ---

    def test_injected_hallucinated_step_is_flagged_unsupported(self):
        steps = _legit_steps() + [_hallucinated_step()]
        result = factual_verifier.verify_roadmap(
            steps=steps, chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        # One bad step taints the whole roadmap.
        self.assertFalse(result.approved)

        halluc = result.verdicts[-1]
        self.assertFalse(halluc.supported)
        self.assertFalse(halluc.citation_ok)  # no source → fails deterministic check
        self.assertEqual(halluc.evidence_chunk_ids, [])
        self.assertEqual([v for v in result.unsupported], [halluc])

    # --- Safety: the verifier cannot invent support from an unretrieved chunk ---

    def test_fabricated_evidence_id_is_filtered_out(self):
        ghost_step = {
            "order": 1,
            "title": f"Step citing a non-existent chunk {_TOK_GHOST}",
            "description": "Claims grounding in a chunk that was never retrieved.",
            "source_url": "https://example.test/ghost",
            "source_chunk_id": "ghost-chunk-999",
            "confidence": "high",
            "requires_expert_review": False,
        }
        verdict = factual_verifier.verify_step(
            step=ghost_step, chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        # The LLM "supported" it citing ghost-chunk-999, but that id was never
        # retrieved → filtered out → no real evidence → not supported.
        self.assertEqual(verdict.evidence_chunk_ids, [])
        self.assertFalse(verdict.supported)
        self.assertFalse(verdict.citation_ok)

    # --- Safety: empty chunk set short-circuits without an LLM call ---

    def test_empty_chunks_short_circuits_without_llm_call(self):
        client = _mock_client()
        verdict = factual_verifier.verify_step(
            step=_legit_steps()[0], chunks=[], client=client
        )
        self.assertFalse(verdict.supported)
        self.assertFalse(verdict.citation_ok)
        self.assertEqual(verdict.evidence_chunk_ids, [])
        self.assertEqual(client.calls, [])  # no tokens spent

    # --- citation_ok is a deterministic lookup, independent of the LLM ---

    def test_citation_ok_requires_real_chunk_and_matching_url(self):
        # Real id + matching url → ok.
        good = factual_verifier.verify_step(
            step=_legit_steps()[0], chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        self.assertTrue(good.citation_ok)

        # Real id but mismatched url → not ok.
        bad_url = dict(_legit_steps()[0])
        bad_url["source_url"] = "https://wrong.example/url"
        bad_url["title"] = f"mismatched url {_TOK_LEGIT_A}"
        verdict = factual_verifier.verify_step(
            step=bad_url, chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        self.assertFalse(verdict.citation_ok)

    def test_unparseable_verdict_is_treated_as_unsupported(self):
        # Title has no sentinel token → MockClient returns its non-JSON default.
        step = {
            "order": 1,
            "title": "Some step with no canned verdict",
            "description": "x",
            "source_url": "https://www.udi.no/en/word-definitions/eea-registration/",
            "source_chunk_id": "fr-no-eea-01",
            "confidence": "high",
            "requires_expert_review": False,
        }
        verdict = factual_verifier.verify_step(
            step=step, chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        self.assertFalse(verdict.supported)
        self.assertEqual(verdict.evidence_chunk_ids, [])
        # citation_ok is still computed deterministically.
        self.assertTrue(verdict.citation_ok)

    def test_empty_roadmap_is_vacuously_approved(self):
        result = factual_verifier.verify_roadmap(
            steps=[], chunks=_FR_NO_CHUNKS, client=_mock_client()
        )
        self.assertTrue(result.approved)
        self.assertEqual(result.verdicts, [])


if __name__ == "__main__":
    unittest.main()

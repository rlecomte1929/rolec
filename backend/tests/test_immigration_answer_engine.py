"""
N4 / AIQ-843 — tests for the grounded immigration answer engine + endpoint.

LLM is mocked (MockClient). The ai_trace_logger DB write is patched to a no-op
so the prod-pointed .env is never written to. No network, no Anthropic key.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_answer_engine import (
    INSUFFICIENT_CONTEXT_REFUSAL,
    _LOW_CONFIDENCE_CAVEAT,
    generate_immigration_answer,
)
from backend.app.services.policy_assistant_llm_client import MockClient

_TRACE_WRITE = "backend.app.services.ai_trace_logger._write_to_db"


def _chunk(url, text="A residence permit is required.", tier=1, fetched="2026-06-06T00:00:00+00:00"):
    return {"source_url": url, "source_ref": url, "chunk_text": text,
            "trust_tier": tier, "fetched_at": fetched, "corridor": "FR_NO"}


def _payload(chunks, all_stale=False):
    return {
        "chunks": chunks,
        "all_stale_warning": all_stale,
        "oldest_fetched_at": chunks[0]["fetched_at"] if chunks else None,
    }


class AnswerEngineTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch(_TRACE_WRITE)   # never write traces to the prod-pointed DB
        p.start()
        self.addCleanup(p.stop)

    def test_answer_with_citations(self):
        url = "https://www.udi.no/en/want-to-apply/"
        mockc = MockClient(default_response=f"You need a residence permit [source: {url}].")
        res = generate_immigration_answer(_payload([_chunk(url)]), "What documents are required?", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "answer")
        self.assertGreaterEqual(len(res["cited_sources"]), 1)
        self.assertEqual(res["cited_sources"][0]["source_url"], url)        # criterion #4
        self.assertEqual(res["cited_sources"][0]["trust_tier"], 1)
        self.assertEqual(res["model"], "claude-sonnet-4-6")
        self.assertTrue(res["trace_id"])
        # 2 calls: generation + the N5/AIQ-844 grounding verifier (reuses the same
        # mock, which returns non-JSON -> verifier fails open, answer untouched).
        self.assertEqual(len(mockc.calls), 2)

    def test_zero_chunks_refuses_without_llm_call(self):
        mockc = MockClient(default_response="should never be used")
        res = generate_immigration_answer(_payload([]), "anything", "ZZ→XX", client=mockc)
        self.assertEqual(res["answer_kind"], "refusal_insufficient_context")
        self.assertEqual(res["cost_usd"], 0.0)
        self.assertEqual(res["answer_text"], INSUFFICIENT_CONTEXT_REFUSAL)
        self.assertEqual(len(mockc.calls), 0)                               # NO LLM call (criterion #2)
        self.assertTrue(res["trace_id"])                                    # still traced

    def test_all_stale_answer_carries_caveat_and_hint(self):
        url = "https://gov.example/x"
        caveat = "⚠️ Note: The available sources may be outdated. Please verify."
        mockc = MockClient(default_response=f"{caveat} You need X [source: {url}].")
        res = generate_immigration_answer(_payload([_chunk(url)], all_stale=True), "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "answer")                      # answer with caveat (not refusal)
        self.assertIn("⚠️ Note:", res["answer_text"])                       # criterion #3
        self.assertIn("potentially outdated", mockc.calls[0].system)        # our code injected the stale hint

    def test_all_stale_refusal_is_classified_stale(self):
        mockc = MockClient(default_response=INSUFFICIENT_CONTEXT_REFUSAL)
        res = generate_immigration_answer(_payload([_chunk("https://gov.example/x")], all_stale=True), "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "refusal_stale_sources")

    def test_refusal_passthrough_when_not_stale(self):
        mockc = MockClient(default_response=INSUFFICIENT_CONTEXT_REFUSAL)
        res = generate_immigration_answer(_payload([_chunk("https://gov.example/x")]), "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "refusal_insufficient_context")

    @staticmethod
    def _scored(url, text, tier, fetched, score=0.8):
        return {"source_url": url, "source_ref": url, "chunk_text": text,
                "trust_tier": tier, "fetched_at": fetched, "adjusted_score": score, "corridor": "FR_NO"}

    def test_contradiction_fields_in_trace_and_lower_trust_dropped(self):
        # N7 criterion #4: conflicts_detected/conflicts_resolved surface in the trace;
        # the suppressed (lower-authority) source is dropped from the generation prompt.
        a = self._scored("https://a.example/visa", "Processing time is 4 weeks.", 2, "2026-06-06T00:00:00+00:00")
        b = self._scored("https://udi.no/permit", "Processing time is 12 weeks.", 1, "2026-06-01T00:00:00+00:00")
        mockc = MockClient(
            responses_by_pattern={"PASSAGE A": '{"conflict": true, "topic": "t", "chunk_a_claim": "4w", "chunk_b_claim": "12w"}'},
            default_response="Processing time is 12 weeks [source: https://udi.no/permit].",
        )
        res = generate_immigration_answer(_payload([a, b]), "How long?", "FR→NO", client=mockc)
        self.assertEqual(res["conflicts_detected"], 1)
        self.assertEqual(res["conflicts_resolved"], 1)
        self.assertFalse(res["contradiction_check_skipped"])
        # The generation call carries the QUESTION (unlike the pair checks or the
        # AIQ-844 grounding-verifier call that share this client).
        gen_call = next(c for c in mockc.calls if "QUESTION:" in c.user_message)
        self.assertNotIn("https://a.example/visa", gen_call.user_message)   # tier-2 suppressed
        self.assertIn("https://udi.no/permit", gen_call.user_message)       # tier-1 kept

    def test_two_official_conflict_injects_escalation_note(self):
        a = self._scored("https://udi.no/a", "Processing time is 4 weeks.", 1, "2026-06-06T00:00:00+00:00")
        b = self._scored("https://politiet.no/b", "Processing time is 12 weeks.", 1, "2026-06-06T00:00:00+00:00")
        mockc = MockClient(
            responses_by_pattern={"PASSAGE A": '{"conflict": true, "topic": "t", "chunk_a_claim": "4w", "chunk_b_claim": "12w"}'},
            default_response="Sources differ [source: https://udi.no/a][source: https://politiet.no/b].",
        )
        res = generate_immigration_answer(_payload([a, b]), "How long?", "FR→NO", client=mockc)
        gen_call = next(c for c in mockc.calls if "QUESTION:" in c.user_message)
        self.assertIn("CONFLICTING OFFICIAL SOURCES", gen_call.system)      # escalation note injected
        self.assertEqual(res["conflicts_resolved"], 0)                     # neither suppressed
        self.assertIn("https://udi.no/a", gen_call.user_message)
        self.assertIn("https://politiet.no/b", gen_call.user_message)

    def test_confidence_higher_for_confirmed_than_secondary_only(self):
        # N9 criterion #4: a confirmed-agreement answer outscores a secondary-only one.
        def _answer(agreement):
            ch = {**_chunk("https://x.example/a"), "source_agreement": agreement}
            mockc = MockClient(default_response="A residence permit is required [source: https://x.example/a].")
            return generate_immigration_answer(_payload([ch]), "q", "FR→NO", client=mockc)

        confirmed = _answer("confirmed")
        secondary = _answer("secondary_only")
        # N6/AIQ-845: the raw agreement float moved into confidence_factors (the
        # headline `confidence` is now N6's calibrated enum). The N9 ordering holds there.
        self.assertGreater(
            confirmed["confidence_factors"]["source_agreement"],
            secondary["confidence_factors"]["source_agreement"],
        )
        self.assertEqual(confirmed["source_agreement_summary"], {"confirmed": 1})

    def test_stale_refusal_with_caveat_prefix_is_classified_stale(self):
        # Regression: a stale refusal is prefixed with the "⚠️ Note:" caveat, so
        # the refusal sentence is NOT at the start — must still be detected.
        text = ("⚠️ Note: The available sources may be outdated. Please verify. "
                + INSUFFICIENT_CONTEXT_REFUSAL)
        mockc = MockClient(default_response=text)
        res = generate_immigration_answer(_payload([_chunk("https://gov.example/x")], all_stale=True),
                                          "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "refusal_stale_sources")

    def test_response_surfaces_staleness_fields(self):
        url = "https://gov.example/x"
        mockc = MockClient(default_response=f"You need X [source: {url}].")
        res = generate_immigration_answer(_payload([_chunk(url)], all_stale=True), "q", "FR→NO", client=mockc)
        self.assertTrue(res["all_stale_warning"])
        self.assertEqual(res["oldest_fetched_at"], "2026-06-06T00:00:00+00:00")
        self.assertIn("truncated", res)

    def test_fabricated_citation_is_dropped(self):
        # Citation-enforced: a [source: url] not in the provided chunks is ungrounded.
        real = "https://gov.example/real"
        mockc = MockClient(default_response="You need X [source: https://gov.example/FABRICATED].")
        res = generate_immigration_answer(_payload([_chunk(real)]), "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "answer")
        self.assertEqual(res["cited_sources"], [])  # fabricated source not surfaced

    def test_empty_answer_is_refusal(self):
        mockc = MockClient(default_response="")
        res = generate_immigration_answer(_payload([_chunk("https://gov.example/x")]), "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "refusal_insufficient_context")
        self.assertEqual(res["answer_text"], INSUFFICIENT_CONTEXT_REFUSAL)


class ConfidenceScoringTests(unittest.TestCase):
    """N6/AIQ-845 — calibrated confidence band + factors + low-confidence caveat."""

    def setUp(self):
        p = mock.patch(_TRACE_WRITE)
        self.mock_write = p.start()
        self.addCleanup(p.stop)

    def _run(self, adj_scores, grounding, all_stale=False):
        urls = [f"https://x.example/{i}" for i in range(len(adj_scores))]
        chunks = [{**_chunk(u), "adjusted_score": a} for u, a in zip(urls, adj_scores)]
        answer = "You need a permit " + " ".join(f"[source: {u}]" for u in urls) + "."
        gen = MockClient(default_response=answer)
        ver = MockClient(default_response='{"verdict": "grounded", "unsupported_claims": [], '
                         f'"grounding_score": {grounding}}}')
        return generate_immigration_answer(
            _payload(chunks, all_stale=all_stale), "q", "FR→NO", client=gen, verifier_client=ver)

    def test_criterion1_2_high_confidence(self):
        # avg_adjusted=0.85, grounding=0.9, citation=3, not stale -> high
        res = self._run([0.85, 0.85, 0.85], 0.9)
        self.assertIn(res["confidence"], ["high", "medium", "low"])   # criterion 1
        self.assertEqual(res["confidence"], "high")                   # criterion 2

    def test_criterion3_stale_is_low_with_caveat(self):
        res = self._run([0.9], 0.9, all_stale=True)
        self.assertEqual(res["confidence"], "low")
        self.assertIn(_LOW_CONFIDENCE_CAVEAT, res["answer_text"])     # mandatory caveat

    def test_low_grounding_is_low(self):
        res = self._run([0.85], 0.3)                                  # grounding < 0.5
        self.assertEqual(res["confidence"], "low")

    def test_medium_when_neither_high_nor_low(self):
        # avg 0.6 (not <0.5, not >=0.75), grounding ok, citation 1 (<2) -> medium
        res = self._run([0.6], 0.85)
        self.assertEqual(res["confidence"], "medium")

    def test_criterion4_confidence_factors_present(self):
        res = self._run([0.85, 0.85], 0.9)
        f = res["confidence_factors"]
        for k in ("avg_retrieval_score", "grounding_score", "citation_count", "has_stale_sources"):
            self.assertIn(k, f)
            self.assertIsNotNone(f[k])
        self.assertAlmostEqual(f["avg_retrieval_score"], 0.85, places=3)
        self.assertEqual(f["citation_count"], 2)
        self.assertFalse(f["has_stale_sources"])

    def test_criterion5_confidence_in_trace(self):
        self._run([0.85, 0.85], 0.9)
        payload = self.mock_write.call_args.args[0]
        conf_steps = [s for s in payload["steps"] if "confidence" in s]
        self.assertTrue(conf_steps, "no trace step carried confidence")
        self.assertIn(conf_steps[0]["confidence"], ["high", "medium", "low"])

    def test_refusal_is_low_confidence(self):
        res = generate_immigration_answer(_payload([]), "q", "ZZ→XX",
                                          client=MockClient(default_response="unused"))
        self.assertEqual(res["confidence"], "low")
        self.assertIn("confidence_factors", res)


if __name__ == "__main__":
    unittest.main()

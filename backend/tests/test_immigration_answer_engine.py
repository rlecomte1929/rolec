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
    _calibrated_confidence,
    generate_immigration_answer,
)
from backend.app.services.policy_assistant_llm_client import MockClient

_TRACE_WRITE = "backend.app.services.ai_trace_logger._write_to_db"


def _scored_chunk(score, **kw):
    return {"source_url": "https://gov.example/x", "source_ref": "https://gov.example/x",
            "chunk_text": "A residence permit is required for stays over 90 days.",
            "trust_tier": 1, "fetched_at": "2026-06-06T00:00:00+00:00", "corridor": "FR_NO",
            "adjusted_score": score, **kw}


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
        # N6/AIQ-845 made `confidence` the calibrated enum; N9's float is now agreement_confidence.
        self.assertGreater(confirmed["agreement_confidence"], secondary["agreement_confidence"])
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


class CalibratedConfidenceTests(unittest.TestCase):
    # --- the pure formula (N6 derivation) ---
    def test_high_when_strong_fresh_grounded_cited(self):
        level, factors = _calibrated_confidence(
            [_scored_chunk(0.8), _scored_chunk(0.9)], grounding_score=0.9, citation_count=3, all_stale=False)
        self.assertEqual(level, "high")
        self.assertAlmostEqual(factors["avg_retrieval_score"], 0.85, places=2)
        self.assertEqual(factors["grounding_score"], 0.9)
        self.assertEqual(factors["citation_count"], 3)
        self.assertFalse(factors["has_stale_sources"])

    def test_low_when_all_stale(self):
        level, _ = _calibrated_confidence([_scored_chunk(0.9)], grounding_score=0.9, citation_count=3, all_stale=True)
        self.assertEqual(level, "low")

    def test_low_when_grounding_below_half(self):
        level, _ = _calibrated_confidence([_scored_chunk(0.9)], grounding_score=0.4, citation_count=3, all_stale=False)
        self.assertEqual(level, "low")

    def test_low_when_retrieval_below_half(self):
        level, _ = _calibrated_confidence([_scored_chunk(0.4)], grounding_score=0.9, citation_count=3, all_stale=False)
        self.assertEqual(level, "low")

    def test_medium_otherwise(self):
        level, _ = _calibrated_confidence([_scored_chunk(0.6)], grounding_score=0.7, citation_count=2, all_stale=False)
        self.assertEqual(level, "medium")

    def test_grounding_none_coerced_to_zero_is_low(self):
        level, factors = _calibrated_confidence([_scored_chunk(0.9)], grounding_score=None, citation_count=3, all_stale=False)
        self.assertEqual(level, "low")
        self.assertEqual(factors["grounding_score"], 0.0)   # non-null per criterion 4


class AnswerConfidenceIntegrationTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch(_TRACE_WRITE)
        p.start()
        self.addCleanup(p.stop)

    def test_response_has_confidence_enum_and_factors(self):
        # Criterion 1 + 4: confidence in enum; confidence_factors has the 4 non-null keys.
        mockc = MockClient(default_response="A residence permit is required [source: https://gov.example/x].")
        res = generate_immigration_answer(_payload([_scored_chunk(0.6)]), "q", "FR→NO", client=mockc)
        self.assertIn(res["confidence"], ["high", "medium", "low"])
        f = res["confidence_factors"]
        for key in ("avg_retrieval_score", "grounding_score", "citation_count", "has_stale_sources"):
            self.assertIn(key, f)
            self.assertIsNotNone(f[key])

    def test_stale_answer_is_low_with_mandatory_caveat(self):
        # Criterion 3: all_stale → confidence='low' AND the caveat is in answer_text.
        mockc = MockClient(default_response="⚠️ Note: ... You need a permit [source: https://gov.example/x].")
        res = generate_immigration_answer(_payload([_scored_chunk(0.9)], all_stale=True), "q", "FR→NO", client=mockc)
        self.assertEqual(res["confidence"], "low")
        self.assertIn(_LOW_CONFIDENCE_CAVEAT, res["answer_text"])

    def test_strong_grounded_answer_is_high(self):
        # Criterion 2: high retrieval + grounding + citations + fresh → high.
        from backend.app.services import immigration_answer_engine as eng
        mockc = MockClient(
            default_response="Permit required [source: https://a.example/1][source: https://b.example/2].")
        chunks = [_scored_chunk(0.85, source_url="https://a.example/1", source_ref="https://a.example/1"),
                  _scored_chunk(0.85, source_url="https://b.example/2", source_ref="https://b.example/2")]
        verdict = {"verdict": "grounded", "grounding_score": 0.9, "unsupported_claims": [],
                   "verification_skipped": False, "latency_ms": 0}
        with mock.patch.object(eng, "verify_grounding", return_value=verdict):
            res = generate_immigration_answer(_payload(chunks), "q", "FR→NO", client=mockc)
        self.assertEqual(res["confidence"], "high")
        self.assertGreaterEqual(len(res["cited_sources"]), 2)

    def test_verification_skipped_surfaces_unverified_caveat(self):
        # W0-3: when the grounding verifier fails open (skipped), the answer is
        # not silently passed as verified — it carries the flag AND a visible
        # "pending review" caveat, while still being served (fail-open kept).
        from backend.app.services import immigration_answer_engine as eng
        mockc = MockClient(default_response="Permit required [source: https://a.example/1].")
        chunks = [_scored_chunk(0.85, source_url="https://a.example/1", source_ref="https://a.example/1")]
        skipped = {"verdict": None, "grounding_score": None, "unsupported_claims": [],
                   "verification_skipped": True, "latency_ms": 0}
        with mock.patch.object(eng, "verify_grounding", return_value=skipped):
            res = generate_immigration_answer(_payload(chunks), "q", "FR→NO", client=mockc)
        self.assertEqual(res["answer_kind"], "answer")          # not blocked
        self.assertTrue(res["verification_skipped"])             # flag surfaced
        self.assertIn(eng._UNVERIFIED_CAVEAT, res["answer_text"])  # visible to consumers

    def test_verified_answer_has_no_unverified_caveat(self):
        # Negative: a successfully verified answer must NOT carry the caveat.
        from backend.app.services import immigration_answer_engine as eng
        mockc = MockClient(default_response="Permit required [source: https://a.example/1].")
        chunks = [_scored_chunk(0.85, source_url="https://a.example/1", source_ref="https://a.example/1")]
        verdict = {"verdict": "grounded", "grounding_score": 0.9, "unsupported_claims": [],
                   "verification_skipped": False, "latency_ms": 0}
        with mock.patch.object(eng, "verify_grounding", return_value=verdict):
            res = generate_immigration_answer(_payload(chunks), "q", "FR→NO", client=mockc)
        self.assertFalse(res["verification_skipped"])
        self.assertNotIn(eng._UNVERIFIED_CAVEAT, res["answer_text"])


class CitedChunkIdRecordingTests(unittest.TestCase):
    """N8-FU/AIQ-856 — the engine records the immigration_corpus_chunks ids it cited
    onto the trace (producer side of the N8 reliability loop)."""

    def _chunk_with_id(self, url, cid):
        return {**_chunk(url), "id": cid, "adjusted_score": 0.8}

    def test_only_cited_chunk_ids_recorded_on_trace(self):
        url_a, url_b = "https://gov.example/a", "https://gov.example/b"
        chunks = [self._chunk_with_id(url_a, "chunk-a"), self._chunk_with_id(url_b, "chunk-b")]
        # the answer cites only url_a
        gen = MockClient(default_response=f"You need a permit [source: {url_a}].")
        with mock.patch(_TRACE_WRITE) as mock_write:
            res = generate_immigration_answer(_payload(chunks), "q", "FR→NO", client=gen)
        self.assertEqual(res["answer_kind"], "answer")
        payload = mock_write.call_args.args[0]
        # only the CITED chunk's id is recorded (not every retrieved chunk)
        self.assertEqual(payload["cited_chunk_ids"], ["chunk-a"])

    def test_zero_chunks_records_no_citations(self):
        gen = MockClient(default_response="unused")
        with mock.patch(_TRACE_WRITE) as mock_write:
            generate_immigration_answer(_payload([]), "q", "ZZ→XX", client=gen)
        self.assertEqual(mock_write.call_args.args[0]["cited_chunk_ids"], [])


if __name__ == "__main__":
    unittest.main()

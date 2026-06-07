"""
N5 / AIQ-844 — tests for the self-critique grounding verifier and its wiring into
the immigration answer engine.

LLM is mocked (MockClient + a raising client for the fail-open path). The
ai_trace_logger DB write is patched to a no-op (and captured) so the prod-pointed
.env is never written to. No network, no Anthropic key.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from statistics import median
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_answer_engine import (
    INSUFFICIENT_CONTEXT_REFUSAL,
    _PARTIALLY_GROUNDED_CAVEAT,
    generate_immigration_answer,
)
from backend.app.services.immigration_answer_verifier import (
    VERIFIER_MODEL,
    _parse_verdict,
    verify_grounding,
)
from backend.app.services.policy_assistant_llm_client import LlmRequest, MockClient

_TRACE_WRITE = "backend.app.services.ai_trace_logger._write_to_db"

_URL = "https://www.udi.no/en/want-to-apply/"


def _chunk(url=_URL, text="A residence permit is required.", tier=1,
           fetched="2026-06-06T00:00:00+00:00"):
    # adjusted_score is always present on real retriever chunks; include it so the N6
    # confidence band (#454) doesn't read these fixtures as artificially low-confidence
    # and append the caveat (which broke these passthrough assertions on main).
    return {"source_url": url, "source_ref": url, "chunk_text": text,
            "trust_tier": tier, "fetched_at": fetched, "corridor": "FR_NO", "adjusted_score": 0.8}


def _payload(chunks):
    return {"chunks": chunks, "all_stale_warning": False,
            "oldest_fetched_at": chunks[0]["fetched_at"] if chunks else None}


def _gen(answer):
    """Generation client that returns a fixed answer."""
    return MockClient(default_response=answer)


def _verifier(verdict_json):
    """Verifier client that returns a fixed JSON verdict string."""
    return MockClient(default_response=verdict_json)


class _RaisingClient:
    """Stand-in for an LLM timeout / transport error on the verifier call."""
    name = "raising"

    def __init__(self):
        self.calls = []

    def complete(self, req):  # noqa: D401 - mimics LlmClient.complete
        self.calls.append(req)
        raise TimeoutError("verifier timed out")


class _SlowClient:
    """Verifier with a fixed simulated model latency, to measure added overhead."""
    name = "slow"

    def __init__(self, delay, verdict_json):
        self.delay = delay
        self._verdict = verdict_json
        self.calls = []

    def complete(self, req):
        self.calls.append(req)
        time.sleep(self.delay)
        return {"text": self._verdict, "model": req.model, "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 10}}


# --------------------------------------------------------------------------- #
# verify_grounding() unit behavior                                            #
# --------------------------------------------------------------------------- #


class VerifierUnitTests(unittest.TestCase):
    def test_grounded_verdict_parsed(self):
        ver = _verifier('{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 0.95}')
        res = verify_grounding("You need a residence permit.", [_chunk()], client=ver)
        self.assertEqual(res["verdict"], "grounded")
        self.assertAlmostEqual(res["grounding_score"], 0.95)
        self.assertFalse(res["verification_skipped"])
        self.assertEqual(res["unsupported_claims"], [])
        # Verifier must use the cheap/fast model, not the generator's.
        self.assertEqual(ver.calls[0].model, VERIFIER_MODEL)
        self.assertEqual(VERIFIER_MODEL, "claude-haiku-4-5-20251001")

    def test_unparseable_output_fails_open(self):
        ver = _verifier("sorry, I am not sure how to answer that.")
        res = verify_grounding("X", [_chunk()], client=ver)
        self.assertTrue(res["verification_skipped"])
        self.assertIsNone(res["verdict"])

    def test_llm_error_fails_open(self):
        bad = _RaisingClient()
        res = verify_grounding("X", [_chunk()], client=bad)
        self.assertTrue(res["verification_skipped"])
        self.assertIsNone(res["verdict"])
        self.assertEqual(len(bad.calls), 1)

    def test_empty_inputs_skip_without_calling(self):
        ver = _verifier('{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 1.0}')
        self.assertTrue(verify_grounding("", [_chunk()], client=ver)["verification_skipped"])
        self.assertTrue(verify_grounding("X", [], client=ver)["verification_skipped"])
        self.assertEqual(len(ver.calls), 0)  # no LLM call when nothing to verify

    def test_parse_verdict_tolerates_prose_and_fences(self):
        wrapped = ('Here is the result:\n```json\n'
                   '{"verdict": "partially_grounded", "unsupported_claims": ["the 90-day figure"], '
                   '"grounding_score": 0.6}\n```')
        parsed = _parse_verdict(wrapped)
        self.assertEqual(parsed["verdict"], "partially_grounded")
        self.assertEqual(parsed["unsupported_claims"], ["the 90-day figure"])
        self.assertAlmostEqual(parsed["grounding_score"], 0.6)

    def test_parse_verdict_rejects_invalid_verdict(self):
        self.assertIsNone(_parse_verdict('{"verdict": "maybe", "grounding_score": 0.5}'))

    def test_non_dict_response_fails_open_not_closed(self):
        # A client returning a non-dict must NOT raise — the parse is inside the guard.
        class _BadShapeClient:
            name = "badshape"

            def __init__(self):
                self.calls = []

            def complete(self, req):
                self.calls.append(req)
                return "not a dict"  # resp.get(...) would AttributeError

        res = verify_grounding("X", [_chunk()], client=_BadShapeClient())
        self.assertTrue(res["verification_skipped"])
        self.assertIsNone(res["verdict"])

    def test_out_of_range_score_is_clamped(self):
        self.assertEqual(
            _parse_verdict('{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 5.0}')["grounding_score"],
            1.0,
        )
        self.assertEqual(
            _parse_verdict('{"verdict": "ungrounded", "unsupported_claims": [], "grounding_score": -3}')["grounding_score"],
            0.0,
        )


# --------------------------------------------------------------------------- #
# Engine integration                                                          #
# --------------------------------------------------------------------------- #


class EngineVerifierIntegrationTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch(_TRACE_WRITE)   # never write traces to the prod-pointed DB
        self.mock_write = p.start()
        self.addCleanup(p.stop)

    def _run(self, answer, verdict_json):
        return generate_immigration_answer(
            _payload([_chunk()]), "What documents are required?", "FR→NO",
            client=_gen(answer), verifier_client=_verifier(verdict_json),
        )

    def test_grounded_answer_passes_through_unchanged(self):
        # Criterion 1: a directly-quoted answer scores >= 0.8 and is returned as-is.
        answer = f"A residence permit is required [source: {_URL}]."
        res = self._run(answer, '{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 0.9}')
        self.assertEqual(res["answer_kind"], "answer")
        self.assertEqual(res["answer_text"], answer)
        self.assertEqual(res["grounding_verdict"], "grounded")
        self.assertGreaterEqual(res["grounding_score"], 0.8)
        self.assertFalse(res["verification_skipped"])
        self.assertEqual(len(res["cited_sources"]), 1)

    def test_ungrounded_answer_is_replaced_with_refusal(self):
        # Criterion 2: a fabricated claim -> ungrounded -> endpoint returns a refusal.
        answer = f"You must pay a 5000 EUR bond [source: {_URL}]."
        res = self._run(answer, '{"verdict": "ungrounded", "unsupported_claims": ["5000 EUR bond"], "grounding_score": 0.1}')
        self.assertEqual(res["answer_kind"], "refusal_ungrounded")
        self.assertEqual(res["answer_text"], INSUFFICIENT_CONTEXT_REFUSAL)
        self.assertEqual(res["cited_sources"], [])
        self.assertEqual(res["grounding_verdict"], "ungrounded")
        # The fabricated claim must NOT be echoed on the response (it would re-surface
        # the suppressed hallucination)...
        self.assertEqual(res["unsupported_claims"], [])
        self.assertIsNone(res["grounding_score"])
        # ...but it MUST remain in the trace step for auditing.
        trace_steps = self.mock_write.call_args.args[0]["steps"]
        gv = next(s for s in trace_steps if "grounding_verdict" in s)
        self.assertEqual(gv["grounding_verdict"], "ungrounded")
        self.assertIn("5000 EUR bond", gv["unsupported_claims"])

    def test_partially_grounded_answer_gets_caveat(self):
        answer = f"A residence permit is required within 90 days [source: {_URL}]."
        res = self._run(answer, '{"verdict": "partially_grounded", "unsupported_claims": ["90 days"], "grounding_score": 0.6}')
        self.assertEqual(res["answer_kind"], "answer")
        self.assertTrue(res["answer_text"].startswith(answer))
        self.assertTrue(res["answer_text"].endswith(_PARTIALLY_GROUNDED_CAVEAT))
        self.assertEqual(res["grounding_verdict"], "partially_grounded")

    def test_grounding_verdict_is_in_the_trace(self):
        # Criterion 3: grounding_verdict present in the flushed trace `steps`.
        answer = f"A residence permit is required [source: {_URL}]."
        self._run(answer, '{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 0.9}')
        self.assertTrue(self.mock_write.called)
        payload = self.mock_write.call_args.args[0]
        steps = payload["steps"]
        gv_steps = [s for s in steps if "grounding_verdict" in s]
        self.assertTrue(gv_steps, "no trace step carried grounding_verdict")
        self.assertEqual(gv_steps[0]["grounding_verdict"], "grounded")

    def test_verifier_timeout_returns_original_answer_skipped(self):
        # Criterion 4: a verifier timeout sets verification_skipped and keeps the answer.
        answer = f"A residence permit is required [source: {_URL}]."
        res = generate_immigration_answer(
            _payload([_chunk()]), "q", "FR→NO",
            client=_gen(answer), verifier_client=_RaisingClient(),
        )
        self.assertEqual(res["answer_kind"], "answer")
        # Fail-open keeps the original answer; N6 (#454) treats a skipped verifier as
        # low-confidence and appends its caveat, so check the answer is preserved
        # (contained), not byte-identical.
        self.assertIn(answer, res["answer_text"])
        self.assertTrue(res["verification_skipped"])
        self.assertIsNone(res["grounding_verdict"])

    def test_refusal_is_not_verified(self):
        # A generator refusal never triggers a verifier call (grounded by construction).
        ver = _verifier('{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 1.0}')
        res = generate_immigration_answer(
            _payload([_chunk()]), "q", "FR→NO",
            client=_gen(INSUFFICIENT_CONTEXT_REFUSAL), verifier_client=ver,
        )
        self.assertEqual(res["answer_kind"], "refusal_insufficient_context")
        self.assertEqual(len(ver.calls), 0)
        self.assertFalse(res["verification_skipped"])

    def test_zero_chunks_response_carries_verification_fields(self):
        res = generate_immigration_answer(_payload([]), "q", "ZZ→XX", client=_gen("unused"))
        for field in ("grounding_verdict", "grounding_score", "unsupported_claims", "verification_skipped"):
            self.assertIn(field, res)

    def test_verifier_synchronous_latency_is_bounded(self):
        # Criterion 5: the verifier runs synchronously and adds bounded latency.
        # Simulate a fixed verifier model latency; assert the engine incurs it
        # exactly once (sync) and stays well under the 2s budget. A double-call or
        # an async leak would blow one of the bounds — so this isn't tautological.
        SLOW = 0.2
        answer = f"A residence permit is required [source: {_URL}]."
        verdict = '{"verdict": "grounded", "unsupported_claims": [], "grounding_score": 0.9}'
        durations = []
        for _ in range(3):
            slow = _SlowClient(SLOW, verdict)
            t0 = time.perf_counter()
            res = generate_immigration_answer(
                _payload([_chunk()]), "q", "FR→NO", client=_gen(answer), verifier_client=slow,
            )
            durations.append(time.perf_counter() - t0)
            self.assertEqual(len(slow.calls), 1)        # exactly one synchronous verifier call
            self.assertFalse(res["verification_skipped"])
        med = median(durations)
        self.assertGreaterEqual(med, SLOW)              # the verifier latency is actually incurred
        self.assertLess(med, SLOW + 1.0)                # engine overhead small; no second call
        self.assertLess(med, 2.0)                       # within the criterion-5 budget


if __name__ == "__main__":
    unittest.main()

"""
N7 / AIQ-846 — tests for the immigration contradiction detector.

LLM is mocked (MockClient keyed by chunk-text substring). No network, no key.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_contradiction_detector import (
    detect_and_resolve_conflicts,
)
from backend.app.services.policy_assistant_llm_client import MockClient

_NO_CONFLICT = '{"conflict": false, "topic": "", "chunk_a_claim": "", "chunk_b_claim": ""}'
_CONFLICT = (
    '{"conflict": true, "topic": "processing time", '
    '"chunk_a_claim": "4 weeks", "chunk_b_claim": "12 weeks"}'
)


def _chunk(url, text, tier, fetched, score=0.8):
    return {
        "chunk_id": url,
        "source_url": url,
        "source_ref": url,
        "chunk_text": text,
        "trust_tier": tier,
        "fetched_at": fetched,
        "adjusted_score": score,
        "corridor": "FR_NO",
    }


def _conflict_client():
    # Any pair whose user message contains "4 weeks" is reported as a conflict.
    return MockClient(responses_by_pattern={"4 weeks": _CONFLICT}, default_response=_NO_CONFLICT)


class _BoomClient:
    name = "boom"

    def __init__(self):
        self.calls = []

    def complete(self, req):
        self.calls.append(req)
        raise TimeoutError("simulated LLM timeout")


class ContradictionDetectorTests(unittest.TestCase):
    def test_conflicting_processing_times_detected_and_lower_trust_suppressed(self):
        # Criterion 1 + 2: conflict detected; higher-authority (lower trust_tier) kept.
        a = _chunk("https://a.example/visa", "Processing time is 4 weeks.", tier=2, fetched="2026-06-06T00:00:00+00:00")
        b = _chunk("https://udi.no/permit", "Processing time is 12 weeks.", tier=1, fetched="2026-06-01T00:00:00+00:00")
        res = detect_and_resolve_conflicts([a, b], client=_conflict_client())

        self.assertEqual(res["conflicts_detected"], 1)
        self.assertEqual(res["conflicts_resolved"], 1)
        kept = {c["source_url"] for c in res["kept_chunks"]}
        self.assertIn("https://udi.no/permit", kept)          # tier 1 kept
        self.assertNotIn("https://a.example/visa", kept)      # tier 2 suppressed
        self.assertEqual(len(res["suppressed_chunks"]), 1)
        self.assertTrue(res["suppressed_chunks"][0]["conflict_suppressed"])

    def test_equal_tier_resolves_by_freshness(self):
        # Same trust tier → more recent fetched_at wins.
        a = _chunk("https://a.example/visa", "Processing time is 4 weeks.", tier=2, fetched="2026-06-06T00:00:00+00:00")
        b = _chunk("https://b.example/visa", "Processing time is 12 weeks.", tier=2, fetched="2026-05-01T00:00:00+00:00")
        res = detect_and_resolve_conflicts([a, b], client=_conflict_client())
        kept = {c["source_url"] for c in res["kept_chunks"]}
        self.assertIn("https://a.example/visa", kept)         # newer kept
        self.assertNotIn("https://b.example/visa", kept)      # older suppressed

    def test_two_tier1_same_date_conflict_escalates_keeps_both(self):
        # Criterion 3: two tier_1 sources, same fetched_at → both kept, escalation noted.
        a = _chunk("https://udi.no/a", "Processing time is 4 weeks.", tier=1, fetched="2026-06-06T00:00:00+00:00")
        b = _chunk("https://politiet.no/b", "Processing time is 12 weeks.", tier=1, fetched="2026-06-06T00:00:00+00:00")
        res = detect_and_resolve_conflicts([a, b], client=_conflict_client())

        self.assertEqual(res["conflicts_detected"], 1)
        self.assertEqual(res["conflicts_resolved"], 0)
        self.assertEqual(len(res["escalations"]), 1)
        kept = {c["source_url"] for c in res["kept_chunks"]}
        self.assertEqual(kept, {"https://udi.no/a", "https://politiet.no/b"})  # both kept
        self.assertEqual(res["suppressed_chunks"], [])

    def test_no_conflict_passes_through_unchanged(self):
        # Criterion 5: no conflict → all chunks pass through, not skipped.
        a = _chunk("https://a.example/visa", "A residence permit is required.", tier=1, fetched="2026-06-06T00:00:00+00:00")
        b = _chunk("https://b.example/visa", "Bring your passport and photos.", tier=1, fetched="2026-06-06T00:00:00+00:00")
        client = _conflict_client()
        res = detect_and_resolve_conflicts([a, b], client=client)

        self.assertEqual(res["conflicts_detected"], 0)
        self.assertEqual(len(res["kept_chunks"]), 2)
        self.assertEqual(res["suppressed_chunks"], [])
        self.assertFalse(res["contradiction_check_skipped"])

    def test_low_score_pairs_are_not_compared(self):
        # adjusted_score < 0.4 → pair skipped (no LLM call, no false positive).
        a = _chunk("https://a.example/visa", "Processing time is 4 weeks.", tier=2, fetched="2026-06-06T00:00:00+00:00", score=0.3)
        b = _chunk("https://udi.no/permit", "Processing time is 12 weeks.", tier=1, fetched="2026-06-01T00:00:00+00:00", score=0.9)
        client = _conflict_client()
        res = detect_and_resolve_conflicts([a, b], client=client)
        self.assertEqual(res["conflicts_detected"], 0)
        self.assertEqual(len(client.calls), 0)

    def test_fail_open_on_llm_timeout(self):
        # Criterion 6: LLM error → fail open, all chunks pass, flagged skipped.
        a = _chunk("https://a.example/visa", "Processing time is 4 weeks.", tier=2, fetched="2026-06-06T00:00:00+00:00")
        b = _chunk("https://udi.no/permit", "Processing time is 12 weeks.", tier=1, fetched="2026-06-01T00:00:00+00:00")
        res = detect_and_resolve_conflicts([a, b], client=_BoomClient())

        self.assertTrue(res["contradiction_check_skipped"])
        self.assertEqual(res["conflicts_detected"], 0)
        self.assertEqual(len(res["kept_chunks"]), 2)

    def test_empty_and_single_chunk_are_noops(self):
        self.assertEqual(detect_and_resolve_conflicts([], client=_conflict_client())["kept_chunks"], [])
        one = [_chunk("https://a", "Processing time is 4 weeks.", 1, "2026-06-06T00:00:00+00:00")]
        res = detect_and_resolve_conflicts(one, client=_conflict_client())
        self.assertEqual(len(res["kept_chunks"]), 1)
        self.assertEqual(res["conflicts_detected"], 0)


if __name__ == "__main__":
    unittest.main()

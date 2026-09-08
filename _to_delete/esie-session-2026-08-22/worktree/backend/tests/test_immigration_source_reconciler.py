"""
N9 / AIQ-849 — tests for multi-source triangulation reconciliation.

Pure vector math (cosine similarity of stored embeddings) — NO LLM/embedder call.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_source_reconciler import (
    confidence_from_agreement,
    reconcile,
)


def _chunk(cid, tier, emb, corridor="FR_NO", text="Processing time is 4 weeks."):
    return {
        "id": cid,
        "trust_tier": tier,
        "corridor": corridor,
        "chunk_text": text,
        "embedding": emb,
        "adjusted_score": 0.8,
    }


# 3-D unit-ish vectors: A and A' are near-identical (cosine ~1.0 >= 0.85);
# B is orthogonal to A (cosine 0.0 < 0.85).
_VEC_A = [1.0, 0.0, 0.0]
_VEC_A2 = [0.98, 0.02, 0.0]
_VEC_B = [0.0, 1.0, 0.0]


def _by_id(reconciled):
    return {c["id"]: c["source_agreement"] for c in reconciled}


class SourceReconcilerTests(unittest.TestCase):
    def test_cross_tier_match_is_confirmed(self):
        # Criterion 1: tier-1 + tier-2 chunks with cosine >= 0.85 → confirmed (both).
        official = [_chunk("o1", 1, _VEC_A)]
        secondary = [_chunk("s1", 2, _VEC_A2)]
        res = reconcile(official, secondary)
        tags = _by_id(res["reconciled_chunks"])
        self.assertEqual(tags["o1"], "confirmed")
        self.assertEqual(tags["s1"], "confirmed")

    def test_official_with_no_match_is_official_only(self):
        official = [_chunk("o1", 1, _VEC_A)]
        secondary = [_chunk("s1", 2, _VEC_B)]   # orthogonal → no agreement
        res = reconcile(official, secondary)
        tags = _by_id(res["reconciled_chunks"])
        self.assertEqual(tags["o1"], "official_only")
        self.assertEqual(tags["s1"], "secondary_only")

    def test_single_tier_only_official_falls_back(self):
        # Criterion 3: corridor with only tier-1 sources → all official_only, no error.
        official = [_chunk("o1", 1, _VEC_A), _chunk("o2", 1, _VEC_B)]
        res = reconcile(official, [])
        tags = _by_id(res["reconciled_chunks"])
        self.assertEqual(set(tags.values()), {"official_only"})
        self.assertEqual(len(res["reconciled_chunks"]), 2)

    def test_single_tier_only_secondary_falls_back(self):
        secondary = [_chunk("s1", 2, _VEC_A)]
        res = reconcile([], secondary)
        tags = _by_id(res["reconciled_chunks"])
        self.assertEqual(tags["s1"], "secondary_only")

    def test_dedup_tier1_chunk_present_in_both_sets(self):
        # The unrestricted (secondary) query also returns the tier-1 chunk; it must
        # not be double-counted, and a tier-1 dup is not its own corroboration.
        o1 = _chunk("o1", 1, _VEC_A)
        res = reconcile([o1], [dict(o1)])   # same id in both sets
        self.assertEqual(len(res["reconciled_chunks"]), 1)
        self.assertEqual(_by_id(res["reconciled_chunks"])["o1"], "official_only")

    def test_reconcile_makes_no_model_call(self):
        # Criterion 5: reconciliation is pure vector math — it never takes/uses a
        # client or embedder. Guard the signature so a future refactor can't sneak one in.
        import inspect
        params = set(inspect.signature(reconcile).parameters)
        self.assertNotIn("client", params)
        self.assertNotIn("embedder", params)

    def test_confidence_confirmed_beats_secondary_only(self):
        # Criterion 4: a confirmed-agreement answer scores higher than secondary-only.
        confirmed = reconcile([_chunk("o1", 1, _VEC_A)], [_chunk("s1", 2, _VEC_A2)])["reconciled_chunks"]
        secondary_only = reconcile([], [_chunk("s1", 2, _VEC_A)])["reconciled_chunks"]
        self.assertGreater(
            confidence_from_agreement(confirmed),
            confidence_from_agreement(secondary_only),
        )

    def test_empty_inputs_are_safe(self):
        res = reconcile([], [])
        self.assertEqual(res["reconciled_chunks"], [])
        self.assertEqual(confidence_from_agreement([]), 0.0)


if __name__ == "__main__":
    unittest.main()

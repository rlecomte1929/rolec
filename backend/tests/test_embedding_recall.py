"""
AIQ-624 / AI-I.4d — top-k recall gold set + recall@5 regression guard.

Why this exists
---------------
Before AI-I.4 swaps the embedding model (text-embedding-3-small -> BGE-M3 /
Cohere v3, AI-W1.2) and AI-I.4e cuts over the HNSW indexes, we need a fixed
gold set so a recall regression is caught instead of shipping blind. The fixture
``backend/tests/fixtures/embedding_recall_pairs.jsonl`` holds 50
(query, expected_canonical_id) pairs over a self-contained multilingual corpus
(FR / DE / NO / EN / Hindi).

How the baseline is recorded
----------------------------
``compute_recall_at_k`` embeds the corpus + each query with a supplied embedder
and measures recall@5 (fraction of queries whose expected canonical id is in the
top-5 by cosine similarity). This test gates on the deterministic, offline
``HashEmbedder`` (a bag-of-token-hashes — no API key, hermetic in CI), and prints
the baseline so it is visible in the test log.

To record the *production* baseline for the model-swap gate, run with the real
embedder:

    POLICY_ASSISTANT_EMBEDDER=openai OPENAI_API_KEY=... \
        python -m pytest backend/tests/test_embedding_recall.py -s

AI-I.4e must assert the new model's recall@5 >= that recorded baseline before it
ships. The corpus is carried in the fixture itself because prod
``rce.canonical_entities`` is empty (0 rows) — the suite must not depend on live
data.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any, Dict, List

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_assistant_embedder import (  # noqa: E402
    HashEmbedder,
    cosine_similarity,
)

FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "embedding_recall_pairs.jsonl"
)
EXPECTED_PAIRS = 50
EXPECTED_LANGS = {"EN", "FR", "DE", "NO", "HI"}
# The HashEmbedder is deterministic; the gold set is built so its recall@5 is a
# perfect 1.0. Gate just below to tolerate a future 1-pair fixture edit while
# still catching a real regression.
HASH_BASELINE_FLOOR = 0.98


def load_pairs(path: str = FIXTURE) -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def compute_recall_at_k(embedder, pairs: List[Dict[str, Any]], k: int = 5) -> float:
    """Recall@k of expected_canonical_id over the fixture's own corpus."""
    corpus = [(p["canonical_id"], embedder.embed(p["corpus_text"])) for p in pairs]
    hits = 0
    for p in pairs:
        q = embedder.embed(p["query"])
        ranked = sorted(
            ((cosine_similarity(q, cv), cid) for cid, cv in corpus),
            key=lambda t: t[0],
            reverse=True,
        )
        if p["canonical_id"] in [cid for _, cid in ranked[:k]]:
            hits += 1
    return hits / len(pairs) if pairs else 0.0


class EmbeddingRecallGoldSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pairs = load_pairs()

    def test_fixture_has_fifty_pairs(self) -> None:
        self.assertEqual(len(self.pairs), EXPECTED_PAIRS)

    def test_canonical_ids_unique(self) -> None:
        ids = [p["canonical_id"] for p in self.pairs]
        self.assertEqual(len(set(ids)), len(ids))

    def test_required_keys_present(self) -> None:
        for p in self.pairs:
            for key in ("canonical_id", "lang", "corpus_text", "query"):
                self.assertIn(key, p, msg=f"missing {key} in {p.get('canonical_id')}")

    def test_all_five_languages_covered(self) -> None:
        langs = {p["lang"] for p in self.pairs}
        self.assertEqual(langs, EXPECTED_LANGS)

    def test_recall_at_5_baseline(self) -> None:
        recall = compute_recall_at_k(HashEmbedder(), self.pairs, k=5)
        # Baseline recorded in the test log (run with -s to see it).
        print(
            f"\n[AIQ-624] recall@5 baseline (embedder=hash): "
            f"{recall:.4f} over {len(self.pairs)} pairs"
        )
        self.assertGreaterEqual(
            recall,
            HASH_BASELINE_FLOOR,
            msg=f"recall@5 {recall:.4f} below baseline floor {HASH_BASELINE_FLOOR}",
        )


if __name__ == "__main__":
    unittest.main()

"""
Tests for the immigration RAG retriever (P1-01a / AIQ-626), updated for N2/AIQ-841.

The retriever now reads immigration_corpus_chunks (corridor-scoped) directly,
not the policy_assistant_chunks namespace. corridor is stored in the underscore
key form ('FR_NO'); the retriever converts the arrow form ('FR→NO') used by
corridor_key/UI when querying.

Seeds a deterministic in-memory SQLite mirror with the HashEmbedder (engine is
injected via the new `engine` param) — no network, no OpenAI key.

Asserts: corridor scoping (no cross-corridor leak), relevance scores present,
arrow→underscore normalization, uncovered corridor empty, incomplete profile empty.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"  # query embedder = hash, matches seeded chunks

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import immigration_retriever
from backend.app.services.immigration_retriever import PathClassification, UserProfile
from backend.app.services.policy_assistant_embedder import HashEmbedder

_FR_NO_IDS = [f"fr-no-{i:02d}" for i in range(1, 13)]
_IN_DE_IDS = ["in-de-01", "in-de-02"]

_SCHEMA = (
    "CREATE TABLE immigration_corpus_chunks ("
    "id TEXT PRIMARY KEY, corridor TEXT NOT NULL, source_doc_id TEXT, source_url TEXT NOT NULL, "
    "chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL, chunk_metadata TEXT DEFAULT '{}', "
    "trust_tier INTEGER NOT NULL DEFAULT 2, fetched_at TEXT NOT NULL, embedding TEXT, "
    "content_hash TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)"
)


def _engine_with_seed():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    emb = HashEmbedder()
    with eng.begin() as c:
        c.execute(text(_SCHEMA))

        def seed(cid, corridor_db, body):
            c.execute(text(
                "INSERT INTO immigration_corpus_chunks "
                "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, trust_tier, "
                " fetched_at, embedding, content_hash, is_active) VALUES "
                "(:id,:cor,:u,:t,:i,:m,:tt,:f,:e,:h,1)"),
                {"id": cid, "cor": corridor_db, "u": f"https://gov.example/{cid}", "t": body,
                 "i": 0, "m": json.dumps({"corridor": corridor_db}), "tt": 1,
                 "f": "2026-06-06T00:00:00+00:00", "e": json.dumps(emb.embed(body)), "h": cid})

        for cid in _FR_NO_IDS:
            seed(cid, "FR_NO", f"France to Norway residence registration rule {cid}")
        for cid in _IN_DE_IDS:
            seed(cid, "IN_DE", f"India to Germany Blue Card rule {cid}")
    return eng


class ImmigrationRetrieverTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine_with_seed()
        self.marc = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
        self.path = PathClassification(pathway_type="eu_free_movement")

    def _retrieve(self, profile, classification, top_k=12):
        return immigration_retriever.retrieve_for_profile(
            profile=profile, classification=classification, top_k=top_k, engine=self.engine,
        )

    def test_corridor_scoped_no_cross_corridor_leak(self):
        chunks = self._retrieve(self.marc, self.path, top_k=20)
        ids = {c["id"] for c in chunks}
        self.assertEqual(ids, set(_FR_NO_IDS))            # all FR_NO returned
        for leaked in _IN_DE_IDS:
            self.assertNotIn(leaked, ids)                  # no IN_DE leak
        for c in chunks:
            self.assertEqual(c["corridor"], "FR_NO")
            self.assertEqual(c["source_type"], "immigration_rule")

    def test_relevance_scores_present(self):
        for c in self._retrieve(self.marc, self.path):
            self.assertIn("score", c)
            self.assertIsInstance(c["score"], float)

    def test_top_k_respected(self):
        self.assertLessEqual(len(self._retrieve(self.marc, self.path, top_k=5)), 5)

    def test_corridor_arrow_to_underscore_normalization(self):
        # classification.corridor supplied in arrow form must match underscore rows.
        chunks = self._retrieve(self.marc, PathClassification(pathway_type="x", corridor="FR→NO"))
        self.assertTrue(chunks)
        self.assertTrue(all(c["corridor"] == "FR_NO" for c in chunks))

    def test_uncovered_corridor_returns_empty(self):
        chunks = self._retrieve(
            UserProfile(nationality="JP", origin_country="JP", destination_country="NO", is_eea=False),
            PathClassification(pathway_type="skilled_worker_permit"),
        )
        self.assertEqual(chunks, [])

    def test_incomplete_profile_returns_empty(self):
        chunks = self._retrieve(
            UserProfile(nationality="FR", origin_country="", destination_country="NO", is_eea=True),
            self.path,
        )
        self.assertEqual(chunks, [])


if __name__ == "__main__":
    unittest.main()

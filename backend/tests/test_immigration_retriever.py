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
from datetime import datetime, timedelta, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"  # query embedder = hash, matches seeded chunks

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import immigration_retriever
from backend.app.services.immigration_retriever import (
    PathClassification,
    UserProfile,
    _apply_quality_gates,
)
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
        # min_similarity_score=0.0 isolates corridor-scoping from the N3 floor
        # (the floor is tested separately in QualityGatesTests).
        return immigration_retriever.retrieve_for_profile(
            profile=profile, classification=classification, top_k=top_k,
            engine=self.engine, min_similarity_score=0.0,
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


def _engine_with_mixed_tiers():
    """Corpus with both official (tier-1) and secondary (tier-2) chunks, plus a
    single-tier corridor — exercises the N9 trust_tier filter + embedding-carry."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    emb = HashEmbedder()
    with eng.begin() as c:
        c.execute(text(_SCHEMA))

        def seed(cid, corridor_db, body, tier):
            c.execute(text(
                "INSERT INTO immigration_corpus_chunks "
                "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, trust_tier, "
                " fetched_at, embedding, content_hash, is_active) VALUES "
                "(:id,:cor,:u,:t,:i,:m,:tt,:f,:e,:h,1)"),
                {"id": cid, "cor": corridor_db, "u": f"https://src.example/{cid}", "t": body,
                 "i": 0, "m": json.dumps({"corridor": corridor_db}), "tt": tier,
                 "f": "2026-06-06T00:00:00+00:00", "e": json.dumps(emb.embed(body)), "h": cid})

        seed("off-1", "FR_NO", "France to Norway residence registration rule A", 1)
        seed("off-2", "FR_NO", "France to Norway residence registration rule B", 1)
        seed("sec-1", "FR_NO", "France to Norway residence registration rule A", 2)
        seed("sec-2", "FR_NO", "France to Norway secondary blog guidance C", 2)
        seed("only-1", "NO_XX", "Norway only official rule", 1)   # single-tier corridor
    return eng


class RetrieveMultiSourceTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine_with_mixed_tiers()
        self.emb = HashEmbedder()
        self.profile = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
        self.path = PathClassification(pathway_type="eu_free_movement")

    def test_returns_official_and_unrestricted_sets_with_embeddings(self):
        res = immigration_retriever.retrieve_multi_source(
            profile=self.profile, classification=self.path, top_k=10,
            embedder=self.emb, engine=self.engine, min_similarity_score=0.0,
        )
        official, secondary = res["official_chunks"], res["secondary_chunks"]
        self.assertTrue(official)
        self.assertTrue(all(int(c["trust_tier"]) == 1 for c in official))      # tier-1 filter applied
        self.assertTrue(any(int(c["trust_tier"]) == 2 for c in secondary))     # unrestricted includes secondary
        self.assertIsInstance(official[0]["embedding"], list)                  # embeddings carried
        self.assertTrue(official[0]["embedding"])

    def test_single_tier_corridor_does_not_error(self):
        prof = UserProfile(nationality="X", origin_country="NO", destination_country="XX", is_eea=False)
        res = immigration_retriever.retrieve_multi_source(
            profile=prof, classification=PathClassification(pathway_type="x", corridor="NO→XX"),
            embedder=self.emb, engine=self.engine, min_similarity_score=0.0,
        )
        self.assertTrue(res["official_chunks"])                                 # tier-1 present
        self.assertTrue(all(int(c["trust_tier"]) == 1 for c in res["secondary_chunks"]))  # no secondary tier


_NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _gc(score, *, tier=None, fetched="2026-06-06T00:00:00+00:00", cid="x"):
    return {"id": cid, "score": score, "trust_tier": tier, "fetched_at": fetched, "corridor": "FR_NO"}


class QualityGatesTests(unittest.TestCase):
    """N3/AIQ-842 floor + trust_tier boost + freshness decay (pure helper)."""

    def test_floor_excludes_below_min(self):
        out = _apply_quality_gates([_gc(0.20, cid="lo"), _gc(0.30, cid="hi")],
                                   min_similarity=0.25, top_k=10, now=_NOW)
        self.assertEqual([c["id"] for c in out], ["hi"])

    def test_floor_disabled_with_zero(self):
        out = _apply_quality_gates([_gc(0.10)], min_similarity=0.0, top_k=10, now=_NOW)
        self.assertEqual(len(out), 1)

    def test_tier1_outranks_tier3(self):
        out = _apply_quality_gates([_gc(0.82, tier=3, cid="t3"), _gc(0.80, tier=1, cid="t1")],
                                   min_similarity=0.0, top_k=10, now=_NOW)
        self.assertEqual(out[0]["id"], "t1")
        # N8/AIQ-848: reliability weight defaults to 0 (dormant), so adjusted_score
        # is the unchanged 3-factor value (raw × tier × freshness).
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.80, places=3)
        self.assertAlmostEqual(
            next(c for c in out if c["id"] == "t3")["adjusted_score"], 0.615, places=3)

    def test_stale_flag_and_decay(self):
        old = (_NOW - timedelta(days=200)).isoformat()
        out = _apply_quality_gates([_gc(0.9, tier=1, fetched=old)], min_similarity=0.0, top_k=10, now=_NOW)
        self.assertTrue(out[0]["is_stale"])
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.9 * 0.70, places=3)

    def test_fresh_not_stale(self):
        out = _apply_quality_gates([_gc(0.9, tier=1)], min_similarity=0.0, top_k=10, now=_NOW)
        self.assertFalse(out[0]["is_stale"])
        self.assertAlmostEqual(out[0]["adjusted_score"], 0.9, places=3)


class StalenessWrapperTests(unittest.TestCase):
    """retrieve_with_staleness returns the {chunks, all_stale_warning, oldest_fetched_at} dict."""

    def setUp(self):
        self.engine = _engine_with_seed()
        self.marc = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
        self.path = PathClassification(pathway_type="eu_free_movement")

    def test_dict_shape_fresh_corpus(self):
        payload = immigration_retriever.retrieve_with_staleness(
            profile=self.marc, classification=self.path, engine=self.engine, min_similarity_score=0.0)
        self.assertEqual(set(payload), {"chunks", "all_stale_warning", "oldest_fetched_at"})
        self.assertTrue(payload["chunks"])
        self.assertFalse(payload["all_stale_warning"])         # seeded fresh
        self.assertIsNotNone(payload["oldest_fetched_at"])

    def test_uncovered_corridor_empty_payload(self):
        payload = immigration_retriever.retrieve_with_staleness(
            profile=UserProfile(nationality="JP", origin_country="JP", destination_country="NO", is_eea=False),
            classification=PathClassification(pathway_type="x"), engine=self.engine)
        self.assertEqual(payload["chunks"], [])
        self.assertFalse(payload["all_stale_warning"])         # empty -> not "all stale"
        self.assertIsNone(payload["oldest_fetched_at"])


if __name__ == "__main__":
    unittest.main()

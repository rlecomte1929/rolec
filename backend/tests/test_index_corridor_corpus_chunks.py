"""
Tests for the P2-06e corridor-corpus RAG indexer
(backend/scripts/index_corridor_corpus_chunks.py).

Two layers:
  1. Unit — `build_chunks` produces the right metadata contract (corridor,
     pathway_type), source_ref shape, and per-section coverage for the real
     us_fr / in_de corpus files.
  2. End-to-end — seed the built+embedded chunks into an in-memory SQLite mirror
     of policy_assistant_chunks (HashEmbedder, no network/key — same pattern as
     test_immigration_retriever.py) and assert that
     immigration_retriever.retrieve_for_profile returns ≥1 applicable chunk for
     a US→FR long_stay_visa profile and an IN→DE blue_card profile (the P2-06e
     validation criterion), and an empty list for an uncovered corridor (the
     RULE_NOT_FOUND guard).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force the hash embedder so nothing tries to call OpenAI.
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.app.services import immigration_retriever  # noqa: E402
from backend.app.services import policy_chunk_retriever  # noqa: E402
from backend.app.services.immigration_retriever import (  # noqa: E402
    PathClassification,
    UserProfile,
)
from backend.app.services.policy_assistant_embedder import HashEmbedder  # noqa: E402
from backend.scripts import index_corridor_corpus_chunks as indexer  # noqa: E402

_US_FR = os.path.join(_REPO_ROOT, "corpus", "us_fr_corridor.json")
_IN_DE = os.path.join(_REPO_ROOT, "corpus", "in_de_corridor.json")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SCHEMA = """
CREATE TABLE policy_assistant_chunks (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    policy_version_id TEXT,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_metadata TEXT NOT NULL DEFAULT '{}',
    embedding TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, source_type, source_ref)
);
"""


class _FakeDb:
    def __init__(self, engine):
        self.engine = engine


class BuildChunksUnitTests(unittest.TestCase):
    def test_us_fr_metadata_contract(self):
        chunks = indexer.build_chunks(_load(_US_FR))
        # Every chunk is tagged with the corridor in corridor_key() format.
        self.assertTrue(chunks)
        for c in chunks:
            self.assertEqual(c["corridor"], "US→FR")
            self.assertEqual(c["metadata"]["corridor"], "US→FR")
            self.assertTrue(c["source_ref"].startswith("immigration_rule."))

        kinds = {c["metadata"]["kind"] for c in chunks}
        self.assertEqual(kinds, {"overview", "pathway", "document", "post_arrival"})

        # Overview is corridor-wide (matches every pathway query).
        overview = [c for c in chunks if c["metadata"]["kind"] == "overview"]
        self.assertEqual(len(overview), 1)
        self.assertIsNone(overview[0]["pathway_type"])

        # Pathway chunks carry their visa_type as pathway_type.
        pathway_types = {c["pathway_type"] for c in chunks if c["metadata"]["kind"] == "pathway"}
        self.assertEqual(pathway_types, {"long_stay_visa", "passeport_talent"})

    def test_in_de_has_blue_card_pathway(self):
        chunks = indexer.build_chunks(_load(_IN_DE))
        for c in chunks:
            self.assertEqual(c["corridor"], "IN→DE")
        pathway_types = {c["pathway_type"] for c in chunks if c["metadata"]["kind"] == "pathway"}
        self.assertIn("blue_card", pathway_types)

    def test_source_refs_unique(self):
        for path in (_US_FR, _IN_DE):
            chunks = indexer.build_chunks(_load(path))
            refs = [c["source_ref"] for c in chunks]
            self.assertEqual(len(refs), len(set(refs)), f"duplicate source_ref in {path}")

    def test_emitted_sql_is_idempotent_shaped(self):
        sql = indexer.build_sql([_US_FR])
        self.assertIn("DELETE FROM public.policy_assistant_chunks", sql)
        self.assertIn("INSERT INTO public.policy_assistant_chunks", sql)
        self.assertIn("ON CONFLICT (company_id, source_type, source_ref) DO UPDATE", sql)
        self.assertIn("::vector", sql)


class RetrieverEndToEndTests(unittest.TestCase):
    """Build → embed → seed SQLite → retrieve, on the real corpus files."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        embedder = HashEmbedder()
        for path in (_US_FR, _IN_DE):
            chunks = indexer.build_chunks(_load(path))
            embs = embedder.embed_batch([c["chunk_text"] for c in chunks])
            with self.engine.begin() as conn:
                for c, emb in zip(chunks, embs):
                    conn.execute(
                        text(
                            "INSERT INTO policy_assistant_chunks "
                            "(id, company_id, source_type, source_ref, chunk_text, "
                            " chunk_metadata, embedding) "
                            "VALUES (:id, :co, :st, :ref, :body, :meta, :emb)"
                        ),
                        {
                            "id": c["source_ref"],
                            "co": immigration_retriever.IMMIGRATION_CORPUS_COMPANY_ID,
                            "st": immigration_retriever.IMMIGRATION_SOURCE_TYPE,
                            "ref": c["source_ref"],
                            "body": c["chunk_text"],
                            "meta": json.dumps(c["metadata"], ensure_ascii=False),
                            "emb": json.dumps(emb),
                        },
                    )

        self.fake_db = _FakeDb(self.engine)
        p = mock.patch.object(policy_chunk_retriever, "db", self.fake_db)
        p.start()
        self.addCleanup(p.stop)

    def test_us_fr_long_stay_visa_profile_gets_grounded_rules(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="US", origin_country="US",
                destination_country="FR", is_eea=False,
            ),
            classification=PathClassification(pathway_type="long_stay_visa"),
            top_k=10,
        )
        self.assertGreaterEqual(len(chunks), 1)  # No RULE_NOT_FOUND.
        for c in chunks:
            self.assertEqual(c["chunk_metadata"]["corridor"], "US→FR")
            # Only long_stay_visa or corridor-wide (null) chunks — no leakage.
            self.assertIn(c["chunk_metadata"].get("pathway_type"), ("long_stay_visa", None))

    def test_in_de_blue_card_profile_gets_grounded_rules(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="IN", origin_country="IN",
                destination_country="DE", is_eea=False,
            ),
            classification=PathClassification(pathway_type="blue_card"),
            top_k=10,
        )
        self.assertGreaterEqual(len(chunks), 1)  # No RULE_NOT_FOUND.
        for c in chunks:
            self.assertEqual(c["chunk_metadata"]["corridor"], "IN→DE")
            self.assertIn(c["chunk_metadata"].get("pathway_type"), ("blue_card", None))

    def test_no_cross_corridor_leak(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="US", origin_country="US",
                destination_country="FR", is_eea=False,
            ),
            classification=PathClassification(pathway_type="long_stay_visa"),
            top_k=50,
        )
        corridors = {c["chunk_metadata"]["corridor"] for c in chunks}
        self.assertEqual(corridors, {"US→FR"})

    def test_uncovered_corridor_returns_empty(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="JP", origin_country="JP",
                destination_country="NO", is_eea=False,
            ),
            classification=PathClassification(pathway_type="skilled_worker"),
            top_k=10,
        )
        self.assertEqual(chunks, [])


if __name__ == "__main__":
    unittest.main()

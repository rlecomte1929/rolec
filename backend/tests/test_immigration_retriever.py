"""
Integration tests for the immigration RAG retriever (P1-01a / AIQ-626).

`immigration_retriever` is a thin wrapper over the company-scoped
`policy_chunk_retriever`. It takes a classified UserProfile + PathClassification,
derives the corridor (e.g. FR→NO) and pathway_type, and returns only the
chunks that apply to that corridor/pathway.

The FR→NO immigration corpus does not exist in the repo yet (blocked on the
real corridor-ingestion task), so this test seeds its own deterministic
fixture chunks into an in-memory SQLite mirror with the HashEmbedder — the
same pattern as test_policy_assistant_rag_a.py. No network, no OpenAI key.

Asserts:
  - Marc Bouchard (FR→NO, EEA) gets ≥10 chunks, ALL from the FR→NO corridor,
    each with a numeric relevance score. Chunk ids are pinned.
  - Chunks from other corridors (IN→DE) never leak into a FR→NO query.
  - pathway_type narrows results within a corridor.
  - An uncovered corridor (JP→NO) returns an empty list (no hallucinated
    cross-corridor matches — the retriever-side basis for RULE_NOT_FOUND).
  - An incomplete profile returns an empty list.
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

# Force the hash embedder so the test never tries to call OpenAI.
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.app.services import immigration_retriever  # noqa: E402
from backend.app.services import policy_chunk_retriever  # noqa: E402
from backend.app.services.immigration_retriever import (  # noqa: E402
    PathClassification,
    UserProfile,
)
from backend.app.services.policy_assistant_embedder import HashEmbedder  # noqa: E402


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
    """Minimal stub exposing only the `.engine` the retriever path uses."""

    def __init__(self, engine):
        self.engine = engine


# FR→NO corridor: 12 chambers of the EU free-movement pathway + 1 non-EEA
# pathway chunk used to prove pathway_type narrowing.
_FR_NO_EEA_IDS = [f"fr-no-eea-{i:02d}" for i in range(1, 13)]
_FR_NO_NONEEA_ID = "fr-no-noneea-01"
# IN→DE corridor: must never leak into a FR→NO query.
_IN_DE_IDS = ["in-de-bluecard-01", "in-de-bluecard-02"]


def _seed_chunk(conn, embedder, *, chunk_id, corridor, pathway_type, text_body):
    meta = {"corridor": corridor, "pathway_type": pathway_type}
    emb = embedder.embed(text_body)
    conn.execute(
        text(
            "INSERT INTO policy_assistant_chunks "
            "(id, company_id, source_type, source_ref, chunk_text, "
            " chunk_metadata, embedding) "
            "VALUES (:id, :co, :st, :ref, :body, :meta, :emb)"
        ),
        {
            "id": chunk_id,
            "co": immigration_retriever.IMMIGRATION_CORPUS_COMPANY_ID,
            "st": immigration_retriever.IMMIGRATION_SOURCE_TYPE,
            "ref": f"immigration_rule.{chunk_id}",
            "body": text_body,
            "meta": json.dumps(meta),
            "emb": json.dumps(emb),
        },
    )


class ImmigrationRetrieverTests(unittest.TestCase):
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
        with self.engine.begin() as conn:
            for cid in _FR_NO_EEA_IDS:
                _seed_chunk(
                    conn, embedder,
                    chunk_id=cid, corridor="FR→NO",
                    pathway_type="eu_free_movement",
                    text_body=f"France to Norway EEA residence registration rule {cid}",
                )
            _seed_chunk(
                conn, embedder,
                chunk_id=_FR_NO_NONEEA_ID, corridor="FR→NO",
                pathway_type="skilled_worker_permit",
                text_body="France to Norway non-EEA skilled worker permit rule",
            )
            for cid in _IN_DE_IDS:
                _seed_chunk(
                    conn, embedder,
                    chunk_id=cid, corridor="IN→DE",
                    pathway_type="eu_blue_card",
                    text_body=f"India to Germany EU Blue Card rule {cid}",
                )

        self.fake_db = _FakeDb(self.engine)
        p = mock.patch.object(policy_chunk_retriever, "db", self.fake_db)
        p.start()
        self.addCleanup(p.stop)

        # Marc Bouchard: French national, France → Norway, EEA.
        self.marc = UserProfile(
            nationality="FR", origin_country="FR",
            destination_country="NO", is_eea=True,
        )
        self.marc_path = PathClassification(pathway_type="eu_free_movement")

    def test_returns_at_least_ten_chunks_all_from_fr_no_corridor(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=self.marc, classification=self.marc_path, top_k=12,
        )
        self.assertGreaterEqual(len(chunks), 10)
        for c in chunks:
            self.assertEqual(c["chunk_metadata"]["corridor"], "FR→NO")

    def test_relevance_scores_present(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=self.marc, classification=self.marc_path, top_k=12,
        )
        for c in chunks:
            self.assertIn("score", c)
            self.assertIsInstance(c["score"], float)

    def test_pinned_chunk_ids_and_no_cross_corridor_leak(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=self.marc, classification=self.marc_path, top_k=20,
        )
        returned_ids = {c["id"] for c in chunks}
        # All EEA FR→NO chunks present; no IN→DE leak; non-EEA pathway excluded.
        self.assertEqual(returned_ids, set(_FR_NO_EEA_IDS))
        for leaked in _IN_DE_IDS:
            self.assertNotIn(leaked, returned_ids)
        self.assertNotIn(_FR_NO_NONEEA_ID, returned_ids)

    def test_pathway_type_narrows_within_corridor(self):
        non_eea = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="US", origin_country="FR",
                destination_country="NO", is_eea=False,
            ),
            classification=PathClassification(pathway_type="skilled_worker_permit"),
            top_k=20,
        )
        returned_ids = {c["id"] for c in non_eea}
        self.assertEqual(returned_ids, {_FR_NO_NONEEA_ID})

    def test_uncovered_corridor_returns_empty(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="JP", origin_country="JP",
                destination_country="NO", is_eea=False,
            ),
            classification=PathClassification(pathway_type="skilled_worker_permit"),
            top_k=12,
        )
        self.assertEqual(chunks, [])

    def test_incomplete_profile_returns_empty(self):
        chunks = immigration_retriever.retrieve_for_profile(
            profile=UserProfile(
                nationality="FR", origin_country="",
                destination_country="NO", is_eea=True,
            ),
            classification=self.marc_path, top_k=12,
        )
        self.assertEqual(chunks, [])


if __name__ == "__main__":
    unittest.main()

"""
N2 / AIQ-841 — unit tests for the immigration corpus indexer.

Injected in-memory SQLite (both tables) + HashEmbedder — no network, no prod,
no OpenAI key. Verifies: a crawled doc produces >=1 embedded chunk, re-running
is idempotent (0 new), and embeddings are 1536-dim.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services.immigration_chunk_indexer import index_immigration_corpus
from backend.app.services.policy_assistant_embedder import EMBEDDING_DIM, HashEmbedder

_CRAWLED_DDL = (
    "CREATE TABLE crawled_immigration_documents ("
    "id TEXT PRIMARY KEY, corridor TEXT, source_url TEXT, trust_tier INTEGER, "
    "raw_html_path TEXT, extracted_text TEXT, content_hash TEXT, fetched_at TEXT, "
    "http_status INTEGER, crawl_error TEXT, is_active INTEGER)"
)
_CHUNKS_DDL = (
    "CREATE TABLE immigration_corpus_chunks ("
    "id TEXT PRIMARY KEY, corridor TEXT NOT NULL, source_doc_id TEXT, source_url TEXT NOT NULL, "
    "chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL, chunk_metadata TEXT DEFAULT '{}', "
    "trust_tier INTEGER NOT NULL DEFAULT 2, fetched_at TEXT NOT NULL, embedding TEXT, "
    "content_hash TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)"
)

_TEXT = (
    "# Work permit requirements\n"
    "A non-EEA national needs a residence permit before starting work. "
    "Required documents include a valid passport, an employment contract, and proof of "
    "qualifications. Processing typically takes several weeks. Applicants should apply "
    "from their home country through the relevant embassy before travelling."
)


def _engine_with_doc():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as c:
        c.execute(text(_CRAWLED_DDL))
        c.execute(text(_CHUNKS_DDL))
        c.execute(text(
            "INSERT INTO crawled_immigration_documents "
            "(id, corridor, source_url, trust_tier, extracted_text, content_hash, fetched_at, "
            " http_status, crawl_error, is_active) VALUES "
            "(:id,'FR_NO','https://www.udi.no/en/want-to-apply/',1,:t,'h1','2026-06-06T00:00:00+00:00',200,NULL,1)"),
            {"id": "doc-1", "t": _TEXT})
    return eng


def _count(eng):
    with eng.begin() as c:
        return c.execute(text("SELECT count(*) FROM immigration_corpus_chunks")).scalar()


class TestImmigrationChunkIndexer(unittest.TestCase):
    def test_ingest_writes_chunks(self):
        eng = _engine_with_doc()
        res = index_immigration_corpus(corridor="FR_NO", embedder=HashEmbedder(), engine=eng)
        self.assertEqual(res["docs"], 1)
        self.assertGreaterEqual(res["chunks_written"], 1)
        self.assertEqual(res["chunks_written"], _count(eng))
        # metadata + corridor carried through
        with eng.begin() as c:
            row = c.execute(text(
                "SELECT corridor, chunk_metadata, trust_tier FROM immigration_corpus_chunks LIMIT 1"
            )).mappings().first()
        self.assertEqual(row["corridor"], "FR_NO")
        self.assertEqual(row["trust_tier"], 1)
        self.assertEqual(json.loads(row["chunk_metadata"])["corridor"], "FR_NO")

    def test_idempotent_rerun(self):
        eng = _engine_with_doc()
        first = index_immigration_corpus(corridor="FR_NO", embedder=HashEmbedder(), engine=eng)
        n = _count(eng)
        second = index_immigration_corpus(corridor="FR_NO", embedder=HashEmbedder(), engine=eng)
        self.assertEqual(second["chunks_written"], 0)
        self.assertEqual(second["chunks_skipped"], first["chunks_written"])
        self.assertEqual(_count(eng), n)  # no new rows

    def test_embedding_dimension_1536(self):
        eng = _engine_with_doc()
        index_immigration_corpus(corridor="FR_NO", embedder=HashEmbedder(), engine=eng)
        with eng.begin() as c:
            emb = c.execute(text("SELECT embedding FROM immigration_corpus_chunks LIMIT 1")).scalar()
        self.assertEqual(len(json.loads(emb)), EMBEDDING_DIM)
        self.assertEqual(EMBEDDING_DIM, 1536)

    def test_skips_error_and_empty_docs(self):
        eng = _engine_with_doc()
        with eng.begin() as c:
            c.execute(text(
                "INSERT INTO crawled_immigration_documents (id, corridor, source_url, trust_tier, "
                "extracted_text, content_hash, fetched_at, crawl_error, is_active) VALUES "
                "('err','FR_NO','u',1,NULL,'error','2026-06-06T00:00:00+00:00','Timeout',1)"))
        res = index_immigration_corpus(corridor="FR_NO", embedder=HashEmbedder(), engine=eng)
        self.assertEqual(res["docs"], 1)  # the error/empty doc is excluded


if __name__ == "__main__":
    unittest.main()

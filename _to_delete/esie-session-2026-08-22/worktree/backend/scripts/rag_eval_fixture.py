"""
W3-4 — deterministic eval fixture loader.

Seeds the synthetic chunk corpus (backend/tests/fixtures/rag_eval/chunks.jsonl,
produced by gen_rag_eval_chunks.py) into an in-memory SQLite
`immigration_corpus_chunks` table using the HashEmbedder, so the context-precision
eval runs against a fixed, byte-deterministic corpus instead of the live DB.

Usage (in the gate test):

    from backend.scripts.rag_eval_fixture import build_seeded_engine, patched_retriever_db
    engine = build_seeded_engine()
    with patched_retriever_db(engine):
        results = evaluate(load_queries(QUERIES), ImmigrationRetrieverAdapter(), k=5)
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

os.environ.setdefault("POLICY_ASSISTANT_EMBEDDER", "hash")  # deterministic embeddings

from backend.app.services import immigration_retriever  # noqa: E402
from backend.app.services.policy_assistant_embedder import HashEmbedder  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = _REPO_ROOT / "backend/tests/fixtures/rag_eval/chunks.jsonl"
QUERIES_PATH = _REPO_ROOT / "backend/tests/fixtures/rag_eval/queries.jsonl"

_SCHEMA = (
    "CREATE TABLE immigration_corpus_chunks ("
    "id TEXT PRIMARY KEY, corridor TEXT NOT NULL, source_doc_id TEXT, source_url TEXT NOT NULL, "
    "chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL DEFAULT 0, chunk_metadata TEXT DEFAULT '{}', "
    "trust_tier INTEGER NOT NULL DEFAULT 2, fetched_at TEXT NOT NULL, embedding TEXT, "
    "content_hash TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)"
)


def load_chunks() -> List[Dict[str, Any]]:
    """Parse chunks.jsonl, skipping the leading // comment line."""
    out: List[Dict[str, Any]] = []
    for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('{"_meta'):
            continue
        out.append(json.loads(line))
    return out


def build_seeded_engine():
    """In-memory SQLite seeded with the fixture corpus (deterministic embeddings)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    emb = HashEmbedder()
    chunks = load_chunks()
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
        for c in chunks:
            body = c["body"]
            meta = {"corridor": c["corridor"], "pathway_type": c.get("pathway_type")}
            conn.execute(
                text(
                    "INSERT INTO immigration_corpus_chunks "
                    "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, "
                    " trust_tier, fetched_at, embedding, content_hash, is_active) "
                    "VALUES (:id,:cor,:u,:t,0,:m,:tt,:f,:e,:h,1)"
                ),
                {
                    "id": c["chunk_id"], "cor": c["corridor"], "u": c["source_url"],
                    "t": body, "m": json.dumps(meta), "tt": int(c.get("trust_tier", 1)),
                    "f": "2026-06-06T00:00:00+00:00", "e": json.dumps(emb.embed(body)),
                    "h": c["chunk_id"],
                },
            )
    return engine


class _FakeDb:
    def __init__(self, engine):
        self.engine = engine


@contextlib.contextmanager
def patched_retriever_db(engine) -> Iterator[None]:
    """Point immigration_retriever at the fixture engine for the duration."""
    with mock.patch.object(immigration_retriever, "db", _FakeDb(engine)):
        yield

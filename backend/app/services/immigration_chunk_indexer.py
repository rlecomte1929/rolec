"""
N2 / AIQ-841 — chunk + embed + ingest the immigration corpus.

Reads crawled_immigration_documents (the N1 crawl output), chunks each doc's
extracted_text, embeds the chunks, and writes them to immigration_corpus_chunks
(the SEPARATE, corridor-scoped corpus table — NOT policy_assistant_chunks).

Mirrors policy_chunk_indexer's embed/insert pattern. Idempotent: a chunk is
skipped if (source_doc_id, content_hash) already exists, so re-running only
ingests new/changed content.

Chunker: reuses the existing crawler char-based chunker
(crawler/chunkers/chunker.py) — there is no 512/64-token chunker in
policy_chunk_indexer (the N2 brief was wrong about that). corridor is stored in
the underscore key form ('FR_NO'), consistent with crawled_immigration_documents.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from ...crawler.chunkers.chunker import chunk_document
from ...crawler.parsers.html_parser import ParsedDocument
from .policy_assistant_embedder import Embedder, get_default_embedder

log = logging.getLogger(__name__)


def _first_heading(extracted_text: str) -> str:
    """Best-effort page title: the first '# ' markdown heading the parser emitted."""
    for line in (extracted_text or "").splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return ""


_INSERT = text(
    """
    INSERT INTO immigration_corpus_chunks
      (id, corridor, source_doc_id, source_url, chunk_text, chunk_index,
       chunk_metadata, trust_tier, fetched_at, embedding, content_hash, is_active)
    VALUES
      (:id, :corridor, :source_doc_id, :source_url, :chunk_text, :chunk_index,
       :chunk_metadata, :trust_tier, :fetched_at, :embedding, :content_hash, :is_active)
    """
)


def index_immigration_corpus(
    *,
    corridor: Optional[str] = None,
    embedder: Optional[Embedder] = None,
    engine=None,
) -> Dict[str, Any]:
    """
    Chunk + embed + ingest crawled immigration docs into immigration_corpus_chunks.
    `corridor` (underscore key, e.g. 'FR_NO') limits the run; None = all corridors.
    Returns a tally dict. Idempotent on (source_doc_id, content_hash).
    """
    engine = engine or db.engine
    embedder = embedder or get_default_embedder()
    is_sqlite = engine.dialect.name == "sqlite"

    where = "WHERE is_active = true AND extracted_text IS NOT NULL AND crawl_error IS NULL"
    params: Dict[str, Any] = {}
    if corridor:
        where += " AND corridor = :c"
        params["c"] = corridor

    with engine.begin() as conn:
        docs = conn.execute(
            text(
                "SELECT id, corridor, source_url, trust_tier, fetched_at, extracted_text "
                f"FROM crawled_immigration_documents {where}"
            ),
            params,
        ).mappings().all()

    written = skipped = 0
    for d in docs:
        title = _first_heading(d["extracted_text"])
        pdoc = ParsedDocument(page_title=title, main_text=d["extracted_text"])
        chunks = chunk_document(pdoc, source_url=d["source_url"], page_title=title)

        # Idempotency: drop chunks already embedded for this doc.
        fresh = []
        with engine.begin() as conn:
            for ch in chunks:
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM immigration_corpus_chunks "
                        "WHERE source_doc_id = :sid AND content_hash = :h LIMIT 1"
                    ),
                    {"sid": str(d["id"]), "h": ch.chunk_hash},
                ).first()
                if exists:
                    skipped += 1
                else:
                    fresh.append(ch)
        if not fresh:
            continue

        embeddings = embedder.embed_batch([ch.chunk_text for ch in fresh])
        with engine.begin() as conn:
            for ch, emb in zip(fresh, embeddings):
                meta = {
                    "corridor": d["corridor"],
                    "source_url": d["source_url"],
                    "trust_tier": int(d["trust_tier"]),
                    "fetched_at": str(d["fetched_at"]),
                    "page_title": title,
                    "chunk_index": ch.chunk_index,
                }
                conn.execute(_INSERT, {
                    "id": str(uuid.uuid4()),
                    "corridor": d["corridor"],
                    "source_doc_id": str(d["id"]),
                    "source_url": d["source_url"],
                    "chunk_text": ch.chunk_text,
                    "chunk_index": ch.chunk_index,
                    "chunk_metadata": json.dumps(meta),
                    "trust_tier": int(d["trust_tier"]),
                    "fetched_at": str(d["fetched_at"]),
                    "embedding": json.dumps(emb) if is_sqlite else emb,
                    "content_hash": ch.chunk_hash,
                    "is_active": True,
                })
                written += 1

    log.info(
        "immigration corpus indexed corridor=%s docs=%d written=%d skipped=%d embedder=%s",
        corridor or "ALL", len(docs), written, skipped, embedder.name,
    )
    return {
        "corridor": corridor or "ALL",
        "docs": len(docs),
        "chunks_written": written,
        "chunks_skipped": skipped,
        "embedder": embedder.name,
    }

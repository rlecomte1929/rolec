"""
Policy Assistant RAG (Sprint A): retrieval.

Given a question + company_id, return the top-K most similar chunks
from policy_assistant_chunks. Two backends:

  - Postgres: uses pgvector cosine distance ORDER BY embedding <=> :q.
    Fast even at thousands of chunks per company.
  - SQLite (dev/tests): pulls all company chunks into memory and
    computes cosine similarity in Python. Fine for <500 chunks; not
    intended for production.

Hard scoping rules baked in:
  - company_id is REQUIRED. No cross-company retrieval is possible.
  - The retriever NEVER sees other companies' chunks even if pgvector
    is wrong, because the WHERE clause filters first.
  - Optional source_type filter (e.g. only matrix_benefit + matrix_
    override) for callers who want to restrict to specific data layers.

Returned shape per chunk:
  {
    "id":           uuid string,
    "source_type":  text,
    "source_ref":   text — used by frontend to render clickable cite chip
    "chunk_text":   text — what the LLM sees
    "chunk_metadata": dict — benefit_key, category, jurisdiction, etc.
    "score":        float — cosine similarity in [0, 1] (1 = identical)
  }
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from ...database import db
from .policy_assistant_embedder import (
    Embedder,
    cosine_similarity,
    get_default_embedder,
)

log = logging.getLogger(__name__)


def retrieve(
    *,
    company_id: str,
    query: str,
    top_k: int = 8,
    source_types: Optional[Sequence[str]] = None,
    embedder: Optional[Embedder] = None,
) -> List[Dict[str, Any]]:
    """
    Top-K retrieval. Returns at most `top_k` chunks for `company_id`,
    ordered by descending similarity to the query embedding.

    Empty list when:
      - company_id missing
      - query empty / whitespace-only
      - company has no indexed chunks yet
    """
    if not company_id:
        return []
    if not query or not query.strip():
        return []

    embedder = embedder or get_default_embedder()
    q_emb = embedder.embed(query)

    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        return _retrieve_sqlite(company_id, q_emb, top_k, source_types)
    return _retrieve_postgres(company_id, q_emb, top_k, source_types)


# --- Postgres (pgvector) ---------------------------------------------------

def _retrieve_postgres(
    company_id: str,
    query_embedding: List[float],
    top_k: int,
    source_types: Optional[Sequence[str]],
) -> List[Dict[str, Any]]:
    """
    Uses pgvector's cosine distance operator (<=>). Distance is in
    [0, 2]; we convert to similarity = 1 - (distance / 2) clipped to
    [0, 1] for a comparable shape with the SQLite path.
    """
    where_extra = ""
    params: Dict[str, Any] = {"co": company_id, "k": int(max(1, min(top_k, 50)))}
    if source_types:
        # SQLAlchemy doesn't expand list params for arbitrary text(),
        # build the IN clause manually.
        names = list(source_types)
        placeholders = ", ".join(f":st_{i}" for i in range(len(names)))
        where_extra = f" AND source_type IN ({placeholders})"
        for i, n in enumerate(names):
            params[f"st_{i}"] = n
    # pgvector wants the embedding as a literal vector or a parameter
    # cast. Easiest: pass as text and CAST inside the query.
    params["q"] = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
    sql = (
        "SELECT id, source_type, source_ref, chunk_text, chunk_metadata, "
        "       (embedding <=> CAST(:q AS vector)) AS distance "
        "FROM policy_assistant_chunks "
        "WHERE company_id = :co"
        + where_extra
        + " ORDER BY embedding <=> CAST(:q AS vector) ASC LIMIT :k"
    )
    with db.engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        meta = d.get("chunk_metadata")
        if isinstance(meta, str):
            try:
                d["chunk_metadata"] = json.loads(meta)
            except Exception:
                d["chunk_metadata"] = {}
        # pgvector cosine distance is in [0,2]. Convert to similarity
        # in [0,1] for a stable API shape across backends.
        dist = float(d.pop("distance", 1.0))
        d["score"] = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
        out.append(d)
    return out


# --- SQLite fallback (in-Python cosine) ------------------------------------

def _retrieve_sqlite(
    company_id: str,
    query_embedding: List[float],
    top_k: int,
    source_types: Optional[Sequence[str]],
) -> List[Dict[str, Any]]:
    """
    Pulls all chunks for the company, computes cosine similarity in
    Python, sorts. Linear in chunk count — acceptable at the expected
    pilot scale (<500 chunks / company). Production uses pgvector.
    """
    where_extra = ""
    params: Dict[str, Any] = {"co": company_id}
    if source_types:
        names = list(source_types)
        placeholders = ", ".join(f":st_{i}" for i in range(len(names)))
        where_extra = f" AND source_type IN ({placeholders})"
        for i, n in enumerate(names):
            params[f"st_{i}"] = n
    sql = (
        "SELECT id, source_type, source_ref, chunk_text, chunk_metadata, embedding "
        "FROM policy_assistant_chunks WHERE company_id = :co" + where_extra
    )
    with db.engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    scored: List[Dict[str, Any]] = []
    for r in rows:
        emb_raw = r["embedding"]
        emb: List[float] = []
        if isinstance(emb_raw, str) and emb_raw:
            try:
                emb = json.loads(emb_raw)
            except Exception:
                emb = []
        elif isinstance(emb_raw, list):
            emb = list(emb_raw)
        sim = cosine_similarity(query_embedding, emb)
        meta_raw = r["chunk_metadata"]
        if isinstance(meta_raw, str):
            try:
                meta = json.loads(meta_raw)
            except Exception:
                meta = {}
        else:
            meta = meta_raw or {}
        scored.append({
            "id": r["id"],
            "source_type": r["source_type"],
            "source_ref": r["source_ref"],
            "chunk_text": r["chunk_text"],
            "chunk_metadata": meta,
            "score": sim,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: max(1, min(top_k, 50))]

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
from datetime import datetime, timezone
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
    min_similarity_score: float = 0.25,
) -> List[Dict[str, Any]]:
    """
    Top-K retrieval. Returns at most `top_k` chunks for `company_id`,
    ranked by an adjusted score: raw cosine similarity, with a quality floor
    (`min_similarity_score`, default 0.25; pass 0.0 to disable), a trust_tier
    boost, and a fetched_at freshness decay (W2/AIQ-836).

    Each returned chunk carries `raw_score`, `adjusted_score`, `trust_tier`,
    `fetched_at`, and `is_stale`.

    Empty list when:
      - company_id missing
      - query empty / whitespace-only
      - company has no indexed chunks yet (or all fall below the floor)
    """
    if not company_id:
        return []
    if not query or not query.strip():
        return []

    embedder = embedder or get_default_embedder()
    q_emb = embedder.embed(query)

    # Over-fetch a candidate pool so the floor + trust/freshness rerank have
    # headroom to reorder before we trim to top_k.
    candidate_k = min(50, max(top_k * 4, top_k))
    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        raw = _retrieve_sqlite(company_id, q_emb, candidate_k, source_types)
    else:
        raw = _retrieve_postgres(company_id, q_emb, candidate_k, source_types)
    return _rank_and_trim(raw, min_similarity_score=min_similarity_score, top_k=top_k)


# --- Ranking: similarity floor + trust_tier boost + freshness decay (W2) ----

_TIER_BOOST = {1: 1.0, 2: 0.9, 3: 0.75}


def _coerce_trust_tier(value: Any) -> Optional[int]:
    """Coerce a trust_tier signal (int or numeric string) to 1/2/3, else None."""
    if value is None:
        return None
    try:
        t = int(value)
    except (TypeError, ValueError):
        return None
    return t if t in (1, 2, 3) else None


def _coerce_fetched_at(value: Any) -> Optional[datetime]:
    """Coerce a fetched_at signal (ISO string or datetime) to an aware UTC dt."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _rank_and_trim(
    chunks: List[Dict[str, Any]],
    *,
    min_similarity_score: float,
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Apply the quality floor + provenance-aware reranking (W2/AIQ-836).

    - Floor: drop chunks whose raw cosine score < min_similarity_score
      (pass 0.0 to disable).
    - trust_tier boost (x1.0 / x0.9 / x0.75 for tier 1/2/3; neutral when absent).
    - fetched_at freshness decay (x0.85 if >90d old, x0.70 if >180d; neutral when null).
    Boost/decay affect RANKING only; the raw score is preserved.

    Premise note: policy_assistant_chunks has NO trust_tier / fetched_at columns —
    these signals are read from `chunk_metadata` when present (e.g. web-ingested
    corpora). Matrix-derived policy chunks carry neither today, so for them this is
    effectively the similarity floor until provenance is added to the metadata.
    """
    now = datetime.now(timezone.utc)
    out: List[Dict[str, Any]] = []
    for c in chunks:
        raw = float(c.get("score", 0.0))
        if min_similarity_score > 0 and raw < min_similarity_score:
            continue
        meta = c.get("chunk_metadata") or {}
        tier = _coerce_trust_tier(meta.get("trust_tier"))
        fetched_at = _coerce_fetched_at(meta.get("fetched_at"))
        tier_boost = _TIER_BOOST.get(tier, 1.0)
        if fetched_at is None:
            freshness, is_stale = 1.0, False
        else:
            days_old = (now - fetched_at).days
            if days_old > 180:
                freshness, is_stale = 0.70, True
            elif days_old > 90:
                freshness, is_stale = 0.85, False
            else:
                freshness, is_stale = 1.0, False
        enriched = dict(c)
        enriched["raw_score"] = raw
        enriched["adjusted_score"] = raw * tier_boost * freshness
        enriched["trust_tier"] = tier
        enriched["fetched_at"] = fetched_at.isoformat() if fetched_at else None
        enriched["is_stale"] = is_stale
        out.append(enriched)
    out.sort(key=lambda c: c["adjusted_score"], reverse=True)
    return out[: max(1, top_k)]


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
    # F3/AIQ-834: set the request-scoped company GUC the RLS second-barrier
    # policy reads, then run the similarity query in the SAME transaction.
    # set_config(..., is_local=true) is transaction-local and survives the
    # Supabase transaction-mode pooler (unlike a session-level SET). Harmless
    # when connected as the superuser (RLS bypassed); load-bearing once the
    # backend connects as the non-superuser relopass_api role.
    with db.request_engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_company_id', :co, true)"),
            {"co": company_id},
        )
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

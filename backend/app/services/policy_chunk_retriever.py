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
import os
import uuid
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

# W2/AIQ-836 retrieval quality gates.
#
# NOTE on schema reality: policy_assistant_chunks has NO `trust_tier` or
# `fetched_at` column (the original task brief assumed they existed). The
# trust signal lives in chunk_metadata->>'source_tier' (string "1"/"2", and
# NULL for HR matrix_benefit chunks, which is correct — tiering is an
# official-source concept), and the freshness signal uses the `created_at`
# column. A null/absent tier maps to a neutral 1.0 boost so HR chunks are
# unaffected.
_DEFAULT_MIN_SIMILARITY = 0.25
_TIER_BOOST = {1: 1.0, 2: 0.9, 3: 0.75}

# P4: optional lexical second-pass reranker (see policy_rerank.py). Default OFF —
# when the flag is unset the reranker is never imported and ranking is byte-
# identical to pre-P4. When ON, the candidate pool is widened before reranking so
# the second pass can recover relevant chunks that the first pass ranked just
# outside top_k.
_RERANK_POOL_FACTOR = 3


def _rerank_enabled() -> bool:
    return os.environ.get("POLICY_RAG_RERANK", "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_tier(value: Any) -> Optional[int]:
    """source_tier arrives as a string ('1'/'2') or None. Coerce to int or None."""
    if value is None:
        return None
    try:
        s = str(value).strip()
        return int(s) if s else None
    except (ValueError, TypeError):
        return None


def _days_old(created: Any, now: datetime) -> int:
    """Age in days from a timestamptz/ISO string. Missing/unparseable -> 0 (neutral)."""
    if not created:
        return 0
    try:
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0, (now - created).days)
    except Exception:
        return 0


def _apply_quality_gates(
    chunks: List[Dict[str, Any]],
    *,
    min_similarity_score: float,
    top_k: int,
    now: Optional[datetime] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Apply the W2 quality gates to already-fetched chunks:
      1. Similarity floor — drop chunks whose raw similarity < min_similarity_score
         (pass min_similarity_score=0.0 to disable).
      2. Trust-tier boost — x1.0 / x0.9 / x0.75 for tier 1 / 2 / 3; neutral (x1.0)
         when source_tier is null/absent.
      3. Freshness decay — x0.85 when >90 days old, x0.70 when >180 days old.
    Re-sorts by adjusted_score DESC and returns the top_k. Pure function — no DB.
    Each chunk's existing `score` is preserved; raw_score, adjusted_score,
    source_tier, and is_stale are added.
    """
    now = now or datetime.now(timezone.utc)
    scored: List[Dict[str, Any]] = []
    for c in chunks:
        raw = float(c.get("score") or 0.0)
        if min_similarity_score > 0.0 and raw < min_similarity_score:
            continue
        meta = c.get("chunk_metadata") or {}
        tier = _parse_tier(meta.get("source_tier") if isinstance(meta, dict) else None)
        tier_boost = _TIER_BOOST.get(tier, 1.0)
        days_old = _days_old(c.get("created_at"), now)
        freshness = 0.70 if days_old > 180 else (0.85 if days_old > 90 else 1.0)
        scored.append({
            **c,
            "raw_score": raw,
            "source_tier": tier,
            "adjusted_score": raw * tier_boost * freshness,
            "is_stale": days_old > 180,
        })
    scored.sort(key=lambda c: c["adjusted_score"], reverse=True)
    # P4: optional lexical second-pass rerank, BETWEEN the sort and the top_k
    # truncation. OFF path (no query OR flag unset) is byte-identical to pre-P4.
    if query and _rerank_enabled():
        from .policy_rerank import rerank_chunks
        scored = rerank_chunks(query, scored)
    return scored[: max(1, top_k)]


def retrieve(
    *,
    company_id: str,
    query: str,
    top_k: int = 8,
    source_types: Optional[Sequence[str]] = None,
    embedder: Optional[Embedder] = None,
    min_similarity_score: float = _DEFAULT_MIN_SIMILARITY,
) -> List[Dict[str, Any]]:
    """
    Top-K retrieval. Returns at most `top_k` chunks for `company_id`,
    ordered by descending *adjusted* similarity (W2 quality gates applied).

    Each returned chunk gains: raw_score, adjusted_score, source_tier, is_stale
    (the legacy `score` field is preserved unchanged).

    `min_similarity_score` (default 0.25) drops low-similarity chunks; pass 0.0
    to disable the floor entirely.

    Empty list when:
      - company_id missing
      - query empty / whitespace-only
      - company has no indexed chunks yet (or all below the floor)
    """
    if not company_id:
        return []
    if not query or not query.strip():
        return []

    embedder = embedder or get_default_embedder()
    # GDPR Art. 28/44 (SEC-03): the user's free-text query is embedded by a
    # US LLM sub-processor (OpenAI embeddings), so mask any PII before egress —
    # the chat-path masking in AnthropicClient does NOT cover this separate
    # embeddings call. Single chokepoint for every retrieval caller.
    from .pii_masker import mask_pii

    q_emb = embedder.embed(mask_pii(query))

    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        return _retrieve_sqlite(company_id, q_emb, top_k, source_types, min_similarity_score, query)
    return _retrieve_postgres(company_id, q_emb, top_k, source_types, min_similarity_score, query)


# --- Postgres (pgvector) ---------------------------------------------------

def _retrieve_postgres(
    company_id: str,
    query_embedding: List[float],
    top_k: int,
    source_types: Optional[Sequence[str]],
    min_similarity_score: float = _DEFAULT_MIN_SIMILARITY,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Uses pgvector's cosine distance operator (<=>). Distance is in
    [0, 2]; we convert to similarity = 1 - (distance / 2) clipped to
    [0, 1] for a comparable shape with the SQLite path.
    """
    # F3: policy_assistant_chunks.company_id is a uuid column, and the request
    # path may run as the non-superuser relopass_api role. A non-UUID company id
    # (e.g. a legacy seed slug like "seed-emp-testingapril") can never match a
    # uuid; binding it as :co makes psycopg2 raise InvalidTextRepresentation ->
    # 500. Such a company has no chunks by definition, so return empty instead.
    # (The RLS policy's safe_uuid() guard handles the same case at the policy
    # layer; this guards the query's own WHERE company_id = :co predicate.)
    try:
        uuid.UUID(str(company_id))
    except (ValueError, AttributeError, TypeError):
        return []
    where_extra = ""
    # P4: widen the candidate pool before reranking, but ONLY when the flag is on
    # — OFF keeps the original LIMIT min(top_k, 50) exactly.
    pool_k = top_k * _RERANK_POOL_FACTOR if (query and _rerank_enabled()) else top_k
    params: Dict[str, Any] = {"co": company_id, "k": int(max(1, min(pool_k, 50)))}
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
        "SELECT id, source_type, source_ref, chunk_text, chunk_metadata, created_at, "
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
    return _apply_quality_gates(
        out, min_similarity_score=min_similarity_score, top_k=top_k, query=query
    )


# --- SQLite fallback (in-Python cosine) ------------------------------------

def _retrieve_sqlite(
    company_id: str,
    query_embedding: List[float],
    top_k: int,
    source_types: Optional[Sequence[str]],
    min_similarity_score: float = _DEFAULT_MIN_SIMILARITY,
    query: Optional[str] = None,
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
    # W2 quality gates (floor + tier boost + freshness). The dev SQLite schema
    # has no created_at, so freshness is neutral here — acceptable for dev/tests.
    # P4: sqlite already pulls the full company corpus, so the pool is wide; pass
    # `query` so the flag-gated rerank can re-order before truncation.
    return _apply_quality_gates(
        scored, min_similarity_score=min_similarity_score, top_k=min(top_k, 50), query=query
    )

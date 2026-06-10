"""
Immigration RAG retriever (P1-01a) — first stage of the roadmap pipeline.

Wraps the company-scoped `policy_chunk_retriever` and adds the
immigration-specific applicability filters the generator needs: corridor
(origin→destination) and visa pathway type. Immigration rules are not
company-specific, so they live under a single synthetic corpus "company"
(`IMMIGRATION_CORPUS_COMPANY_ID`) and are tagged with corridor + pathway_type
in `chunk_metadata`.

`policy_chunk_retriever` only filters by company_id + source_type, so this
wrapper over-fetches and then post-filters the result set down to the
applicable corridor/pathway. An uncovered corridor yields an empty list,
which is the retriever-side basis for the generator's RULE_NOT_FOUND guard
(P1-01b) — we never substitute a different corridor's rules.

Returned chunk shape is unchanged from `policy_chunk_retriever.retrieve`
(id, source_type, source_ref, chunk_text, chunk_metadata, score).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Protocol, Sequence

from sqlalchemy import text

from ...database import db
from . import source_reliability_config as _rel_cfg
from .policy_assistant_embedder import Embedder, cosine_similarity, get_default_embedder

log = logging.getLogger(__name__)

# N3/AIQ-842 retrieval quality gates.
_IMMIGRATION_MIN_SIMILARITY = float(os.getenv("IMMIGRATION_MIN_SIMILARITY", "0.25"))
_TIER_BOOST = {1: 1.0, 2: 0.9, 3: 0.75}

# W3-2 hybrid retrieval. When enabled, a BM25/keyword leg (Postgres FTS or, on
# the sqlite eval/test path, an in-Python BM25) is fused with the pgvector cosine
# leg via Reciprocal Rank Fusion. Ships OFF (vector-only, byte-identical to the
# prior behaviour); flip the env flag on after the evals confirm no regression —
# mirrors the dormant IMMIGRATION_RELIABILITY_WEIGHT rollout pattern.
_RRF_C = int(os.getenv("IMMIGRATION_RRF_C", "60"))  # RRF damping constant
_BM25_K1 = 1.5
_BM25_B = 0.75
_WORD_RE = re.compile(r"[a-z0-9]+")


def _hybrid_enabled() -> bool:
    """Read the flag at call time so tests can toggle it via monkeypatch/env."""
    return os.getenv("IMMIGRATION_HYBRID_RETRIEVAL", "").strip().lower() in (
        "1", "true", "on", "yes",
    )

# Synthetic corpus owner: immigration rules are corridor-scoped, not
# company-scoped, but policy_chunk_retriever requires a company_id. The
# policy_assistant_chunks.company_id column is `uuid`, so this must be a real
# UUID (not a free-form string). Fixed, deterministic value derived from
# uuid5(NAMESPACE_URL, "relopass:immigration_corpus") — used both here and by
# the corpus indexer (backend/scripts/index_corridor_corpus_chunks.py) so the
# rows it writes and the rows this retriever reads share the same partition.
IMMIGRATION_CORPUS_COMPANY_ID = "c0de6492-13b0-5222-80db-9f9e2abdd913"
IMMIGRATION_SOURCE_TYPE = "immigration_rule"

# Over-fetch factor: policy_chunk_retriever can't filter by corridor, so we
# pull more than top_k and trim after corridor/pathway filtering.
_OVER_FETCH_FACTOR = 5
_MAX_FETCH = 50  # policy_chunk_retriever caps top_k at 50 anyway.


@dataclass(frozen=True)
class UserProfile:
    """Classified mobility subject. Country fields are ISO-2 codes."""

    nationality: str
    origin_country: str
    destination_country: str
    is_eea: Optional[bool] = None


@dataclass(frozen=True)
class PathClassification:
    """Output of the (upstream) pathway classifier. `corridor` is derived
    from the profile when not supplied explicitly."""

    pathway_type: str
    corridor: Optional[str] = None


def corridor_key(origin: str, destination: str) -> str:
    """Canonical corridor string, e.g. ("fr", "no") -> "FR→NO"."""
    return f"{origin.strip().upper()}→{destination.strip().upper()}"


def retrieve_for_profile(
    *,
    profile: UserProfile,
    classification: PathClassification,
    top_k: int = 10,
    company_id: str = IMMIGRATION_CORPUS_COMPANY_ID,  # accepted for back-compat; unused
    source_type: str = IMMIGRATION_SOURCE_TYPE,        # accepted for back-compat; unused
    embedder: Optional[Embedder] = None,
    engine=None,
    min_similarity_score: Optional[float] = None,
    trust_tiers: Optional[Sequence[int]] = None,
    include_embedding: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve the immigration-rule chunks for this profile's corridor, ranked by
    relevance, from immigration_corpus_chunks (N2/AIQ-841) with the N3/AIQ-842
    quality gates applied (similarity floor + trust_tier boost + freshness decay +
    corridor hard-filter). Corridor-scoped only.

    Returns an empty list when the profile is incomplete or the corridor is
    uncovered/below the floor — never cross-corridor substitutes.

    Return shape per chunk: id, source_type, source_ref, source_url, chunk_text,
    chunk_metadata, corridor, trust_tier, fetched_at, score, raw_score,
    adjusted_score, is_stale.
    """
    if not profile.origin_country or not profile.destination_country:
        return []

    corridor = classification.corridor or corridor_key(
        profile.origin_country, profile.destination_country
    )
    # Corpus rows store the underscore key form ('FR_NO'); corridor_key/UI use
    # the arrow form ('FR→NO'). Normalize for the query.
    corridor_db = corridor.replace("→", "_")
    query = _build_query(profile, classification, corridor)

    embedder = embedder or get_default_embedder()
    q_emb = embedder.embed(query)
    engine = engine or db.engine
    k = int(max(1, min(top_k, 50)))
    # Over-fetch a little so the tier/freshness re-rank can promote within-floor chunks.
    fetch_k = min(50, max(k, k * 3))

    # W3-2: hybrid (vector + BM25 keyword, RRF-fused) behind a flag; default OFF
    # → VectorRetriever, byte-identical to the prior path. When fused, the RRF
    # score is the relevance base the quality gates scale.
    hybrid = _hybrid_enabled()
    retriever: RetrieverProtocol = HybridRetriever() if hybrid else VectorRetriever()
    raw = retriever.candidates(
        engine=engine, corridor_db=corridor_db, q_emb=q_emb, query=query,
        fetch_k=fetch_k, trust_tiers=trust_tiers, include_embedding=include_embedding,
    )

    # Corridor hard-filter (belt-and-suspenders; the query already scopes corridor).
    raw = [c for c in raw if c.get("corridor") == corridor_db]
    min_sim = _IMMIGRATION_MIN_SIMILARITY if min_similarity_score is None else min_similarity_score
    result = _apply_quality_gates(
        raw, min_similarity=min_sim, top_k=k, rank_base=("rrf_score" if hybrid else None),
    )

    log.info(
        "immigration_retriever corridor=%s pathway=%s returned=%d min_sim=%.2f",
        corridor, classification.pathway_type, len(result), min_sim,
    )
    return result


def retrieve_with_staleness(
    *,
    profile: UserProfile,
    classification: PathClassification,
    top_k: int = 10,
    embedder: Optional[Embedder] = None,
    engine=None,
    min_similarity_score: Optional[float] = None,
) -> Dict[str, Any]:
    """
    N3/AIQ-842 staleness-aware wrapper for the answer generator (N4): same
    retrieval as retrieve_for_profile, but returns
    {chunks, all_stale_warning, oldest_fetched_at}. Kept separate so the
    list-returning retrieve_for_profile contract (W1 endpoint + rag_roadmap
    pipeline) is unchanged.
    """
    chunks = retrieve_for_profile(
        profile=profile, classification=classification, top_k=top_k,
        embedder=embedder, engine=engine, min_similarity_score=min_similarity_score,
    )
    all_stale = bool(chunks) and all(c.get("is_stale") for c in chunks)
    fetched = [c.get("fetched_at") for c in chunks if c.get("fetched_at")]
    # ISO-8601 strings sort chronologically.
    oldest = min(fetched) if fetched else None
    return {"chunks": chunks, "all_stale_warning": all_stale, "oldest_fetched_at": oldest}


def retrieve_multi_source(
    *,
    profile: UserProfile,
    classification: PathClassification,
    top_k: int = 10,
    embedder: Optional[Embedder] = None,
    engine=None,
    min_similarity_score: Optional[float] = None,
) -> Dict[str, Any]:
    """
    N9/AIQ-849 multi-source triangulation retrieval. Runs two corridor-scoped
    queries: one restricted to official (trust_tier=1) sources and one unrestricted
    (all tiers). Returns both sets WITH embeddings so the source reconciler can
    compute cross-tier agreement. Falls back gracefully to single-source when only
    one tier of sources exists for the corridor (e.g. no official sources crawled
    yet) — the empty set simply yields official_only / secondary_only downstream.
    """
    common = dict(
        profile=profile, classification=classification, top_k=top_k,
        embedder=embedder, engine=engine, min_similarity_score=min_similarity_score,
        include_embedding=True,
    )
    official_chunks = retrieve_for_profile(trust_tiers=[1], **common)
    all_chunks = retrieve_for_profile(trust_tiers=None, **common)
    return {"official_chunks": official_chunks, "secondary_chunks": all_chunks}


def _days_old(fetched_at: Any, now: datetime) -> int:
    if not fetched_at:
        return 0
    try:
        dt = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00")) if isinstance(fetched_at, str) else fetched_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 0


def _apply_quality_gates(
    chunks: List[Dict[str, Any]], *, min_similarity: float, top_k: int,
    now: Optional[datetime] = None, rank_base: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Similarity floor + trust_tier boost + freshness decay; re-sort by adjusted_score.

    The similarity floor always applies to the cosine `score` (so semantically
    irrelevant keyword-only matches are still dropped). `rank_base` selects the
    relevance base the tier/freshness/reliability multipliers scale: None →
    cosine `score` (vector default, unchanged); a key name (e.g. "rrf_score") →
    that fused signal (W3-2 hybrid).
    """
    now = now or datetime.now(timezone.utc)
    out: List[Dict[str, Any]] = []
    for c in chunks:
        raw = float(c.get("score") or 0.0)
        if min_similarity > 0.0 and raw < min_similarity:
            continue
        tier = c.get("trust_tier")
        try:
            tier = int(tier) if tier is not None and str(tier).strip() != "" else None
        except (ValueError, TypeError):
            tier = None
        boost = _TIER_BOOST.get(tier, 1.0)
        days = _days_old(c.get("fetched_at"), now)
        freshness = 0.70 if days > 180 else (0.85 if days > 90 else 1.0)
        # N8/AIQ-848: feedback-loop reliability is the 4th ranking factor, blended
        # by RELIABILITY_WEIGHT (0 = dormant/no effect; ships off by default).
        factor = _rel_cfg.reliability_factor(c.get("reliability_score"))
        base = float(c.get(rank_base) or 0.0) if rank_base else raw
        out.append({**c, "raw_score": raw,
                    "adjusted_score": base * boost * freshness * factor, "is_stale": days > 180})
    out.sort(key=lambda x: x["adjusted_score"], reverse=True)
    return out[: max(1, top_k)]


def _shape(meta_raw: Any, *, id_, source_url, chunk_text, corridor, trust_tier, fetched_at, score,
           reliability_score: Any = None, embedding=None) -> Dict[str, Any]:
    meta = meta_raw
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    # N8/AIQ-848: feedback-loop reliability (neutral when absent/null).
    rel = _rel_cfg.NEUTRAL_RELIABILITY if reliability_score is None else float(reliability_score)
    shaped = {
        "id": str(id_),
        "source_type": IMMIGRATION_SOURCE_TYPE,
        "source_ref": source_url,
        "source_url": source_url,
        "chunk_text": chunk_text,
        "chunk_metadata": meta or {},
        "corridor": corridor,
        "trust_tier": trust_tier,
        "fetched_at": str(fetched_at) if fetched_at is not None else None,
        "score": max(0.0, min(1.0, float(score))),
        "reliability_score": max(0.0, min(1.0, rel)),
    }
    # N9/AIQ-849: triangulation needs the raw embedding vector to compute cross-tier
    # cosine agreement. Only carried when requested (retrieve_multi_source) so the
    # default retrieval payload stays lean.
    if embedding is not None:
        shaped["embedding"] = embedding
    return shaped


def _tier_filter_sql(trust_tiers: Optional[Sequence[int]]) -> str:
    if not trust_tiers:
        return ""
    vals = ", ".join(str(int(t)) for t in trust_tiers)
    return f" AND trust_tier IN ({vals})"


def _retrieve_corpus_postgres(
    engine, corridor_db: str, q_emb: List[float], k: int,
    *, trust_tiers: Optional[Sequence[int]] = None, include_embedding: bool = False,
) -> List[Dict[str, Any]]:
    q = "[" + ",".join(f"{x:.6f}" for x in q_emb) + "]"
    emb_col = ", embedding::text AS emb_text " if include_embedding else " "
    sql = text(
        "SELECT id, corridor, source_url, chunk_text, chunk_metadata, trust_tier, fetched_at, "
        "       reliability_score, "
        "       (embedding <=> CAST(:q AS vector)) AS distance" + emb_col +
        "FROM immigration_corpus_chunks "
        "WHERE corridor = :corridor AND is_active = true" + _tier_filter_sql(trust_tiers) + " "
        "ORDER BY embedding <=> CAST(:q AS vector) ASC LIMIT :k"
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"q": q, "corridor": corridor_db, "k": k}).mappings().all()
    out = []
    for r in rows:
        dist = float(r["distance"] if r["distance"] is not None else 1.0)
        emb = None
        if include_embedding and r.get("emb_text"):
            try:
                emb = json.loads(r["emb_text"])
            except Exception:
                emb = None
        out.append(_shape(
            r["chunk_metadata"], id_=r["id"], source_url=r["source_url"], chunk_text=r["chunk_text"],
            corridor=r["corridor"], trust_tier=r["trust_tier"], fetched_at=r["fetched_at"],
            score=1.0 - (dist / 2.0), reliability_score=r["reliability_score"], embedding=emb,
        ))
    return out


def _retrieve_corpus_sqlite(
    engine, corridor_db: str, q_emb: List[float], k: int,
    *, trust_tiers: Optional[Sequence[int]] = None, include_embedding: bool = False,
) -> List[Dict[str, Any]]:
    base = ("SELECT id, corridor, source_url, chunk_text, chunk_metadata, trust_tier, fetched_at, "
            "embedding{rel} FROM immigration_corpus_chunks WHERE corridor = :corridor AND is_active = 1"
            + _tier_filter_sql(trust_tiers))
    with engine.begin() as conn:
        # reliability_score (N8) is read when present; tolerate older sqlite fixtures
        # that predate the column without forcing a fixture edit.
        try:
            rows = conn.execute(text(base.format(rel=", reliability_score")),
                                {"corridor": corridor_db}).mappings().all()
        except Exception:
            rows = conn.execute(text(base.format(rel="")),
                                {"corridor": corridor_db}).mappings().all()
    scored = []
    for r in rows:
        emb_raw = r["embedding"]
        emb = json.loads(emb_raw) if isinstance(emb_raw, str) and emb_raw else (emb_raw or [])
        scored.append(_shape(
            r["chunk_metadata"], id_=r["id"], source_url=r["source_url"], chunk_text=r["chunk_text"],
            corridor=r["corridor"], trust_tier=r["trust_tier"], fetched_at=r["fetched_at"],
            score=cosine_similarity(q_emb, emb), reliability_score=r.get("reliability_score"),
            embedding=(list(emb) if include_embedding else None),
        ))
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


def _build_query(
    profile: UserProfile, classification: PathClassification, corridor: str
) -> str:
    eea = "EEA" if profile.is_eea else "non-EEA"
    return (
        f"{classification.pathway_type} immigration requirements for a "
        f"{eea} {profile.nationality} national relocating {corridor}"
    )


# ── W3-2 hybrid retrieval ──────────────────────────────────────────────────


class RetrieverProtocol(Protocol):
    """A corridor-scoped candidate source. Returns shaped chunk dicts (see
    `_shape`) ordered by the leg's native relevance. Every candidate carries a
    cosine `score` regardless of which leg surfaced it, so the shared similarity
    floor in `_apply_quality_gates` stays meaningful across legs."""

    def candidates(
        self, *, engine, corridor_db: str, q_emb: List[float], query: str, fetch_k: int,
        trust_tiers: Optional[Sequence[int]] = None, include_embedding: bool = False,
    ) -> List[Dict[str, Any]]:
        ...


class VectorRetriever:
    """pgvector cosine leg (Postgres) / in-Python cosine (sqlite) — the prior
    default behaviour, unchanged."""

    def candidates(self, *, engine, corridor_db, q_emb, query, fetch_k,
                   trust_tiers=None, include_embedding=False):
        fn = _retrieve_corpus_sqlite if engine.dialect.name == "sqlite" else _retrieve_corpus_postgres
        return fn(engine, corridor_db, q_emb, fetch_k,
                  trust_tiers=trust_tiers, include_embedding=include_embedding)


class KeywordRetriever:
    """BM25/keyword leg. Postgres uses native FTS (`ts_rank` over the `chunk_tsv`
    generated column); sqlite uses an in-Python BM25 over `chunk_text` so the
    eval/test path (hash embedder + sqlite fixtures) exercises hybrid too."""

    def candidates(self, *, engine, corridor_db, q_emb, query, fetch_k,
                   trust_tiers=None, include_embedding=False):
        if engine.dialect.name == "sqlite":
            return _retrieve_keyword_sqlite(engine, corridor_db, q_emb, query, fetch_k,
                                            trust_tiers=trust_tiers, include_embedding=include_embedding)
        return _retrieve_keyword_postgres(engine, corridor_db, q_emb, query, fetch_k,
                                          trust_tiers=trust_tiers, include_embedding=include_embedding)


class HybridRetriever:
    """Reciprocal-Rank-Fusion of the vector + keyword legs."""

    def __init__(self, vector: Optional[RetrieverProtocol] = None,
                 keyword: Optional[RetrieverProtocol] = None, c: int = _RRF_C):
        self._vec = vector or VectorRetriever()
        self._kw = keyword or KeywordRetriever()
        self._c = c

    def candidates(self, *, engine, corridor_db, q_emb, query, fetch_k,
                   trust_tiers=None, include_embedding=False):
        common = dict(engine=engine, corridor_db=corridor_db, q_emb=q_emb, query=query,
                      fetch_k=fetch_k, trust_tiers=trust_tiers, include_embedding=include_embedding)
        vec = self._vec.candidates(**common)
        kw = self._kw.candidates(**common)
        return _rrf_fuse(vec, kw, c=self._c)


def _rrf_fuse(vec_list, kw_list, *, c: int = _RRF_C) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion: score(d) = Σ_legs 1/(c + rank_d) (0-based rank +1).
    Higher = better. Union of both legs; the first-seen shaped dict wins (the
    vector leg carries the embedding when requested)."""
    rrf: Dict[str, float] = {}
    shaped: Dict[str, Dict[str, Any]] = {}
    for lst in (vec_list, kw_list):
        for rank, ch in enumerate(lst):
            cid = str(ch.get("id"))
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (c + rank + 1)
            shaped.setdefault(cid, ch)
    fused: List[Dict[str, Any]] = []
    for cid, score in rrf.items():
        ch = dict(shaped[cid])
        ch["rrf_score"] = score
        fused.append(ch)
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused


def _tokenize(t: str) -> List[str]:
    return _WORD_RE.findall((t or "").lower())


def _bm25_scores(query: str, docs: List[str]) -> List[float]:
    """Deterministic BM25 over a small candidate doc set (a corridor's chunks).
    sqlite path only; Postgres uses native ts_rank."""
    q_terms = set(_tokenize(query))
    if not q_terms or not docs:
        return [0.0] * len(docs)
    tokenized = [_tokenize(d) for d in docs]
    lengths = [len(toks) for toks in tokenized]
    avgdl = (sum(lengths) / len(lengths)) or 1.0
    n_docs = len(docs)
    df = {t: 0 for t in q_terms}
    for toks in tokenized:
        present = set(toks)
        for t in q_terms:
            if t in present:
                df[t] += 1
    scores: List[float] = []
    for toks, dl in zip(tokenized, lengths):
        tf: Dict[str, int] = {}
        for tok in toks:
            if tok in q_terms:
                tf[tok] = tf.get(tok, 0) + 1
        s = 0.0
        for t, f in tf.items():
            n_t = df.get(t, 0)
            idf = math.log(1 + (n_docs - n_t + 0.5) / (n_t + 0.5))
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
            s += idf * (f * (_BM25_K1 + 1)) / (denom or 1.0)
        scores.append(s)
    return scores


def _fetch_corridor_rows_sqlite(engine, corridor_db, *, trust_tiers=None):
    base = ("SELECT id, corridor, source_url, chunk_text, chunk_metadata, trust_tier, fetched_at, "
            "embedding{rel} FROM immigration_corpus_chunks WHERE corridor = :corridor AND is_active = 1"
            + _tier_filter_sql(trust_tiers))
    with engine.begin() as conn:
        try:
            return conn.execute(text(base.format(rel=", reliability_score")), {"corridor": corridor_db}).mappings().all()
        except Exception:
            return conn.execute(text(base.format(rel="")), {"corridor": corridor_db}).mappings().all()


def _retrieve_keyword_sqlite(engine, corridor_db, q_emb, query, k, *, trust_tiers=None, include_embedding=False):
    """sqlite keyword leg: rank the corridor's chunks by in-Python BM25 over
    chunk_text. Only genuine keyword matches (BM25 > 0) earn a keyword rank.
    Each kept chunk still carries a cosine `score` for the shared floor."""
    rows = _fetch_corridor_rows_sqlite(engine, corridor_db, trust_tiers=trust_tiers)
    if not rows:
        return []
    bm25 = _bm25_scores(query, [r["chunk_text"] or "" for r in rows])
    ranked = []
    for r, kw in zip(rows, bm25):
        if kw <= 0.0:
            continue
        emb_raw = r["embedding"]
        emb = json.loads(emb_raw) if isinstance(emb_raw, str) and emb_raw else (emb_raw or [])
        ch = _shape(
            r["chunk_metadata"], id_=r["id"], source_url=r["source_url"], chunk_text=r["chunk_text"],
            corridor=r["corridor"], trust_tier=r["trust_tier"], fetched_at=r["fetched_at"],
            score=cosine_similarity(q_emb, emb), reliability_score=r.get("reliability_score"),
            embedding=(list(emb) if include_embedding else None),
        )
        ranked.append((kw, ch))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in ranked[:k]]


def _retrieve_keyword_postgres(engine, corridor_db, q_emb, query, k, *, trust_tiers=None, include_embedding=False):
    """Postgres keyword leg: FTS `ts_rank` over the `chunk_tsv` generated column.
    The same row returns the cosine distance so kept chunks carry a `score` for
    the shared similarity floor."""
    q = "[" + ",".join(f"{x:.6f}" for x in q_emb) + "]"
    emb_col = ", embedding::text AS emb_text " if include_embedding else " "
    sql = text(
        "SELECT id, corridor, source_url, chunk_text, chunk_metadata, trust_tier, fetched_at, "
        "       reliability_score, (embedding <=> CAST(:q AS vector)) AS distance, "
        "       ts_rank(chunk_tsv, websearch_to_tsquery('english', :kq)) AS kw_rank" + emb_col +
        "FROM immigration_corpus_chunks "
        "WHERE corridor = :corridor AND is_active = true "
        "  AND chunk_tsv @@ websearch_to_tsquery('english', :kq)" + _tier_filter_sql(trust_tiers) + " "
        "ORDER BY kw_rank DESC LIMIT :k"
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"q": q, "kq": query, "corridor": corridor_db, "k": k}).mappings().all()
    out = []
    for r in rows:
        dist = float(r["distance"] if r["distance"] is not None else 1.0)
        emb = None
        if include_embedding and r.get("emb_text"):
            try:
                emb = json.loads(r["emb_text"])
            except Exception:
                emb = None
        out.append(_shape(
            r["chunk_metadata"], id_=r["id"], source_url=r["source_url"], chunk_text=r["chunk_text"],
            corridor=r["corridor"], trust_tier=r["trust_tier"], fetched_at=r["fetched_at"],
            score=1.0 - (dist / 2.0), reliability_score=r["reliability_score"], embedding=emb,
        ))
    return out

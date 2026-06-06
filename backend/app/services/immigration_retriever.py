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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .policy_assistant_embedder import Embedder, cosine_similarity, get_default_embedder

log = logging.getLogger(__name__)

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
) -> List[Dict[str, Any]]:
    """
    Retrieve the immigration-rule chunks for this profile's corridor, ranked by
    relevance, from immigration_corpus_chunks (N2/AIQ-841). Corridor-scoped only.

    Returns an empty list when the profile is incomplete or the corridor is
    uncovered (no chunks) — never cross-corridor substitutes.

    Return shape per chunk is backward-compatible with the prior retriever:
    id, source_type, source_ref, chunk_text, chunk_metadata, score (+ corridor,
    trust_tier, fetched_at, source_url).
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

    if engine.dialect.name == "sqlite":
        result = _retrieve_corpus_sqlite(engine, corridor_db, q_emb, k)
    else:
        result = _retrieve_corpus_postgres(engine, corridor_db, q_emb, k)

    log.info(
        "immigration_retriever corridor=%s pathway=%s returned=%d",
        corridor, classification.pathway_type, len(result),
    )
    return result


def _shape(meta_raw: Any, *, id_, source_url, chunk_text, corridor, trust_tier, fetched_at, score) -> Dict[str, Any]:
    meta = meta_raw
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return {
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
    }


def _retrieve_corpus_postgres(engine, corridor_db: str, q_emb: List[float], k: int) -> List[Dict[str, Any]]:
    q = "[" + ",".join(f"{x:.6f}" for x in q_emb) + "]"
    sql = text(
        "SELECT id, corridor, source_url, chunk_text, chunk_metadata, trust_tier, fetched_at, "
        "       (embedding <=> CAST(:q AS vector)) AS distance "
        "FROM immigration_corpus_chunks "
        "WHERE corridor = :corridor AND is_active = true "
        "ORDER BY embedding <=> CAST(:q AS vector) ASC LIMIT :k"
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"q": q, "corridor": corridor_db, "k": k}).mappings().all()
    out = []
    for r in rows:
        dist = float(r["distance"] if r["distance"] is not None else 1.0)
        out.append(_shape(
            r["chunk_metadata"], id_=r["id"], source_url=r["source_url"], chunk_text=r["chunk_text"],
            corridor=r["corridor"], trust_tier=r["trust_tier"], fetched_at=r["fetched_at"],
            score=1.0 - (dist / 2.0),
        ))
    return out


def _retrieve_corpus_sqlite(engine, corridor_db: str, q_emb: List[float], k: int) -> List[Dict[str, Any]]:
    sql = text(
        "SELECT id, corridor, source_url, chunk_text, chunk_metadata, trust_tier, fetched_at, embedding "
        "FROM immigration_corpus_chunks WHERE corridor = :corridor AND is_active = 1"
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"corridor": corridor_db}).mappings().all()
    scored = []
    for r in rows:
        emb_raw = r["embedding"]
        emb = json.loads(emb_raw) if isinstance(emb_raw, str) and emb_raw else (emb_raw or [])
        scored.append(_shape(
            r["chunk_metadata"], id_=r["id"], source_url=r["source_url"], chunk_text=r["chunk_text"],
            corridor=r["corridor"], trust_tier=r["trust_tier"], fetched_at=r["fetched_at"],
            score=cosine_similarity(q_emb, emb),
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

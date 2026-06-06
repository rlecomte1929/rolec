"""
W2 / AIQ-836 — similarity floor + trust_tier boost + fetched_at freshness in
policy_chunk_retriever. Tests the pure ranking function directly (deterministic,
no DB) plus a retrieve() integration with the DB backend mocked.

Premise note: policy_assistant_chunks has no trust_tier/fetched_at columns; the
signals are read from chunk_metadata when present (neutral when absent), so the
boost/decay paths are exercised here with synthetic metadata.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.services import policy_chunk_retriever as r


def _chunk(cid: str, score: float, meta: dict | None = None) -> dict:
    return {
        "id": cid,
        "source_type": "matrix_benefit",
        "source_ref": f"b.{cid}",
        "chunk_text": f"chunk {cid}",
        "chunk_metadata": meta or {},
        "score": score,
    }


# --- floor -----------------------------------------------------------------

def test_floor_excludes_below_threshold() -> None:
    out = r._rank_and_trim(
        [_chunk("hi", 0.30), _chunk("lo", 0.20)],
        min_similarity_score=0.25,
        top_k=10,
    )
    ids = [c["id"] for c in out]
    assert ids == ["hi"]
    assert all(c["raw_score"] >= 0.25 for c in out)


def test_floor_zero_disables() -> None:
    out = r._rank_and_trim(
        [_chunk("hi", 0.30), _chunk("lo", 0.20)],
        min_similarity_score=0.0,
        top_k=10,
    )
    assert {c["id"] for c in out} == {"hi", "lo"}


# --- trust_tier boost ------------------------------------------------------

def test_tier1_outranks_tier3_within_boost_margin() -> None:
    # tier_3 raw 0.82 -> 0.615; tier_1 raw 0.80 -> 0.80 => tier_1 first.
    out = r._rank_and_trim(
        [_chunk("t3", 0.82, {"trust_tier": 3}), _chunk("t1", 0.80, {"trust_tier": 1})],
        min_similarity_score=0.0,
        top_k=10,
    )
    assert [c["id"] for c in out] == ["t1", "t3"]
    by_id = {c["id"]: c for c in out}
    assert round(by_id["t3"]["adjusted_score"], 3) == 0.615
    assert by_id["t1"]["adjusted_score"] == 0.80
    # raw preserved
    assert by_id["t3"]["raw_score"] == 0.82


def test_string_trust_tier_is_coerced() -> None:
    out = r._rank_and_trim([_chunk("x", 0.5, {"trust_tier": "2"})], min_similarity_score=0.0, top_k=1)
    assert out[0]["trust_tier"] == 2
    assert out[0]["adjusted_score"] == 0.45  # 0.5 * 0.9


# --- freshness decay -------------------------------------------------------

def test_stale_chunk_flagged_and_decayed() -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    out = r._rank_and_trim([_chunk("old", 0.90, {"fetched_at": old})], min_similarity_score=0.0, top_k=1)
    assert out[0]["is_stale"] is True
    assert round(out[0]["adjusted_score"], 3) == 0.63  # 0.90 * 0.70


def test_mid_age_decays_without_stale_flag() -> None:
    mid = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    out = r._rank_and_trim([_chunk("mid", 0.80, {"fetched_at": mid})], min_similarity_score=0.0, top_k=1)
    assert out[0]["is_stale"] is False
    assert round(out[0]["adjusted_score"], 3) == 0.68  # 0.80 * 0.85


def test_absent_provenance_is_neutral() -> None:
    out = r._rank_and_trim([_chunk("plain", 0.7)], min_similarity_score=0.0, top_k=1)
    c = out[0]
    assert c["trust_tier"] is None
    assert c["fetched_at"] is None
    assert c["is_stale"] is False
    assert c["adjusted_score"] == 0.7


def test_returned_chunk_has_all_w2_fields() -> None:
    out = r._rank_and_trim([_chunk("x", 0.5)], min_similarity_score=0.0, top_k=1)
    for field in ("raw_score", "adjusted_score", "trust_tier", "fetched_at", "is_stale"):
        assert field in out[0], f"missing {field}"


def test_top_k_trim_after_rerank() -> None:
    chunks = [_chunk(str(i), 0.5 + i / 100) for i in range(10)]
    out = r._rank_and_trim(chunks, min_similarity_score=0.0, top_k=3)
    assert len(out) == 3
    # highest raw scores (no provenance) win after neutral rerank
    assert [c["id"] for c in out] == ["9", "8", "7"]


# --- retrieve() integration (DB backend mocked) ----------------------------

class _FakeEmbedder:
    def embed(self, query: str):
        return [0.1, 0.1, 0.1, 0.1]


def test_retrieve_applies_floor_and_rerank(monkeypatch) -> None:
    fake = [
        _chunk("t3", 0.30, {"trust_tier": 3}),   # 0.30*0.75 = 0.225
        _chunk("lo", 0.20),                       # floored (< 0.25)
        _chunk("t1", 0.28, {"trust_tier": 1}),   # 0.28*1.0 = 0.28  -> ranks first
    ]
    monkeypatch.setattr(r, "_retrieve_sqlite", lambda *a, **k: list(fake))
    monkeypatch.setattr(r, "_retrieve_postgres", lambda *a, **k: list(fake))

    out = r.retrieve(
        company_id="co-a",
        query="housing allowance",
        top_k=10,
        embedder=_FakeEmbedder(),
        min_similarity_score=0.25,
    )
    ids = [c["id"] for c in out]
    assert "lo" not in ids               # floor applied
    assert ids[0] == "t1"                # tier-1 boost reranked above tier-3
    assert all(c["raw_score"] >= 0.25 for c in out)

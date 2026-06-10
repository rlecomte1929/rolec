"""
W3-2 hybrid retrieval tests — BM25 keyword leg fused with pgvector cosine via RRF
behind the IMMIGRATION_HYBRID_RETRIEVAL flag.

Covers (sqlite + hash embedder, no network):
  - flag OFF → VectorRetriever path used (HybridRetriever never constructed),
    result byte-identical to the prior vector-only behaviour.
  - flag ON → HybridRetriever used; result stays corridor-scoped + floored and
    surfaces a keyword-strong chunk.
  - _bm25_scores ranking + zero on no-overlap.
  - _rrf_fuse: union + a doc in both legs outranks single-leg docs.
  - KeywordRetriever sqlite leg: BM25-ordered, zero-overlap excluded, carries a
    cosine `score` for the shared floor.
  - quality gates preserved: similarity floor still drops sub-floor chunks.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.services import immigration_retriever as ir  # noqa: E402
from backend.app.services.immigration_retriever import (  # noqa: E402
    HybridRetriever,
    KeywordRetriever,
    PathClassification,
    UserProfile,
    VectorRetriever,
    _bm25_scores,
    _rrf_fuse,
)
from backend.app.services.policy_assistant_embedder import HashEmbedder  # noqa: E402

_SCHEMA = (
    "CREATE TABLE immigration_corpus_chunks ("
    "id TEXT PRIMARY KEY, corridor TEXT NOT NULL, source_doc_id TEXT, source_url TEXT NOT NULL, "
    "chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL, chunk_metadata TEXT DEFAULT '{}', "
    "trust_tier INTEGER NOT NULL DEFAULT 2, fetched_at TEXT NOT NULL, embedding TEXT, "
    "content_hash TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT)"
)

# Chunk texts: one is keyword-rich for the FR→NO query, one is keyword-empty,
# the rest are generic corridor filler.
_KW_HIT = "immigration requirements eea fr national relocating residence registration"
_KW_MISS = "zzz unrelated content concerning maritime shipping tariffs"
_FILLER = [f"france norway generic relocation note number {i}" for i in range(6)]


def _seed_engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    emb = HashEmbedder()
    rows = [("kw-hit", _KW_HIT), ("kw-miss", _KW_MISS)] + [(f"fill-{i}", t) for i, t in enumerate(_FILLER)]
    with eng.begin() as c:
        c.execute(text(_SCHEMA))
        for cid, body in rows:
            c.execute(text(
                "INSERT INTO immigration_corpus_chunks "
                "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, trust_tier, "
                " fetched_at, embedding, content_hash, is_active) VALUES "
                "(:id,:cor,:u,:t,:i,:m,:tt,:f,:e,:h,1)"),
                {"id": cid, "cor": "FR_NO", "u": f"https://gov.example/{cid}", "t": body,
                 "i": 0, "m": json.dumps({"corridor": "FR_NO"}), "tt": 1,
                 "f": "2026-06-06T00:00:00+00:00", "e": json.dumps(emb.embed(body)), "h": cid})
    return eng


_PROFILE = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
_PATH = PathClassification(pathway_type="eu_free_movement")


def _set_flag(case, value):
    prev = os.environ.get("IMMIGRATION_HYBRID_RETRIEVAL")
    if value is None:
        os.environ.pop("IMMIGRATION_HYBRID_RETRIEVAL", None)
    else:
        os.environ["IMMIGRATION_HYBRID_RETRIEVAL"] = value

    def restore():
        if prev is None:
            os.environ.pop("IMMIGRATION_HYBRID_RETRIEVAL", None)
        else:
            os.environ["IMMIGRATION_HYBRID_RETRIEVAL"] = prev
    case.addCleanup(restore)


# --------------------------------------------------------------------------- #
# Pure-function units                                                         #
# --------------------------------------------------------------------------- #
class Bm25Tests(unittest.TestCase):
    def test_keyword_overlap_ranks_above_no_overlap(self):
        docs = [_KW_HIT, _KW_MISS, "fr national immigration"]
        scores = _bm25_scores("immigration requirements fr national", docs)
        self.assertGreater(scores[0], scores[2])   # most overlap wins
        self.assertEqual(scores[1], 0.0)            # zero overlap → 0

    def test_empty_query_or_docs(self):
        self.assertEqual(_bm25_scores("", ["a b c"]), [0.0])
        self.assertEqual(_bm25_scores("a", []), [])


class RrfTests(unittest.TestCase):
    def test_doc_in_both_legs_outranks_single_leg_docs(self):
        vec = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        kw = [{"id": "c"}, {"id": "d"}]
        fused = _rrf_fuse(vec, kw, c=60)
        ids = [f["id"] for f in fused]
        self.assertEqual(set(ids), {"a", "b", "c", "d"})   # union
        self.assertEqual(ids[0], "c")                       # appears in both → top
        for f in fused:
            self.assertIn("rrf_score", f)

    def test_rank_position_drives_score(self):
        fused = _rrf_fuse([{"id": "x"}, {"id": "y"}], [], c=60)
        sx = next(f["rrf_score"] for f in fused if f["id"] == "x")
        sy = next(f["rrf_score"] for f in fused if f["id"] == "y")
        self.assertGreater(sx, sy)


# --------------------------------------------------------------------------- #
# Keyword leg (sqlite)                                                        #
# --------------------------------------------------------------------------- #
class KeywordLegTests(unittest.TestCase):
    def setUp(self):
        self.engine = _seed_engine()
        self.q_emb = HashEmbedder().embed(_KW_HIT)

    def test_bm25_ordered_zero_overlap_excluded_and_carries_cosine(self):
        out = KeywordRetriever().candidates(
            engine=self.engine, corridor_db="FR_NO", q_emb=self.q_emb,
            query="immigration requirements eea fr national relocating", fetch_k=10,
        )
        ids = [c["id"] for c in out]
        self.assertEqual(ids[0], "kw-hit")        # strongest keyword match first
        self.assertNotIn("kw-miss", ids)          # zero-overlap excluded
        for c in out:
            self.assertIn("score", c)             # cosine present for the floor
            self.assertIsInstance(c["score"], float)


# --------------------------------------------------------------------------- #
# Flag wiring + end-to-end                                                    #
# --------------------------------------------------------------------------- #
class FlagWiringTests(unittest.TestCase):
    def setUp(self):
        self.engine = _seed_engine()

    def _retrieve(self, **kw):
        params = dict(min_similarity_score=0.0, top_k=10)
        params.update(kw)
        return ir.retrieve_for_profile(
            profile=_PROFILE, classification=_PATH, engine=self.engine, **params,
        )

    def test_flag_off_uses_vector_path_not_hybrid(self):
        _set_flag(self, None)  # default off
        with mock.patch.object(ir, "HybridRetriever", side_effect=AssertionError("hybrid must not run")):
            res = self._retrieve()
        self.assertTrue(res)
        for c in res:                              # corridor-scoped, no rrf base
            self.assertEqual(c["corridor"], "FR_NO")
            self.assertNotIn("rrf_score", c)

    def test_flag_off_byte_identical_to_vector_baseline(self):
        _set_flag(self, None)
        got = self._retrieve()
        # Reproduce the pure vector path independently.
        q_emb = HashEmbedder().embed(ir._build_query(_PROFILE, _PATH, "FR→NO"))
        raw = VectorRetriever().candidates(
            engine=self.engine, corridor_db="FR_NO", q_emb=q_emb, query="", fetch_k=30,
        )
        raw = [c for c in raw if c.get("corridor") == "FR_NO"]
        baseline = ir._apply_quality_gates(raw, min_similarity=0.0, top_k=10)
        self.assertEqual([c["id"] for c in got], [c["id"] for c in baseline])

    def test_flag_on_uses_hybrid_and_stays_corridor_scoped(self):
        _set_flag(self, "on")
        res = self._retrieve()
        self.assertTrue(res)
        self.assertTrue(any("rrf_score" in c for c in res))   # fused base present
        for c in res:
            self.assertEqual(c["corridor"], "FR_NO")
        self.assertIn("kw-hit", {c["id"] for c in res})       # keyword recall

    def test_flag_on_floor_still_drops_subfloor_chunks(self):
        # An impossibly high floor must still empty the result under hybrid —
        # proving the cosine similarity gate survives RRF fusion.
        _set_flag(self, "on")
        res = self._retrieve(min_similarity_score=2.0)
        self.assertEqual(res, [])


# --------------------------------------------------------------------------- #
# Deterministic eval-style delta (precision@k, no live corpus)                #
# --------------------------------------------------------------------------- #
def _chunk(cid, score=0.5):
    return {"id": cid, "corridor": "FR_NO", "trust_tier": 1, "score": score,
            "fetched_at": "2026-06-06T00:00:00+00:00", "reliability_score": None}


class _StubLeg:
    """A RetrieverProtocol leg returning a fixed ordered candidate list."""

    def __init__(self, ids):
        self._chunks = [_chunk(i) for i in ids]

    def candidates(self, **_kw):
        return [dict(c) for c in self._chunks]


class EvalDeltaTests(unittest.TestCase):
    """Deterministic precision@k delta using the real harness metric. The
    on-topic answer is *vector-buried* (rank 5) but *keyword-surfaced* (rank 0);
    RRF must promote it to the top, so hybrid precision@1 beats vector — the
    keyword-recall win hybrid exists to deliver. No live corpus / no embedder
    noise (stub legs isolate the fusion behaviour)."""

    def setUp(self):
        from backend.scripts.rag_eval_harness import precision_at_k
        self._p_at_k = precision_at_k

    def test_rrf_promotes_vector_buried_keyword_match(self):
        # Vector ranks the answer last; keyword ranks it first.
        vec_leg = _StubLeg(["f0", "f1", "f2", "f3", "f4", "target"])
        kw_leg = _StubLeg(["target"])

        vector_only = ir._apply_quality_gates(
            vec_leg.candidates(), min_similarity=0.0, top_k=5, rank_base=None)
        fused = HybridRetriever(vector=vec_leg, keyword=kw_leg).candidates(
            engine=mock.Mock(), corridor_db="FR_NO", q_emb=[0.0], query="q", fetch_k=10)
        hybrid = ir._apply_quality_gates(
            fused, min_similarity=0.0, top_k=5, rank_base="rrf_score")

        p_vec = self._p_at_k([c["id"] for c in vector_only], ["target"], k=1)
        p_hyb = self._p_at_k([c["id"] for c in hybrid], ["target"], k=1)
        self.assertEqual(p_vec, 0.0)              # vector buries the answer
        self.assertEqual(p_hyb, 1.0)              # hybrid surfaces it
        self.assertGreater(p_hyb, p_vec)


if __name__ == "__main__":
    unittest.main()

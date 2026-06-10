"""
W3-4 — deterministic RAG context-precision gate.

Runs the real eval harness over the golden query set against the committed
synthetic chunk fixture (deterministic: HashEmbedder + fixed corpus). Asserts a
stable precision floor (catches retrieval-pipeline regressions) and that the
hybrid retriever (W3-2) is not worse than vector — the deterministic signal the
live-corpus eval can't give in CI.

This IS the W3-4 hard gate. It needs no DB / no secrets, so it lives in the
curated CI suite.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.scripts.rag_eval_fixture import (  # noqa: E402
    QUERIES_PATH,
    build_seeded_engine,
    load_chunks,
    patched_retriever_db,
)
from backend.scripts.rag_eval_harness import aggregate_report, load_queries  # noqa: E402
from backend.scripts.eval_rag_context_precision import (  # noqa: E402
    ImmigrationRetrieverAdapter,
    evaluate,
)

# Measured vector aggregate p@5 on this fixture is 0.2400; the floor sits below it
# so the gate trips on a real regression (corridor filter / quality gates / ranking
# breaking → precision collapses) without flaking on minor ranking shifts.
_PRECISION_FLOOR = 0.20
_K = 5


def _aggregate(engine, queries, hybrid: bool) -> dict:
    prev = os.environ.get("IMMIGRATION_HYBRID_RETRIEVAL")
    if hybrid:
        os.environ["IMMIGRATION_HYBRID_RETRIEVAL"] = "on"
    else:
        os.environ.pop("IMMIGRATION_HYBRID_RETRIEVAL", None)
    try:
        with patched_retriever_db(engine):
            results = evaluate(queries, ImmigrationRetrieverAdapter(default_top_k=_K), k=_K)
        return aggregate_report(results, metric_name="precision_at_k", threshold=0.0)
    finally:
        if prev is None:
            os.environ.pop("IMMIGRATION_HYBRID_RETRIEVAL", None)
        else:
            os.environ["IMMIGRATION_HYBRID_RETRIEVAL"] = prev


class RagEvalFixtureGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = build_seeded_engine()
        cls.queries = load_queries(str(QUERIES_PATH))

    def test_fixture_covers_every_expected_chunk_id(self):
        # No golden query may reference an id absent from the fixture, else it
        # scores a silent 0.0 (the exact noise W3-4 removes).
        have = {c["chunk_id"] for c in load_chunks()}
        expected = {cid for q in self.queries for cid in q.expected_chunk_ids}
        missing = expected - have
        self.assertEqual(missing, set(), f"fixture missing chunks: {sorted(missing)}")

    def test_all_queries_scored(self):
        rep = _aggregate(self.engine, self.queries, hybrid=False)
        self.assertEqual(rep["queries_evaluated"], 50)

    def test_vector_precision_above_floor(self):
        rep = _aggregate(self.engine, self.queries, hybrid=False)
        self.assertGreater(rep["aggregate"], 0.0)                 # not 0.0 noise
        self.assertGreaterEqual(
            rep["aggregate"], _PRECISION_FLOOR,
            f"context precision@{_K} {rep['aggregate']:.4f} < floor {_PRECISION_FLOOR} "
            "— a retrieval-pipeline regression",
        )

    def test_deterministic(self):
        a = _aggregate(self.engine, self.queries, hybrid=False)["aggregate"]
        b = _aggregate(self.engine, self.queries, hybrid=False)["aggregate"]
        self.assertEqual(a, b)

    def test_hybrid_not_worse_than_vector(self):
        vec = _aggregate(self.engine, self.queries, hybrid=False)["aggregate"]
        hyb = _aggregate(self.engine, self.queries, hybrid=True)["aggregate"]
        self.assertGreaterEqual(
            hyb, vec - 1e-9,
            f"hybrid p@{_K} {hyb:.4f} regressed below vector {vec:.4f}",
        )


if __name__ == "__main__":
    unittest.main()

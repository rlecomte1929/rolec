"""
Deepen-evals slice 4 — source-reliability A/B harness.

Produces the EVIDENCE needed before flipping IMMIGRATION_RELIABILITY_WEIGHT in
prod: it runs immigration_retriever._apply_quality_gates over the same chunks at
weight 0 (dormant) vs weight>0 and reports the precision@k delta. The fixture is
engineered so the most-reliable chunk is the correct one but has slightly lower
similarity — so reliability re-ranking should promote it.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.run_reliability_ab import compare, precision_at_k

_NOW = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _chunk(cid, score, reliability):
    return {"id": cid, "score": score, "reliability_score": reliability,
            "trust_tier": 1, "fetched_at": "2026-06-01T00:00:00+00:00"}


def test_precision_at_k_helper():
    assert precision_at_k(["a", "b", "c"], {"a", "c"}, 2) == 0.5  # a relevant, b not
    assert precision_at_k(["a"], {"a"}, 1) == 1.0


def test_reliability_weight_promotes_the_reliable_correct_chunk():
    chunks = [
        _chunk("a", 0.80, 0.95),  # correct answer, very reliable, slightly lower similarity
        _chunk("b", 0.85, 0.30),  # higher similarity but unreliable (e.g. down-ranked by feedback)
    ]
    result = compare(chunks, relevant_ids={"a"}, k=1, weight_on=1.0, now=_NOW)

    # weight 0 (dormant): similarity wins → b first → precision@1 = 0
    assert result["off"]["ranked_ids"][0] == "b"
    assert result["off"]["precision_at_k"] == 0.0
    # weight 1: reliability promotes a → a first → precision@1 = 1.0
    assert result["on"]["ranked_ids"][0] == "a"
    assert result["on"]["precision_at_k"] == 1.0
    assert result["delta"] == 1.0


def test_weight_state_is_restored_after_compare():
    from backend.app.services import source_reliability_config as cfg
    before = cfg.RELIABILITY_WEIGHT
    compare([_chunk("a", 0.8, 0.9)], relevant_ids={"a"}, k=1, weight_on=1.0, now=_NOW)
    assert cfg.RELIABILITY_WEIGHT == before  # no global-state leak

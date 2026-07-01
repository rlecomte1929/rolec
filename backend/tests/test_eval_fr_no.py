"""
Deepen-evals slice 3 — FR→NO (EEA free-movement) corridor gold, proving the
structuring + roadmap harnesses generalize beyond IN→DE. Structuring runs the REAL
policy_applicability_engine (regression guard); roadmap grades a representative
complete FR→NO roadmap against its gold.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.run_roadmap_outcome_eval import grade_roadmaps
from backend.eval.run_structuring_eval import load_gold
from backend.eval.structuring_metrics import score_structuring

_FIX = Path(__file__).parent / "fixtures" / "eval"


def test_fr_no_structuring_gold_scores_perfectly():
    cases = load_gold(_FIX / "structuring" / "fr_no.jsonl")
    assert len(cases) >= 8
    report = score_structuring(cases)  # real engine
    assert report["accuracy"] == 1.0, report["confusion"]
    for axis in ("assignment_type", "family", "nationality_origin", "destination", "ambiguity"):
        assert report["by_axis"].get(axis) == 1.0, (axis, report["by_axis"])


def test_fr_no_complete_roadmap_passes():
    gold = json.loads((_FIX / "roadmap" / "fr_no.json").read_text())
    produced = [r["steps"] for r in json.loads((_FIX / "roadmap" / "fr_no_produced_sample.json").read_text())]
    report = grade_roadmaps(produced, gold)
    # A clean corridor: both required steps present, in order.
    assert report["completeness"] == 1.0
    assert report["ordering"] == 1.0
    assert report["noise_precision"] == 1.0

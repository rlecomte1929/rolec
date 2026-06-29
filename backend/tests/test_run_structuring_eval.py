"""
Phase 2 — structuring eval over the IN→DE gold set, exercising the REAL
policy_applicability_engine end to end. The gold encodes correct per-profile
structuring across every axis (assignment_type / family / nationality / destination
/ ambiguity), so a perfect score here is the regression guard: if the engine starts
mis-applying requirements for a profile, accuracy drops and the confusion map names
the broken case.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.run_structuring_eval import load_gold
from backend.eval.structuring_metrics import score_structuring

_GOLD = Path(__file__).parent / "fixtures" / "eval" / "structuring" / "in_de.jsonl"


def test_engine_matches_in_de_structuring_gold():
    cases = load_gold(_GOLD)
    assert len(cases) >= 10  # full axis coverage

    report = score_structuring(cases)  # real evaluate_fact_applicability

    # Perfect structuring on the gold — any miss names the broken (expected->actual) pair.
    assert report["accuracy"] == 1.0, report["confusion"]
    assert report["f1"] == 1.0
    # Every axis is represented and fully correct.
    for axis in ("assignment_type", "family", "nationality_origin", "destination", "ambiguity"):
        assert report["by_axis"].get(axis) == 1.0, (axis, report["by_axis"])

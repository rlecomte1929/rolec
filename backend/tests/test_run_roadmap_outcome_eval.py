"""
Phase 2 — roadmap completeness/ordering eval over the IN→DE gold.

Grades a representative (intentionally imperfect) produced roadmap against the gold
and asserts the eval DETECTS the gap: a missing residence-permit step (completeness
< 1) and an irrelevant bank-account step (noise). This is the fail-to-detect proof
— if the metrics ever reported a perfect score for this known-imperfect roadmap,
the eval would be worthless.
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

_FIX = Path(__file__).parent / "fixtures" / "eval" / "roadmap"


def test_in_de_sample_roadmap_is_graded_and_gaps_detected():
    gold = json.loads((_FIX / "in_de.json").read_text())
    produced = [r["steps"] for r in json.loads((_FIX / "in_de_produced_sample.json").read_text())]

    report = grade_roadmaps(produced, gold)

    # 2 of 3 expected steps present; residence permit missing.
    assert report["completeness"] == round(2 / 3, 4)
    assert report["per_roadmap"][0]["missing_steps"] == ["residence_permit"]
    # The bank-account step is flagged as noise.
    assert report["noise_precision"] == round(2 / 3, 4)
    assert report["per_roadmap"][0]["extra_steps"] == ["Open a German bank account"]
    # The one applicable ordering constraint (visa before anmeldung) holds.
    assert report["ordering"] == 1.0
    # Composite is well below a perfect score — the eval is not blind.
    assert report["outcome_accuracy"] < 0.8

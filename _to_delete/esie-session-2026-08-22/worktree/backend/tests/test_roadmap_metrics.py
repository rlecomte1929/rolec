"""
Phase 2 — roadmap completeness/ordering eval metrics (gaps #2 + #4).

Grades a produced AI roadmap against a gold expectation for a profile:
  - completeness (recall): did we include every required step?
  - noise (precision): did we avoid irrelevant steps?
  - ordering: are the gold's dependency constraints satisfied in the sequence?

A produced step matches an expected step when the expected `match` substring
appears (case-insensitive) in the step title. These tests pin the math on a small
hand-verifiable roadmap.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.roadmap_metrics import score_roadmap


def test_completeness_noise_and_ordering():
    produced = [
        {"order": 1, "title": "Apply for the EU Blue Card visa"},
        {"order": 2, "title": "Register your address (Anmeldung)"},
        {"order": 3, "title": "Open a local bank account"},  # not in gold → noise
    ]
    gold = {
        "expected_steps": [
            {"key": "visa", "match": "blue card"},
            {"key": "anmeldung", "match": "register your address"},
            {"key": "residence_permit", "match": "residence permit"},  # missing → hurts recall
        ],
        "order": [["visa", "anmeldung"]],
    }

    report = score_roadmap(produced, gold)

    # 2 of 3 expected steps present.
    assert report["completeness"] == round(2 / 3, 4)
    # 2 of 3 produced steps are relevant (bank account is noise).
    assert report["noise_precision"] == round(2 / 3, 4)
    # visa (pos 0) precedes anmeldung (pos 1) → constraint satisfied.
    assert report["ordering"] == 1.0
    assert report["missing_steps"] == ["residence_permit"]
    assert report["extra_steps"] == ["Open a local bank account"]


def test_ordering_violation_detected():
    produced = [
        {"order": 1, "title": "Register your address (Anmeldung)"},
        {"order": 2, "title": "Apply for the EU Blue Card visa"},
    ]
    gold = {
        "expected_steps": [{"key": "visa", "match": "blue card"},
                           {"key": "anmeldung", "match": "anmeldung"}],
        "order": [["visa", "anmeldung"]],  # visa must precede anmeldung — violated here
    }

    report = score_roadmap(produced, gold)

    assert report["completeness"] == 1.0
    assert report["ordering"] == 0.0  # the one constraint is violated


def test_empty_produced_is_safe():
    gold = {"expected_steps": [{"key": "visa", "match": "blue card"}], "order": []}
    report = score_roadmap([], gold)
    assert report["completeness"] == 0.0
    assert report["noise_precision"] == 0.0
    assert report["ordering"] == 1.0  # no applicable constraints → vacuously satisfied

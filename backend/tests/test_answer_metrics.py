"""
Deepen-evals slice 1 — answer/extraction faithfulness eval.

Grades the immigration Q&A path (feature_key='immigration_answer' replay records)
from the pipeline's own stored verify_grounding verdicts — deterministic, no LLM.
This is the user's original "remove noise, ensure accuracy" target for the answer
surface: are answers grounded, cited, and free of unsupported claims, and does the
system refuse rather than hallucinate?
"""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.answer_metrics import grade_answer_records


def _ans(corridor, answer_kind, grounding=None, cited=None, unsupported=None, confidence="high"):
    out = {
        "answer_kind": answer_kind,
        "grounding_verdict": grounding,
        "cited_sources": cited or [],
        "unsupported_claims": unsupported or [],
        "confidence": confidence,
    }
    return {"feature_key": "immigration_answer", "corridor": corridor,
            "output_masked": json.dumps(out)}


def test_grounding_citation_and_refusal_rates():
    records = [
        _ans("FR_NO", "answer", grounding="grounded", cited=[{"source_url": "u1"}]),
        _ans("FR_NO", "answer", grounding="partially_grounded",
             cited=[{"source_url": "u2"}], unsupported=["x"]),
        _ans("FR_NO", "answer", grounding="grounded", cited=[]),          # grounded but uncited
        _ans("FR_NO", "refusal_insufficient_context"),
        _ans("FR_NO", "refusal_ungrounded"),                              # hallucination caught
        # a non-answer feature record must be ignored entirely
        {"feature_key": "rag_roadmap", "corridor": "FR_NO", "output_masked": "{}"},
    ]

    report = grade_answer_records(records)

    assert report["extra"]["n_answered"] == 3
    assert report["aggregate"] == round(2 / 3, 4)           # grounding_rate: 2 grounded of 3 answered
    assert report["extra"]["citation_validity"] == round(2 / 3, 4)
    assert report["extra"]["unsupported_claim_rate"] == round(1 / 3, 4)
    assert report["extra"]["refusal_rate"] == round(2 / 5, 4)
    assert report["extra"]["ungrounded_caught"] == 1
    assert report["by_corridor"]["FR_NO"] == round(2 / 3, 4)


def test_empty_is_safe():
    report = grade_answer_records([])
    assert report["aggregate"] == 0.0
    assert report["extra"]["n_answered"] == 0

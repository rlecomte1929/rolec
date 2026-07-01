"""Deepen-evals slice 1 — answer grader runner emits a dashboard report."""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.rag_eval_reports import load_live_reports
from backend.eval import run_answer_grade


def test_runner_emits_answer_grounding_dashboard_report(tmp_path):
    recs = [
        {"feature_key": "immigration_answer", "corridor": "FR_NO",
         "output_masked": json.dumps({"answer_kind": "answer", "grounding_verdict": "grounded",
                                       "cited_sources": [{"source_url": "u"}], "unsupported_claims": []})},
        {"feature_key": "immigration_answer", "corridor": "FR_NO",
         "output_masked": json.dumps({"answer_kind": "refusal_insufficient_context"})},
    ]
    recs_file = tmp_path / "recs.json"
    recs_file.write_text(json.dumps(recs))

    rc = run_answer_grade.main(["--records", str(recs_file), "--out", str(tmp_path)])
    assert rc == 0
    assert list(tmp_path.glob("answer_grounding_*.json"))
    series = load_live_reports(tmp_path)
    assert series.get("answer_grounding")
    assert series["answer_grounding"][-1]["aggregate"] == 1.0  # 1 grounded of 1 answered

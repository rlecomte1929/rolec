"""Deepen-evals slice 2 — calibration runner emits a dashboard report."""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.rag_eval_reports import load_live_reports
from backend.eval import run_calibration_eval


def _ans(confidence, grounded):
    out = {"answer_kind": "answer", "confidence": confidence,
           "grounding_verdict": "grounded" if grounded else "partially_grounded"}
    return {"feature_key": "immigration_answer", "output_masked": json.dumps(out)}


def test_runner_emits_calibration_dashboard_report(tmp_path):
    recs = [_ans("high", True)] * 5 + [_ans("low", True)] * 2 + [_ans("low", False)] * 3
    recs_file = tmp_path / "recs.json"
    recs_file.write_text(json.dumps(recs))

    rc = run_calibration_eval.main(["--records", str(recs_file), "--out", str(tmp_path)])
    assert rc == 0
    assert list(tmp_path.glob("calibration_score_*.json"))
    series = load_live_reports(tmp_path)
    assert series["calibration_score"][-1]["aggregate"] == 0.95

"""Unit tests for environmental-failure reclassification in ingest_playwright_results.

A Playwright test that failed because the backend was mid rolling-restart carries an
`environmental` annotation (pushed by assertLogicalPage / markEnvironmentalIfDown). The
ingest must reclassify such a FAIL to a non-scoring `ENV` status so the scorer never
files a P0 for a deploy-window transient — while a genuine FAIL (no annotation) stays FAIL.
Pure stdlib + tmp files — no browser, no network.
"""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ingest_playwright_results as ing  # noqa: E402


def _spec(title, status, annotations=None):
    return {
        "title": title,
        "tests": [{"annotations": annotations or [], "results": [{"status": status}]}],
    }


def _pw(tmp_path, specs):
    p = tmp_path / "_results.json"
    p.write_text(json.dumps({"suites": [{"specs": specs}]}))
    return p


def test_environmental_fail_becomes_env(tmp_path):
    pw = _pw(tmp_path, [
        _spec("[CORE-HR-dashboard] renders", "failed",
              [{"type": "environmental", "description": "backend down"}]),
        _spec("[CORE-RLS] scoped", "failed"),          # genuine fail, no annotation
        _spec("[CORE-EMP-dashboard] ok", "passed"),
    ])
    rows = {r["id"]: r for r in ing.parse_playwright(pw)[0]}
    assert rows["CORE-HR-dashboard"]["status"] == "ENV", "env-annotated FAIL must become ENV"
    assert rows["CORE-RLS"]["status"] == "FAIL", "un-annotated FAIL must stay FAIL"
    assert rows["CORE-EMP-dashboard"]["status"] == "PASS"


def test_env_excluded_from_fail_count_and_score(tmp_path):
    pw = _pw(tmp_path, [
        _spec("[A] a", "passed"),
        _spec("[B] b", "failed", [{"type": "environmental"}]),  # ENV
        _spec("[C] c", "passed"),
    ])
    rows = ing.parse_playwright(pw)[0]
    summ = ing.summarize(rows)
    assert summ["fail"] == 0, "ENV must not count as a failure"
    assert summ.get("env") == 1, "ENV counted in its own bucket"
    # score_pct denominator excludes ENV (like SKIP): 2 pass / 2 scorable = 100
    scorable = summ["total"] - summ["skip"] - summ.get("env", 0)
    assert scorable == 2


def test_non_environmental_annotation_does_not_reclassify(tmp_path):
    # an unrelated annotation type must NOT turn a FAIL into ENV
    pw = _pw(tmp_path, [
        _spec("[D] d", "failed", [{"type": "slow", "description": "took a while"}]),
    ])
    rows = {r["id"]: r for r in ing.parse_playwright(pw)[0]}
    assert rows["D"]["status"] == "FAIL"

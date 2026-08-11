"""Acceptance/integration test: replay the deploy-window false-positive class end to end
through the REAL pipeline functions (ingest -> score -> candidates -> confirm-twice) and
prove (a) an environmental failure files NOTHING, (b) a genuine persistent failure STILL
files. This is the regression gate for AIQ-1375/1386/1394/1395.
"""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ingest_playwright_results as ing  # noqa: E402
import campaign_scorer as cs  # noqa: E402
import notion_sync_candidates as nsc  # noqa: E402

_MAP = json.loads((SCRIPTS_DIR / "scoring_map.json").read_text())


def _notion_worthy_ids():
    return [tid for tid, m in _MAP["tests"].items()
            if m.get("notion_worthy") and m["priority"] in ("P0", "P1")]


def _spec(title, status, annotations=None):
    return {"title": title, "tests": [{"annotations": annotations or [], "results": [{"status": status}]}]}


def _pipeline(tmp_path, specs, prev_ids=None, have_prev=False):
    """Run PW json -> ingest -> score -> candidates -> confirm-twice; return the ids filed."""
    pw = tmp_path / "_results.json"
    pw.write_text(json.dumps({"suites": [{"specs": specs}]}))
    rows = ing.parse_playwright(pw)[0]
    _dom, _overall, per_test = cs.score_results(rows, _MAP)
    regressions, _fixed, new_failures, still_broken = cs.diff_tests(per_test, {})
    candidates = cs.notion_candidates(per_test, regressions, new_failures, still_broken)
    degraded = cs.is_degraded(cs.count_env(per_test))
    candidates = cs.finalize_candidates(candidates, degraded)
    if prev_ids is not None or have_prev:
        candidates, _held = nsc.filter_confirmed(candidates, set(prev_ids or []), have_prev)
    return {c["test_id"] for c in candidates}, degraded


def test_environmental_failure_files_nothing(tmp_path):
    ids = _notion_worthy_ids()
    env_id, real_id = ids[0], ids[1]
    filed, degraded = _pipeline(tmp_path, [
        _spec(f"[{env_id}] deploy-window", "failed", [{"type": "environmental"}]),
        _spec(f"[{real_id}] genuine", "failed"),
    ])
    assert env_id not in filed, "an environmental (deploy-window) failure must NOT file"
    assert real_id in filed, "a genuine failure must still file (no masking)"
    assert degraded is False, "one ENV is below the degraded threshold"


def test_backend_wide_outage_is_inconclusive(tmp_path):
    # AIQ-1395 shape: multiple surfaces error environmentally in one run → INCONCLUSIVE, file nothing
    ids = _notion_worthy_ids()[:3]
    filed, degraded = _pipeline(
        tmp_path,
        [_spec(f"[{i}] down", "failed", [{"type": "environmental"}]) for i in ids],
    )
    assert degraded is True
    assert filed == set(), "a degraded (backend-wide) run files nothing"


def test_persistent_real_bug_files_under_confirm_twice(tmp_path):
    ids = _notion_worthy_ids()
    real_id = ids[0]
    # seen this run AND last run (prev_ids) → confirm-twice files it
    filed, _ = _pipeline(
        tmp_path,
        [_spec(f"[{real_id}] genuine", "failed")],
        prev_ids=[real_id], have_prev=True,
    )
    assert real_id in filed, "a bug failing two consecutive runs must file"


def test_first_seen_failure_is_held_under_confirm_twice(tmp_path):
    ids = _notion_worthy_ids()
    real_id = ids[0]
    # failed this run but NOT last run → held (transient-or-not, wait one cycle)
    filed, _ = _pipeline(
        tmp_path,
        [_spec(f"[{real_id}] genuine", "failed")],
        prev_ids=[], have_prev=True,
    )
    assert real_id not in filed, "a first-seen failure is held for confirm-twice"

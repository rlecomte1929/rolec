"""
H4 · Regression tests for scripts/campaign_scorer.py shape tolerance.

Background — the C8 campaign (2026-06-29) crashed the scorer with
``'str' object has no attribute 'get'``. The runner output had drifted: newer
``test_results_*.json`` files store ``results`` as a *list* of dicts, while some
older baselines store ``results`` as a *dict* keyed by test_id (with the list under
``results_list``). main() iterated ``data.get("results", [])`` directly, so a
dict-shaped baseline yielded its *keys* (strings) and ``status_of`` blew up calling
``.get`` on a string — forcing a manual ``--prev`` override to score at all.

The shape-normalisation fix landed in PR #1189 (``extract_results`` + a hardened
``status_of``) but shipped **without a regression test**. This module is that
missing guard: it pins the dict-shaped-prev path so the crash cannot silently
return.

The scorer is a standalone script under scripts/ (no package), so we add that dir
to sys.path and import it by module name. No DB, no app, no network.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import campaign_scorer as cs  # noqa: E402


# ── extract_results: shape tolerance ────────────────────────────────────────────

def test_extract_results_list_shaped_passthrough():
    """Newer runner output (results = list of dicts) is returned as-is."""
    data = {"results": [{"id": "CORE-RLS", "status": "PASS"}]}
    assert cs.extract_results(data) == [{"id": "CORE-RLS", "status": "PASS"}]


def test_extract_results_dict_shaped_is_normalised_to_list():
    """Legacy results-as-dict (keyed by test_id) → list of dicts carrying the id.

    This is the exact shape that crashed the C8 run.
    """
    data = {"results": {"CORE-RLS": {"status": "PASS"}, "PER-H1": {"status": "FAIL"}}}
    out = cs.extract_results(data)
    assert isinstance(out, list)
    by_id = {r["id"]: r["status"] for r in out}
    assert by_id == {"CORE-RLS": "PASS", "PER-H1": "FAIL"}


def test_extract_results_prefers_results_list_when_results_is_dict():
    """When both a dict ``results`` and a list ``results_list`` exist, the list wins."""
    data = {
        "results": {"CORE-RLS": {"status": "PASS"}},
        "results_list": [{"id": "PER-H1", "status": "WARN"}],
    }
    assert cs.extract_results(data) == [{"id": "PER-H1", "status": "WARN"}]


def test_extract_results_missing_key_returns_empty_list():
    """A file with no recognisable results shape degrades to [] (no crash)."""
    assert cs.extract_results({"summary": {"total": 0}}) == []


def test_status_of_skips_non_dict_rows():
    """Hardened status_of must not choke on stray non-dict rows."""
    rows = ["CORE-RLS", {"id": "PER-H1", "status": "FAIL"}]
    assert cs.status_of("PER-H1", rows) == "FAIL"
    assert cs.status_of("missing", rows) == "SKIP"


# ── End-to-end: the C8 crash scenario (dict-shaped prev) must score, not crash ──

@pytest.fixture(scope="module")
def score_map():
    return cs.load_json(str(cs.MAP_FILE))


def test_dict_shaped_prev_scores_instead_of_crashing(score_map):
    """The regression: a dict-shaped PREVIOUS baseline diffed against a list-shaped
    CURRENT run must produce a numeric overall score and a clean diff — not raise.

    Pre-fix this raised AttributeError('str' object has no attribute 'get').
    """
    test_ids = list(score_map["tests"].keys())[:5]

    # CURRENT — list shape (newer runner): everything PASS.
    current = cs.extract_results(
        {"results": [{"id": tid, "status": "PASS"} for tid in test_ids]}
    )
    # PREVIOUS — dict shape (legacy baseline): one was failing.
    prev_raw = {tid: {"status": "PASS"} for tid in test_ids}
    prev_raw[test_ids[0]] = {"status": "FAIL"}
    prev = cs.extract_results({"results": prev_raw})

    cur_domains, cur_overall, cur_per_test = cs.score_results(current, score_map)
    prev_domains, prev_overall, prev_per_test = cs.score_results(prev, score_map)

    # Scored, not crashed.
    assert cur_overall is not None
    assert prev_overall is not None
    assert cur_overall >= prev_overall  # current fixed the one prior failure

    regressions, fixed, new_failures, still_broken = cs.diff_tests(
        cur_per_test, prev_per_test
    )
    assert test_ids[0] in fixed
    assert regressions == []


def test_scorer_cli_runs_on_dict_shaped_prev(tmp_path, score_map):
    """Full CLI smoke: invoke campaign_scorer.py with an explicit dict-shaped --prev
    and a list-shaped --current. Must exit 0 and emit a report — the manual override
    that C8 needed now succeeds on the dict shape directly.
    """
    test_ids = list(score_map["tests"].keys())[:5]

    current_file = tmp_path / "test_results_2026-06-29T20-36.json"
    prev_file = tmp_path / "test_results_2026-06-28T07-10.json"
    current_file.write_text(
        json.dumps(
            {
                "summary": {"total": len(test_ids)},
                "results": [{"id": tid, "status": "PASS"} for tid in test_ids],
            }
        )
    )
    prev_file.write_text(
        json.dumps(
            {
                "summary": {"total": len(test_ids)},
                # dict shape — the C8 crash trigger
                "results": {tid: {"status": "PASS"} for tid in test_ids},
            }
        )
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS_DIR / "campaign_scorer.py"),
            "--current", str(current_file),
            "--prev", str(prev_file),
            "--out-dir", str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )

    assert proc.returncode == 0, f"scorer crashed:\nSTDOUT{proc.stdout}\nSTDERR{proc.stderr}"
    assert "has no attribute 'get'" not in proc.stderr
    reports = list(tmp_path.glob("campaign_report_*.json"))
    assert reports, "no campaign report written"
    report = json.loads(reports[0].read_text())
    assert report["overall_score"] is not None
    assert report["health_band"] in {"GREEN", "AMBER", "RED"}

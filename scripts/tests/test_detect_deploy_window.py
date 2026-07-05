"""Tests for scripts/detect_deploy_window.py — the E2E Sentinel deploy-window detector."""
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.detect_deploy_window import detect  # noqa: E402


def _write(tmp_path, rows):
    p = tmp_path / "test_results.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    return str(p)


def _row(status, actual="", detail="", tid="AT1"):
    return {"id": tid, "title": "t", "status": status, "actual": actual, "detail": detail}


def test_gateway_502_is_deploy_window(tmp_path):
    path = _write(tmp_path, [_row("FAIL", actual="502/token=false")])
    assert detect(path) == "AT1"


def test_gateway_503_504(tmp_path):
    assert detect(_write(tmp_path, [_row("FAIL", actual="503/x")])) == "AT1"
    assert detect(_write(tmp_path, [_row("FAIL", actual="504/x")])) == "AT1"


def test_status_zero_network(tmp_path):
    assert detect(_write(tmp_path, [_row("FAIL", actual="0/token=false")])) == "AT1"


def test_network_error_in_detail(tmp_path):
    assert detect(_write(tmp_path, [_row("FAIL", actual="", detail="fetch failed")])) == "AT1"


def test_404_and_500_are_not_infra(tmp_path):
    # 4xx and a plain 500 can be real app bugs → must still file (not a deploy window).
    assert detect(_write(tmp_path, [_row("FAIL", actual="404/token=false")])) is None
    assert detect(_write(tmp_path, [_row("FAIL", actual="500/token=false")])) is None


def test_passing_rows_ignored(tmp_path):
    assert detect(_write(tmp_path, [_row("PASS", actual="502/x"), _row("PASS", actual="0/x")])) is None


def test_missing_or_bad_file(tmp_path):
    assert detect(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert detect(str(bad)) is None


def test_wrapped_results_key(tmp_path):
    p = tmp_path / "test_results.json"
    p.write_text(json.dumps({"results": [_row("FAIL", actual="502/x")]}), encoding="utf-8")
    assert detect(str(p)) == "AT1"

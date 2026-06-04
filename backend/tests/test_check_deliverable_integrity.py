"""Tests for scripts/check_deliverable_integrity.py (HYGIENE-1 / AIQ-786).

Covers the handoff acceptance criteria:
  (1) flags a missing path / exits non-zero; exits 0 when all present or allowlisted
  (2) regression fixtures — one present, one missing (proves it catches phantom deliverables)
  (3) allowlist suppresses a missing path
  (5) unit test for the path parser
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# scripts/ is not a package — load the module by path.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_deliverable_integrity.py"
_spec = importlib.util.spec_from_file_location("check_deliverable_integrity", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(mod)


# --------------------------------------------------------------------------- #
# (5) Path parser unit tests
# --------------------------------------------------------------------------- #


def test_extract_created_and_modified_labels():
    notes = "## Files changed\n- CREATED: `audit/x.md` — purpose\n- MODIFIED: `backend/app/main.py` — wired"
    assert mod.extract_paths(notes) == ["audit/x.md", "backend/app/main.py"]


def test_extract_move_into_destination():
    # per spec we capture the move *destination* path; a bare unbackticked
    # source token in prose is intentionally not captured (avoids false positives)
    notes = "move the annex into `audit/eu_ai_act/`"
    assert mod.extract_paths(notes) == ["audit/eu_ai_act/"]


def test_extract_bare_backtick_paths():
    notes = "Added the guard at `scripts/check_deliverable_integrity.py` and a config."
    assert mod.extract_paths(notes) == ["scripts/check_deliverable_integrity.py"]


def test_parser_ignores_non_paths():
    # shell commands, SQL, urls, and flags must NOT be treated as deliverables
    notes = (
        "Ran `git ls-files` and `SELECT * FROM x`, see https://example.com/page, "
        "passed `--report-only`."
    )
    assert mod.extract_paths(notes) == []


def test_parser_strips_trailing_punctuation_and_dedupes():
    notes = "See `a/b.ts`. Again `a/b.ts`, and `a/b.ts`."
    assert mod.extract_paths(notes) == ["a/b.ts"]


def test_parser_empty_input():
    assert mod.extract_paths("") == []
    assert mod.extract_paths(None) == []


# --------------------------------------------------------------------------- #
# Existence check
# --------------------------------------------------------------------------- #


def test_path_present_file_exact_match():
    tracked = {"backend/main.py", "scripts/x.py"}
    assert mod.path_present("backend/main.py", tracked)
    assert not mod.path_present("backend/missing.py", tracked)


def test_path_present_directory_claim():
    tracked = {"audit/eu_ai_act/annex_iv.md"}
    assert mod.path_present("audit/eu_ai_act/", tracked)
    assert not mod.path_present("audit/empty_dir/", tracked)


# --------------------------------------------------------------------------- #
# (1)(2)(3) find_missing: present vs missing fixtures + allowlist suppression
# --------------------------------------------------------------------------- #

_TRACKED = {"audit/present.md", "backend/main.py"}


def test_find_missing_present_path_is_clean():
    tasks = [{"id": "T1", "title": "ok", "notes": "CREATED: `audit/present.md`"}]
    assert mod.find_missing(tasks, _TRACKED, allowlist=set()) == []


def test_find_missing_flags_phantom_deliverable():
    tasks = [{"id": "T2", "title": "phantom", "notes": "CREATED: `audit/never_merged.md`"}]
    missing = mod.find_missing(tasks, _TRACKED, allowlist=set())
    assert len(missing) == 1
    assert missing[0]["path"] == "audit/never_merged.md"
    assert missing[0]["task"] == "T2"


def test_allowlist_suppresses_missing_path():
    tasks = [{"id": "T2", "title": "phantom", "notes": "CREATED: `audit/never_merged.md`"}]
    missing = mod.find_missing(tasks, _TRACKED, allowlist={"audit/never_merged.md"})
    assert missing == []


# --------------------------------------------------------------------------- #
# (1) main() exit codes via --input (one present, one missing fixture)
# --------------------------------------------------------------------------- #


def _write_input(tmp_path: Path, tasks: list[dict]) -> Path:
    p = tmp_path / "tasks.json"
    p.write_text(json.dumps(tasks))
    return p


def test_main_exits_zero_when_all_present(tmp_path, monkeypatch, capsys):
    # use a path that is actually tracked in this repo so git_tracked_files() finds it
    tasks = [{"id": "T1", "title": "ok", "notes": "CREATED: `CLAUDE.md`"}]
    inp = _write_input(tmp_path, tasks)
    monkeypatch.setattr("sys.argv", ["prog", "--input", str(inp)])
    assert mod.main() == 0
    assert "PASS" in capsys.readouterr().out


def test_main_exits_nonzero_on_missing(tmp_path, monkeypatch, capsys):
    tasks = [
        {"id": "T1", "title": "ok", "notes": "CREATED: `CLAUDE.md`"},
        {"id": "T2", "title": "phantom", "notes": "CREATED: `does/not/exist_xyz.md`"},
    ]
    inp = _write_input(tmp_path, tasks)
    monkeypatch.setattr("sys.argv", ["prog", "--input", str(inp)])
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "does/not/exist_xyz.md" in out


def test_main_report_only_always_zero(tmp_path, monkeypatch, capsys):
    tasks = [{"id": "T2", "title": "phantom", "notes": "CREATED: `does/not/exist_xyz.md`"}]
    inp = _write_input(tmp_path, tasks)
    monkeypatch.setattr("sys.argv", ["prog", "--input", str(inp), "--report-only"])
    assert mod.main() == 0
    assert "WARN" in capsys.readouterr().out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

"""Tests for scripts/check_corridor_cvr.py.

A filled CVR is a markdown file under docs/corridors/<slug>/ whose section 6
Response cell is Yes or No. The live IE→ES template must fail until a session is recorded.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "scripts" / "check_corridor_cvr.py"

_spec = importlib.util.spec_from_file_location("check_corridor_cvr", GUARD)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)

_FILLED = """\
# Case Verification Report — fixture

## 5. Lawyer sign-off

placeholder

## 6. Relief moment

| | |
|---|---|
| Response (Yes/No) | Yes |
| "What surprised you most?" | the cita previa queue |

## 7. Outcome

done
"""

_BLANK = """\
# Case Verification Report — template

## 6. Relief moment

| | |
|---|---|
| Response (Yes/No) | |
| "What surprised you most?" | |
"""


def test_ie_es_template_is_incomplete():
    code, messages = guard.check(REPO, "IE_ES")
    assert code == 1
    assert any("IE_ES" in m or "ie-es" in m for m in messages)


def test_cli_ie_es_exits_nonzero():
    proc = subprocess.run(
        [sys.executable, str(GUARD), "--corridor", "IE_ES", "--root", str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1


def test_fixture_with_section_6_yes_passes(tmp_path: Path):
    docs = tmp_path / "docs" / "corridors" / "ie-es"
    docs.mkdir(parents=True)
    (docs / "session.md").write_text(_FILLED, encoding="utf-8")
    code, messages = guard.check(tmp_path, "IE_ES")
    assert code == 0, messages


def test_blank_template_fails(tmp_path: Path):
    docs = tmp_path / "docs" / "corridors" / "ie-es"
    docs.mkdir(parents=True)
    (docs / "CVR-TEMPLATE.md").write_text(_BLANK, encoding="utf-8")
    code, messages = guard.check(tmp_path, "IE_ES")
    assert code == 1
    assert any("section 6" in m for m in messages)


def test_missing_docs_dir_fails(tmp_path: Path):
    code, messages = guard.check(tmp_path, "IE_ES")
    assert code == 1
    assert any("no corridor docs dir" in m for m in messages)


def test_section_6_no_is_complete():
    text = _FILLED.replace("| Yes |", "| No |")
    assert guard.section_6_response(text) == "No"


def test_missing_corridor_flag_is_exit_2():
    proc = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2

"""Meta-test for scripts/check_corridor_cvr.py.

A corridor must not treat pending requirement_items as approvable without a CVR
whose section 6 (Relief moment) Response is Yes or No. IE→ES today has only
CVR-TEMPLATE.md with that cell blank — the guard must go red on the live tree.

A guard nobody has watched fail is decoration: the fixture with a filled
Response must exit 0, and the empty template must not.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "scripts" / "check_corridor_cvr.py"

_spec = importlib.util.spec_from_file_location("check_corridor_cvr", GUARD)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)

_EMPTY_SECTION_6 = """\
# Case Verification Report — fixture

## 6. Relief moment

| | |
|---|---|
| Response (Yes/No) | |
| "What surprised you most?" | |
"""

_FILLED_YES = """\
# Case Verification Report — fixture

## 6. Relief moment

| | |
|---|---|
| Response (Yes/No) | Yes |
| "What surprised you most?" | the padrón / NIE loop |
"""

_FILLED_NO = """\
# Case Verification Report — fixture

## 6. Relief moment

| | |
|---|---|
| Response (Yes/No) | No |
| "What surprised you most?" | |
"""


def _write_cvr(root: Path, slug: str, body: str, name: str = "CVR.md") -> Path:
    d = root / "docs" / "corridors" / slug
    d.mkdir(parents=True)
    path = d / name
    path.write_text(body, encoding="utf-8")
    return path


def test_live_ie_es_is_incomplete():
    """IE_ES today is the empty template. That is the failing check this card lands."""
    code, messages = guard.check(REPO, "IE_ES")
    assert code == 1, messages
    assert any("IE_ES" in m or "ie-es" in m for m in messages)


def test_cli_ie_es_exits_nonzero():
    result = subprocess.run(
        [sys.executable, str(GUARD), "--corridor", "IE_ES"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_empty_template_fixture_fails(tmp_path):
    _write_cvr(tmp_path, "ie-es", _EMPTY_SECTION_6, name="CVR-TEMPLATE.md")
    code, messages = guard.check(tmp_path, "IE_ES")
    assert code == 1
    assert any("section 6" in m.lower() or "Response" in m for m in messages)


def test_filled_yes_fixture_passes(tmp_path):
    _write_cvr(tmp_path, "ie-es", _FILLED_YES)
    code, messages = guard.check(tmp_path, "IE_ES")
    assert code == 0, messages


def test_filled_no_fixture_passes(tmp_path):
    _write_cvr(tmp_path, "ie-es", _FILLED_NO)
    code, messages = guard.check(tmp_path, "IE_ES")
    assert code == 0, messages


def test_cli_filled_fixture_exits_0(tmp_path):
    _write_cvr(tmp_path, "ie-es", _FILLED_YES)
    result = subprocess.run(
        [sys.executable, str(GUARD), "--corridor", "IE_ES", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_gate_keys_on_corridor_id_not_destination_country(tmp_path):
    """Ireland is the origin of more than one corridor. The flag is the pair id."""
    _write_cvr(tmp_path, "ie-es", _FILLED_YES)
    _write_cvr(tmp_path, "ie-xx", _EMPTY_SECTION_6)
    assert guard.check(tmp_path, "IE_ES")[0] == 0
    assert guard.check(tmp_path, "IE_XX")[0] == 1


def test_missing_docs_dir_is_incomplete(tmp_path):
    code, messages = guard.check(tmp_path, "ZZ_YY")
    assert code == 1
    assert any("ZZ_YY" in m or "zz-yy" in m for m in messages)


def test_missing_corridor_flag_is_exit_2():
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2

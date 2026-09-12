"""Meta-test for scripts/check_corridor_anchor.py.

A guard nobody has watched go red is decoration. Each planted failure asserts exit 1
and names the missing field; the live-repo run asserts the committed tree still passes;
GRANDFATHERED is frozen so expanding it to dodge a new corridor fails this file.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "scripts" / "check_corridor_anchor.py"
sys.path.insert(0, str(REPO / "scripts"))

_spec = importlib.util.spec_from_file_location("check_corridor_anchor", GUARD)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)

FROZEN_GRANDFATHERED = frozenset({
    "DE_NO",
    "ES_IE",
    "ES_NL",
    "FR_CH",
    "FR_DE",
    "FR_ES",
    "FR_NL",
    "FR_NO",
    "FR_SG",
    "IE_ES",
    "IN_DE",
    "NO_FR",
    "US_EC",
})

_MINIMAL = """\
corridor:
  id: "{cid}"
  origin_iso: "XX"
  destination_iso: "YY"
  display_name: "XX → YY"
{anchor}
"""


def _write_profile(root: Path, cid: str, anchor: str = "") -> Path:
    d = root / "corridors" / cid
    d.mkdir(parents=True)
    body = _MINIMAL.format(cid=cid, anchor=anchor)
    (d / "corridor.yaml").write_text(body, encoding="utf-8")
    return d / "corridor.yaml"


def test_grandfathered_without_anchor_passes(tmp_path):
    _write_profile(tmp_path, "FR_NO")
    code, messages = guard.check(tmp_path)
    assert code == 0, messages
    assert messages == []


def test_new_corridor_without_anchor_fails(tmp_path):
    _write_profile(tmp_path, "ZZ_YY")
    code, messages = guard.check(tmp_path)
    assert code == 1
    assert any("ZZ_YY" in m and "case_id" in m for m in messages)
    assert any("Do not add 'ZZ_YY' to GRANDFATHERED" in m for m in messages)


def test_new_corridor_with_note_only_fails(tmp_path):
    _write_profile(tmp_path, "ZZ_YY", anchor="  anchor:\n    note: invented pair\n")
    code, messages = guard.check(tmp_path)
    assert code == 1
    assert any("case_ref" in m for m in messages)


def test_new_corridor_with_case_ref_passes(tmp_path):
    _write_profile(tmp_path, "ZZ_YY", anchor="  anchor:\n    case_ref: Andrea ES→IE 2026\n")
    code, messages = guard.check(tmp_path)
    assert code == 0, messages


def test_new_corridor_with_case_id_passes(tmp_path):
    _write_profile(
        tmp_path,
        "ZZ_YY",
        anchor="  anchor:\n    case_id: 6ecadafe-0fdb-43c5-b8dc-0284e323cf51\n",
    )
    code, messages = guard.check(tmp_path)
    assert code == 0, messages


def test_unreadable_yaml_is_exit_2(tmp_path):
    d = tmp_path / "corridors" / "ZZ_YY"
    d.mkdir(parents=True)
    (d / "corridor.yaml").write_text("corridor: [this: is: not valid\n", encoding="utf-8")
    code, messages = guard.check(tmp_path)
    assert code == 2
    assert any("unreadable YAML" in m for m in messages)


def test_empty_root_is_exit_2(tmp_path):
    code, messages = guard.check(tmp_path)
    assert code == 2
    assert any("no corridors" in m for m in messages)


def test_grandfathered_set_is_frozen():
    assert guard.GRANDFATHERED == FROZEN_GRANDFATHERED


def test_live_repo_passes():
    code, messages = guard.check(REPO)
    assert code == 0, messages
    on_disk = {p.name for p in guard.iter_corridor_yaml(REPO)}
    extra = on_disk - guard.GRANDFATHERED
    for cid in extra:
        path = REPO / "corridors" / cid / "corridor.yaml"
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert guard.has_usable_anchor(doc), f"{cid} is not grandfathered and has no anchor"

"""Tests for the seed/prod parity guard.

DB-free: every test exercises the pure manifest-vs-actual comparison, plus manifest
well-formedness. No DB, no network — the fetch path is the only DB-touching code and is
kept a thin, separately-obvious wrapper.

Imports the module via the sibling-scripts sys.path insertion (NOT `import
scripts.check_seed_prod_parity`): under CI's full-suite pytest discovery `scripts` is not
an importable package, so the dotted spelling raises ModuleNotFoundError.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_seed_prod_parity as guard  # noqa: E402

MANIFEST_PATH = SCRIPTS_DIR / "seed_prod_parity_manifest.json"


# ─── manifest: shape + the FR/ES/DE contract ────────────────────────────────


def test_manifest_loads_and_covers_fr_es_no_de():
    m = guard.load_manifest(MANIFEST_PATH)
    assert set(m) == {
        "FR_cerfa_14571_v2024",
        "ES_ex17_v2024",
        "NO_udi_gp7028_v2024",
        "DE_blue_card_v2024",
    }


def test_manifest_expected_counts_are_locked():
    """Pins the verified prod baseline so an accidental manifest edit is caught."""
    m = guard.load_manifest(MANIFEST_PATH)
    fr = m["FR_cerfa_14571_v2024"]
    assert len(fr["text"]) == 9 and len(fr["checkbox_option"]) == 9
    assert "applicantSurname" in fr["text"] and "applicantGenderM" in fr["checkbox_option"]
    es = m["ES_ex17_v2024"]
    assert len(es["text"]) == 8 and len(es["single_radio"]) == 2
    assert "Año_Nacimiento" in es["text"] and "Sexo" in es["single_radio"]
    no = m["NO_udi_gp7028_v2024"]
    assert len(no["text"]) == 11 and len(no["single_radio"]) == 2
    assert "Family name" in no["text"] and "Marital status group 1" in no["single_radio"]
    assert len(m["DE_blue_card_v2024"]["text"]) == 15


def test_manifest_has_no_stale_fictional_fr_ids():
    """The exact bug this guard exists to catch must not be baked into the manifest:
    the fictional imm11 FR ids must NOT appear as expected."""
    m = guard.load_manifest(MANIFEST_PATH)
    fr_text = m["FR_cerfa_14571_v2024"]["text"]
    for fictional in ("nom", "prenoms", "date_naissance", "numero_passeport", "profession"):
        assert fictional not in fr_text, f"fictional imm11 id {fictional!r} leaked into the manifest"


@pytest.mark.parametrize(
    "bad",
    [
        {},                                                   # no form_field_mappings
        {"form_field_mappings": {}},                          # empty
        {"form_field_mappings": {"F": {"text": "x"}}},        # ids not a list
        {"form_field_mappings": {"F": {"text": ["a", "a"]}}}, # duplicate ids
        {"form_field_mappings": {"F": {}}},                   # form has no kinds
    ],
)
def test_load_manifest_rejects_malformed(tmp_path, bad):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        guard.load_manifest(p)


# ─── diff_form: both directions ─────────────────────────────────────────────


def test_diff_form_in_parity_is_empty():
    exp = {"text": {"a", "b"}, "single_radio": {"r"}}
    assert guard.diff_form("F", exp, {"text": {"a", "b"}, "single_radio": {"r"}}) == []


def test_diff_form_flags_missing():
    exp = {"text": {"a", "b"}}
    problems = guard.diff_form("F", exp, {"text": {"a"}})
    assert len(problems) == 1 and "MISSING" in problems[0] and "b" in problems[0]


def test_diff_form_flags_stale():
    exp = {"text": {"a"}}
    problems = guard.diff_form("F", exp, {"text": {"a", "zzz"}})
    assert len(problems) == 1 and "STALE" in problems[0] and "zzz" in problems[0]


def test_diff_form_missing_kind_is_all_missing():
    exp = {"single_radio": {"Sexo"}}
    problems = guard.diff_form("F", exp, {})  # prod has none of this kind
    assert problems and "MISSING" in problems[0] and "Sexo" in problems[0]


def test_diff_form_ignores_unmanaged_kinds():
    """A kind the manifest does not name for this form is not policed."""
    exp = {"text": {"a"}}
    assert guard.diff_form("F", exp, {"text": {"a"}, "date_part": {"whatever"}}) == []


# ─── check: aggregate + exit codes ──────────────────────────────────────────


def test_check_passes_when_actual_matches_manifest():
    m = guard.load_manifest(MANIFEST_PATH)
    code, report = guard.check(m, m)  # actual == expected
    assert code == 0 and "OK" in report


def test_check_fails_on_drift():
    m = guard.load_manifest(MANIFEST_PATH)
    actual = json_like(m)
    actual["ES_ex17_v2024"]["text"].discard("PASAPORTE")  # a seed row went missing
    code, report = guard.check(m, actual)
    assert code == 1 and "DRIFT" in report and "PASAPORTE" in report


def test_check_reproduces_the_real_fr_incident():
    """The historical bug end to end: prod carried the fictional imm11 FR text ids and
    NONE of the real AcroForm ids. The guard must go red with both signals."""
    m = guard.load_manifest(MANIFEST_PATH)
    actual = json_like(m)
    # prod as it actually was before remediation: fictional text ids, radios intact.
    actual["FR_cerfa_14571_v2024"]["text"] = {
        "nom", "prenoms", "date_naissance", "lieu_naissance", "nationalite",
        "numero_passeport", "profession", "sexe", "situation_familiale",
        "employeur", "date_delivrance", "date_expiration",
    }
    code, report = guard.check(m, actual)
    assert code == 1
    assert "MISSING" in report and "applicantSurname" in report      # real ids absent
    assert "STALE/UNEXPECTED" in report and "nom" in report          # fictional ids present


def test_check_reproduces_the_es_empty_incident():
    """ES had zero rows before the seed applied — every expected id is missing."""
    m = guard.load_manifest(MANIFEST_PATH)
    actual = json_like(m)
    actual["ES_ex17_v2024"] = {}  # prod ES totally empty
    code, report = guard.check(m, actual)
    assert code == 1 and "ES_ex17_v2024" in report and "MISSING" in report


def json_like(manifest):
    """Deep-copy the manifest's set-of-sets so a test can mutate 'actual' freely."""
    return {fid: {k: set(v) for k, v in kinds.items()} for fid, kinds in manifest.items()}

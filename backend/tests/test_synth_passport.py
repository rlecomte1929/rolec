"""Tests for the synthetic passport generator (C1-17a / AIQ-512).

Validation criteria proven here:
  1. Output PDF parses via the C1-02 MRZ parser with all_check_digits_valid=True.
  2. Names with diacritics render and MRZ-transliterate.
  3. CLI/API accepts ISO 3166-1 alpha-3 country codes (and rejects bad ones).
  4. SPECIMEN / TEST DOCUMENT disclaimers are stamped (render refuses otherwise).
  5. Tool is for test fixtures only (licence declaration in the docstring).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

import pytest

import pdfplumber

from backend.relopass.docs.mrz import parse_mrz

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "synth_passport.py"

_spec = importlib.util.spec_from_file_location("synth_passport", _SCRIPT)
synth = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
# Register before exec so dataclasses can resolve the module's namespace.
sys.modules["synth_passport"] = synth
_spec.loader.exec_module(synth)


def _fields(**overrides):
    base = dict(
        surname="SHARMA",
        given_names="PRIYA",
        date_of_birth=date(1992, 3, 14),
        expiry_date=date(2032, 6, 30),
        nationality="IND",
        issuing_state="IND",
        document_number="L8989ABCD",
        sex="F",
    )
    base.update(overrides)
    return synth.PassportFields(**base)


# ── Criterion 1: MRZ check digits valid ──────────────────────────────────────
def test_build_td3_mrz_round_trips_with_valid_check_digits():
    line1, line2 = synth.build_td3_mrz(_fields())
    assert len(line1) == 44 and len(line2) == 44

    result = parse_mrz(f"{line1}\n{line2}")
    assert result.format == "TD3"
    assert result.all_check_digits_valid is True
    assert result.nationality_iso3 == "IND"
    assert result.issuing_state_iso3 == "IND"
    assert result.date_of_birth == date(1992, 3, 14)
    assert result.expiry_date == date(2032, 6, 30)
    assert result.sex == "F"


def test_empty_personal_number_still_valid():
    line1, line2 = synth.build_td3_mrz(_fields(personal_number=""))
    result = parse_mrz(f"{line1}\n{line2}")
    assert result.all_check_digits_valid is True


# ── Criterion 2: diacritics transliterate and stay valid ─────────────────────
@pytest.mark.parametrize(
    "surname, expected_fragment",
    [("Müller", "MULLER"), ("Bouchard", "BOUCHARD"), ("García", "GARCIA")],
)
def test_diacritics_fold_into_mrz(surname, expected_fragment):
    line1, line2 = synth.build_td3_mrz(_fields(surname=surname, issuing_state="DEU"))
    assert expected_fragment in line1
    # diacritic characters must never leak into the MRZ
    assert all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<P" for ch in line1)
    assert parse_mrz(f"{line1}\n{line2}").all_check_digits_valid is True


def test_multiple_given_names_separated_by_filler():
    line1, _ = synth.build_td3_mrz(_fields(given_names="Priya Anne"))
    assert "PRIYA<ANNE" in line1


# ── Criterion 3: ISO alpha-3 handling ────────────────────────────────────────
def test_default_country_is_icao_test_code():
    line1, line2 = synth.build_td3_mrz(
        _fields(nationality=synth.ICAO_TEST_CODE, issuing_state=synth.ICAO_TEST_CODE)
    )
    result = parse_mrz(f"{line1}\n{line2}")
    assert result.issuing_state_iso3 == "UTO"
    assert result.nationality_iso3 == "UTO"


@pytest.mark.parametrize("bad", ["US", "USAA", "12A", ""])
def test_invalid_country_code_rejected(bad):
    with pytest.raises(ValueError):
        synth.build_td3_mrz(_fields(nationality=bad))


# ── Criterion 4 + end-to-end: PDF parses + carries disclaimers ───────────────
def test_pdf_generation_round_trips_through_parser(tmp_path):
    out = tmp_path / "nested" / "passport.pdf"
    fields = _fields()
    path = synth.render_passport_pdf(fields, str(out))

    assert Path(path).exists()
    assert Path(path).stat().st_size > 0

    line1, line2 = synth.build_td3_mrz(fields)
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # MRZ must survive into the PDF text layer (whitespace-insensitive match).
    compact = re.sub(r"\s", "", text)
    assert line1 in compact and line2 in compact

    # Parse the MRZ recovered FROM the PDF, not from the generator return value.
    idx = compact.index(line1)
    recovered = parse_mrz(f"{compact[idx:idx + 44]}\n{compact[idx + 44:idx + 88]}")
    assert recovered.all_check_digits_valid is True

    # Disclaimers present so the artefact can't be mistaken for a real passport.
    assert "SPECIMEN" in text
    assert "TEST DOCUMENT" in text.upper()


def test_render_refuses_without_specimen_watermark(tmp_path):
    with pytest.raises(ValueError):
        synth.render_passport_pdf(_fields(), str(tmp_path / "p.pdf"), specimen=False)


# ── Criterion 5: licence/usage declaration in the tool docstring ─────────────
def test_module_docstring_declares_test_only_usage():
    doc = (synth.__doc__ or "").upper()
    assert "TEST FIXTURE" in doc
    assert "SPECIMEN" in doc

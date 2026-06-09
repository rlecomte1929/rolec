"""AI-I.3b — IBAN recognizer fixture test.

Validation criterion (AIQ-671): a 50-IBAN fixture (25 valid + 25 invalid) must
hit recall ≥95% on the valid set and false-positive ≤1% on the invalid set.

The recall/FP gate runs against the pure-Python validator (`is_valid_iban`), so
it needs no presidio install and can run in the default CI suite. A second test,
guarded by `importorskip`, exercises the actual presidio recognizer wiring.
"""
from __future__ import annotations

import pytest

from backend.app.services.pii.presidio_recognizers import iban as iban_mod

# 25 structurally valid IBANs (correct format, country length, mod-97 checksum)
# across the corridors that matter for the immigration flows + a broad EU spread.
VALID_IBANS = [
    "DE89370400440532013000",            # Germany
    "FR1420041010050500013M02606",       # France
    "GB29NWBK60161331926819",            # United Kingdom
    "NO9386011117947",                   # Norway
    "ES9121000418450200051332",          # Spain
    "IT60X0542811101000000123456",       # Italy
    "NL91ABNA0417164300",                # Netherlands
    "BE68539007547034",                  # Belgium
    "CH9300762011623852957",             # Switzerland
    "AT611904300234573201",              # Austria
    "PL61109010140000071219812874",      # Poland
    "SE4550000000058398257466",          # Sweden
    "DK5000400440116243",                # Denmark
    "FI2112345600000785",                # Finland
    "PT50000201231234567890154",         # Portugal
    "IE29AIBK93115212345678",            # Ireland
    "LU280019400644750000",              # Luxembourg
    "GR1601101250000000012300695",       # Greece
    "CZ6508000000192000145399",          # Czechia
    "HU42117730161111101800000000",      # Hungary
    "RO49AAAA1B31007593840000",          # Romania
    "HR1210010051863000160",             # Croatia
    "BG80BNBG96611020345678",            # Bulgaria
    "IS140159260076545510730339",        # Iceland
    "GI75NWBK000000007099453",           # Gibraltar
]

# 25 invalid IBANs: broken mod-97 checksum, wrong country length, or malformed.
INVALID_IBANS = [
    "DE89370400440532013001",            # bad checksum (last digit flipped)
    "FR1420041010050500013M02607",       # bad checksum
    "GB29NWBK60161331926818",            # bad checksum
    "NO9386011117948",                   # bad checksum
    "ES9121000418450200051333",          # bad checksum
    "NL91ABNA0417164301",                # bad checksum
    "BE68539007547035",                  # bad checksum
    "CH9300762011623852958",             # bad checksum
    "AT611904300234573202",              # bad checksum
    "IT60X0542811101000000123457",       # bad checksum
    "SE4550000000058398257467",          # bad checksum
    "DK5000400440116244",                # bad checksum
    "FI2112345600000786",                # bad checksum
    "PT50000201231234567890155",         # bad checksum
    "IE29AIBK93115212345670",            # bad checksum
    "DE00370400440532013000",            # invalid check digits (00)
    "DE8937040044053201",                # too short for DE (len 18 ≠ 22)
    "DE89370400440532013000000",         # too long for DE (len 25 ≠ 22)
    "ZZ89370400440532013000",            # unknown country + bad checksum
    "1234567890123456",                  # no country prefix (malformed)
    "GB29NWBK6016133192681",             # wrong length for GB (21 ≠ 22)
    "FR1420041010050500013M0260",        # wrong length for FR (26 ≠ 27)
    "DEAB370400440532013000",            # letters where check digits go
    "NO938601111794",                    # wrong length for NO (14 ≠ 15)
    "XX00",                              # far too short
]


def test_fixture_is_5050():
    assert len(VALID_IBANS) == 25
    assert len(INVALID_IBANS) == 25


def test_recall_on_valid_ibans():
    """≥95% of the valid IBANs must be recognised (≥24 of 25)."""
    hits = [s for s in VALID_IBANS if iban_mod.is_valid_iban(s)]
    recall = len(hits) / len(VALID_IBANS)
    missed = [s for s in VALID_IBANS if not iban_mod.is_valid_iban(s)]
    assert recall >= 0.95, f"recall {recall:.2%} below 0.95; missed: {missed}"


def test_false_positive_on_invalid_ibans():
    """≤1% of the invalid IBANs may slip through (effectively 0 of 25)."""
    false_pos = [s for s in INVALID_IBANS if iban_mod.is_valid_iban(s)]
    fp_rate = len(false_pos) / len(INVALID_IBANS)
    assert fp_rate <= 0.01, f"FP {fp_rate:.2%} above 0.01; leaked: {false_pos}"


# --------------------------------------------------------------------------
# Presidio wiring — only runs where presidio-analyzer is installed.
# --------------------------------------------------------------------------

def test_presidio_recognizer_wiring():
    pytest.importorskip(
        "presidio_analyzer", reason="presidio-analyzer not installed"
    )
    recognizers = iban_mod.get_recognizers()
    assert len(recognizers) == 1
    rec = recognizers[0]
    assert rec.supported_entities == [iban_mod.IBAN_ENTITY]

    # A checksum-valid IBAN is detected; a checksum-broken one is rejected by
    # validate_result even though it matches the pattern.
    valid_results = rec.analyze(
        "iban DE89370400440532013000", entities=[iban_mod.IBAN_ENTITY], nlp_artifacts=None
    )
    assert valid_results, "valid IBAN should be detected"
    assert valid_results[0].score >= 0.5

    invalid_results = rec.analyze(
        "iban DE89370400440532013001", entities=[iban_mod.IBAN_ENTITY], nlp_artifacts=None
    )
    assert not invalid_results, "checksum-invalid IBAN must be rejected"


def test_presidio_detects_iban_in_free_text():
    pytest.importorskip(
        "presidio_analyzer", reason="presidio-analyzer not installed"
    )
    rec = iban_mod.get_recognizers()[0]

    # Compact IBAN embedded in a sentence.
    compact = rec.analyze(
        "Please wire it to GB29NWBK60161331926819 by Friday.",
        entities=[iban_mod.IBAN_ENTITY],
        nlp_artifacts=None,
    )
    assert compact, "compact IBAN in text should be detected"

    # 4-char-group spaced IBAN should also be detected (and validated).
    spaced = rec.analyze(
        "IBAN: DE89 3704 0044 0532 0130 00 — thanks.",
        entities=[iban_mod.IBAN_ENTITY],
        nlp_artifacts=None,
    )
    assert spaced, "spaced IBAN in text should be detected"


def test_registry_includes_iban_recognizer():
    pytest.importorskip(
        "presidio_analyzer", reason="presidio-analyzer not installed"
    )
    from backend.app.services.pii.presidio_recognizers import (
        build_relopass_recognizer_registry,
    )

    registry = build_relopass_recognizer_registry(load_predefined=False)
    entities = registry.get_supported_entities()
    assert iban_mod.IBAN_ENTITY in entities

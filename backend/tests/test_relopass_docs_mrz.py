"""
Tests for relopass.docs.mrz (C1-02).

Covers the ICAO 9303 canonical example, country-fixture transliteration
(German ü→UE, Norwegian ø→OE, plus FR/US/IN), and the WARN-not-raise
behaviour on broken MRZs. Pure unit tests — no DB, no network.

The test file lives under backend/tests/ so it runs with the existing
pytest configuration. The module under test is at /relopass/docs/mrz.py
(a new top-level package created in C1-02).
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.relopass.docs.mrz import (  # noqa: E402
    DocumentValidationFinding,
    MRZParseResult,
    compute_check_digit,
    fold_diacritics,
    parse_mrz,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────────
#
# Each fixture below was hand-built with the same algorithm the parser uses
# (compute_check_digit) so we know the check digits are correct. Synthetic;
# no real passport data.

# Canonical ICAO 9303 example. Verified against the public specimen in the
# ICAO documentation.
CANONICAL_TD3 = (
    "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
    "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
)

# FR — straightforward Latin name; no transliteration needed.
# Doc number AB1234567, DOB 1985-03-15, expiry 2028-06-20, no personal no.
def _build_td3(
    *,
    issuing: str,
    surname: str,
    given: str,
    doc_number: str,
    nationality: str,
    dob: str,
    sex: str,
    expiry: str,
    personal: str = "",
) -> str:
    """Helper that constructs a valid TD3 string with correct check digits.

    Names are uppercased and '<'-padded into the 39-char name field.
    `doc_number` and `personal` are '<'-padded to 9 and 14 chars.
    """
    name_field = f"{surname}<<{given}".upper()
    name_field = name_field.ljust(39, "<")[:39]
    line1 = f"P<{issuing}{name_field}"
    assert len(line1) == 44, f"line1 wrong len: {len(line1)}"

    doc_padded = doc_number.upper().ljust(9, "<")[:9]
    personal_padded = personal.upper().ljust(14, "<")[:14]

    doc_cd = compute_check_digit(doc_padded)
    dob_cd = compute_check_digit(dob)
    expiry_cd = compute_check_digit(expiry)
    personal_cd = compute_check_digit(personal_padded)

    composite_input = (
        doc_padded
        + str(doc_cd)
        + dob
        + str(dob_cd)
        + expiry
        + str(expiry_cd)
        + personal_padded
        + str(personal_cd)
    )
    composite_cd = compute_check_digit(composite_input)

    line2 = (
        f"{doc_padded}{doc_cd}{nationality}{dob}{dob_cd}{sex}{expiry}{expiry_cd}"
        f"{personal_padded}{personal_cd}{composite_cd}"
    )
    assert len(line2) == 44, f"line2 wrong len: {len(line2)}"
    return f"{line1}\n{line2}"


class MRZCheckDigitTests(unittest.TestCase):
    """Direct tests of compute_check_digit against published ICAO values."""

    def test_doc_number_canonical(self) -> None:
        # L898902C3 → 6 (per ICAO 9303 Part 3 §4.9 worked example)
        self.assertEqual(compute_check_digit("L898902C3"), 6)

    def test_dob_canonical(self) -> None:
        # 740812 → 2
        self.assertEqual(compute_check_digit("740812"), 2)

    def test_expiry_canonical(self) -> None:
        # 120415 → 9
        self.assertEqual(compute_check_digit("120415"), 9)

    def test_personal_canonical(self) -> None:
        # ZE184226B<<<<< → 1
        self.assertEqual(compute_check_digit("ZE184226B<<<<<"), 1)

    def test_empty_string(self) -> None:
        # All-zero sum mod 10 = 0
        self.assertEqual(compute_check_digit(""), 0)

    def test_all_fillers(self) -> None:
        # Every '<' contributes 0
        self.assertEqual(compute_check_digit("<<<<<<<<<"), 0)


class MRZCanonicalTests(unittest.TestCase):
    """The ICAO canonical example must parse with every field intact."""

    def test_canonical_example_parses_cleanly(self) -> None:
        r = parse_mrz(CANONICAL_TD3)
        self.assertEqual(r.format, "TD3")
        self.assertTrue(r.is_well_formed)
        self.assertEqual(r.surname, "Eriksson")
        self.assertEqual(r.given_names, "Anna Maria")
        self.assertEqual(r.document_number, "L898902C3")
        self.assertEqual(r.nationality_iso3, "UTO")
        self.assertEqual(r.issuing_state_iso3, "UTO")
        self.assertEqual(r.date_of_birth, date(1974, 8, 12))
        self.assertEqual(r.sex, "F")
        self.assertEqual(r.expiry_date, date(2012, 4, 15))
        self.assertEqual(r.personal_number, "ZE184226B")
        self.assertTrue(r.all_check_digits_valid)
        # No findings — every check digit passed.
        self.assertEqual(
            [f for f in r.findings if f.severity in ("WARN", "ERROR")],
            [],
        )


class MRZCountryFixturesTests(unittest.TestCase):
    """One fixture per target country covering the transliteration paths."""

    def test_fr_plain_latin(self) -> None:
        text = _build_td3(
            issuing="FRA",
            surname="DUPONT",
            given="JEAN<MARIE",
            doc_number="AB1234567",
            nationality="FRA",
            dob="850315",
            sex="M",
            expiry="280620",
        )
        r = parse_mrz(text)
        self.assertEqual(r.format, "TD3")
        self.assertEqual(r.surname, "Dupont")
        self.assertEqual(r.given_names, "Jean Marie")
        self.assertEqual(r.nationality_iso3, "FRA")
        self.assertEqual(r.date_of_birth, date(1985, 3, 15))
        self.assertTrue(r.all_check_digits_valid)

    def test_de_with_umlaut_round_trip(self) -> None:
        # MRZ encodes ü → UE. Parser must reverse this for German passports.
        text = _build_td3(
            issuing="DEU",
            surname="MUELLER",
            given="ANNA",
            doc_number="C01X00T47",
            nationality="DEU",
            dob="910405",
            sex="F",
            expiry="310705",
        )
        r = parse_mrz(text)
        self.assertEqual(r.surname, "Müller")
        self.assertEqual(r.given_names, "Anna")
        self.assertEqual(r.issuing_state_iso3, "DEU")
        self.assertTrue(r.all_check_digits_valid)

    def test_no_with_oe_round_trip(self) -> None:
        # Norwegian ø encoded as OE. Reverse mapping applies for NOR.
        text = _build_td3(
            issuing="NOR",
            surname="SOERENSEN",
            given="OLE",
            doc_number="N12345678",
            nationality="NOR",
            dob="800101",
            sex="M",
            expiry="300101",
        )
        r = parse_mrz(text)
        # Note: 'SOERENSEN' contains 'OE' digraph → 'Ø'; output is 'Sørensen'
        self.assertEqual(r.surname, "Sørensen")
        self.assertEqual(r.given_names, "Ole")
        self.assertEqual(r.issuing_state_iso3, "NOR")

    def test_in_latin_transliteration(self) -> None:
        # Indian passports MRZ-encode Hindi-origin names in Latin
        # (transliterated by the issuing authority). v1 does not reverse-map
        # Devanagari; we keep the Latin form the MRZ already contains.
        text = _build_td3(
            issuing="IND",
            surname="SHARMA",
            given="PRIYA",
            doc_number="J0123456A",
            nationality="IND",
            dob="950528",
            sex="F",
            expiry="290528",
        )
        r = parse_mrz(text)
        self.assertEqual(r.surname, "Sharma")
        self.assertEqual(r.given_names, "Priya")
        self.assertTrue(r.all_check_digits_valid)

    def test_us_straightforward(self) -> None:
        text = _build_td3(
            issuing="USA",
            surname="SMITH",
            given="JOHN<Q",
            doc_number="987654321",
            nationality="USA",
            dob="700415",
            sex="M",
            expiry="320101",
        )
        r = parse_mrz(text)
        self.assertEqual(r.surname, "Smith")
        # 'JOHN<Q' → 'JOHN Q' → 'John Q'
        self.assertEqual(r.given_names, "John Q")
        self.assertEqual(r.nationality_iso3, "USA")


class MRZBrokenFixturesTests(unittest.TestCase):
    """Deliberately broken MRZs must surface WARN findings, not raise."""

    def test_doc_number_check_digit_wrong_emits_warn(self) -> None:
        # Build a valid string, then flip the doc-number check digit.
        good = _build_td3(
            issuing="FRA",
            surname="DUPONT",
            given="JEAN",
            doc_number="AB1234567",
            nationality="FRA",
            dob="850315",
            sex="M",
            expiry="280620",
        )
        # Locate the doc-number check digit (position 9 on line 2) and flip it.
        line1, line2 = good.split("\n")
        wrong_cd = "9" if line2[9] != "9" else "0"
        broken = line1 + "\n" + line2[:9] + wrong_cd + line2[10:]
        r = parse_mrz(broken)
        # Result is still well-formed (parses), but the doc-number check fails.
        self.assertTrue(r.is_well_formed)
        self.assertFalse(r.all_check_digits_valid)
        self.assertFalse(r.check_digits["document_number"].passed)
        # At least one WARN finding for the failed check digit.
        warns = [f for f in r.findings if f.severity == "WARN"]
        self.assertTrue(any(f.code == "MRZ_CHECK_DIGIT_FAIL" for f in warns))

    def test_wrong_line_count_emits_error(self) -> None:
        r = parse_mrz("just one line")
        self.assertEqual(r.format, "UNKNOWN")
        self.assertFalse(r.is_well_formed)
        errors = [f for f in r.findings if f.severity == "ERROR"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "MRZ_FORMAT_UNRECOGNIZED")

    def test_wrong_line_length_emits_error(self) -> None:
        # Two lines but each is 40 chars instead of 44.
        r = parse_mrz("P<FRA" + "<" * 35 + "\n" + "X" * 40)
        self.assertEqual(r.format, "UNKNOWN")
        errors = [f for f in r.findings if f.severity == "ERROR"]
        self.assertEqual(len(errors), 1)

    def test_invalid_date_returns_none_not_exception(self) -> None:
        # DOB '999999' is not a valid date but must not crash.
        text = _build_td3(
            issuing="FRA",
            surname="DUPONT",
            given="JEAN",
            doc_number="AB1234567",
            nationality="FRA",
            dob="999999",  # nonsense — check digit still computes
            sex="M",
            expiry="280620",
        )
        r = parse_mrz(text)
        self.assertEqual(r.format, "TD3")
        self.assertIsNone(r.date_of_birth)  # didn't crash

    def test_missing_sex_byte_returns_none(self) -> None:
        # Build then replace sex slot with '<' (some old MRZs use this).
        text = _build_td3(
            issuing="FRA",
            surname="DUPONT",
            given="JEAN",
            doc_number="AB1234567",
            nationality="FRA",
            dob="850315",
            sex="<",
            expiry="280620",
        )
        r = parse_mrz(text)
        self.assertEqual(r.format, "TD3")
        # sex '<' is not 'M' or 'F' → returned as None
        self.assertIsNone(r.sex)


class MRZTransliterationTests(unittest.TestCase):
    """Direct tests of the diacritic-fold helper."""

    def test_fold_basic_diacritics(self) -> None:
        self.assertEqual(fold_diacritics("José"), "Jose")
        self.assertEqual(fold_diacritics("Müller"), "Muller")
        self.assertEqual(fold_diacritics("Şahin"), "Sahin")
        self.assertEqual(fold_diacritics("Łukasz"), "Łukasz")  # Ł has no decomposition

    def test_fold_preserves_ascii(self) -> None:
        self.assertEqual(fold_diacritics("PLAIN"), "PLAIN")


if __name__ == "__main__":
    unittest.main()

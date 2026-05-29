"""Tests for backend/relopass/normalize/ — C1-06.

Acceptance: >= 50 tests passing. Covers the 7 validation criteria from the
C1-06 Notion task plus boundary cases per submodule.
"""
from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.relopass.normalize import (  # noqa: E402
    normalize_name,
    parse_date,
    parse_address,
    normalize_employer,
    parse_money,
    LocaleHintSuggestion,
)
from backend.relopass.normalize.money import annualize  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Names — ICAO 9303 transliteration + particles + Devanagari
# ─────────────────────────────────────────────────────────────────────────────


class NameTests(unittest.TestCase):
    def test_simple_us_name(self) -> None:
        r = normalize_name("John Smith", issuing_state_iso3="USA")
        self.assertEqual(r.surname_main, "SMITH")
        self.assertEqual(r.given_names, ("John",))
        self.assertEqual(r.initial, "J")

    def test_comma_separated_form(self) -> None:
        r = normalize_name("Smith, John")
        self.assertEqual(r.surname_main, "SMITH")
        self.assertEqual(r.given_names, ("John",))

    def test_de_umlaut_folds_for_deu(self) -> None:
        r = normalize_name("Müller, Anna", issuing_state_iso3="DEU")
        self.assertEqual(r.surname_main, "MUELLER")
        # Substitution should be recorded for audit.
        self.assertTrue(any("Ü" in s for s in r.transliteration_applied))

    def test_de_umlaut_round_trip(self) -> None:
        # MUELLER (already transliterated) should also yield MUELLER.
        r = normalize_name("MUELLER, ANNA", issuing_state_iso3="DEU")
        self.assertEqual(r.surname_main, "MUELLER")

    def test_de_eszett_folds(self) -> None:
        r = normalize_name("Weiß, Karl", issuing_state_iso3="DEU")
        self.assertEqual(r.surname_main, "WEISS")

    def test_norwegian_oe_folds_for_nor(self) -> None:
        r = normalize_name("Sørensen, Ole", issuing_state_iso3="NOR")
        self.assertEqual(r.surname_main, "SOERENSEN")

    def test_norwegian_aring_folds_for_nor(self) -> None:
        r = normalize_name("Hågård, Astrid", issuing_state_iso3="NOR")
        self.assertEqual(r.surname_main, "HAAGAARD")

    def test_french_diacritic_strips_for_fra(self) -> None:
        # FR isn't in the ICAO digraph set; expect general Latin fold.
        r = normalize_name("Dupont, Hélène", issuing_state_iso3="FRA")
        self.assertEqual(r.surname_main, "DUPONT")
        # Given name diacritic dropped.
        self.assertEqual(r.given_names, ("Helene",))

    def test_particle_de(self) -> None:
        r = normalize_name("de la Vega, Pablo")
        self.assertEqual(r.surname_main, "VEGA")
        # Particle preserved in the display form.
        self.assertIn("De La", r.surname_with_particle)

    def test_particle_van_der(self) -> None:
        r = normalize_name("van der Berg, Anna")
        self.assertEqual(r.surname_main, "BERG")
        self.assertIn("Van Der", r.surname_with_particle)

    def test_particle_von(self) -> None:
        r = normalize_name("von Habsburg, Otto")
        self.assertEqual(r.surname_main, "HABSBURG")

    def test_devanagari_iso_15919(self) -> None:
        # Hindi: शर्मा (Sharma) as surname; प्रिया (Priya) as given name.
        # Use comma form so the surname/given split is explicit — the
        # naked "last token = surname" heuristic is wrong for Indian
        # passport convention where the surname is typed first.
        r = normalize_name("शर्मा, प्रिया")
        # ISO 15919 minimal: श → ś. After diacritic strip → S; uppercased.
        self.assertTrue(
            r.surname_main.startswith("S"),
            f"expected S* surname, got {r.surname_main!r}",
        )
        self.assertGreater(len(r.surname_main), 0)
        self.assertGreater(len(r.given_names), 0)

    def test_devanagari_naked_whitespace_falls_back(self) -> None:
        # Without comma + without an issuing-state context, the naked-text
        # parse uses the "last token = surname" heuristic. This is a
        # documented limitation; callers with passport context should pre-split.
        r = normalize_name("शर्मा प्रिया")
        # We don't assert which token wins — just that no crash occurred and
        # both tokens transliterated successfully.
        self.assertGreater(len(r.surname_main), 0)

    def test_normalized_join_used_for_embedding(self) -> None:
        r = normalize_name("Smith, John", issuing_state_iso3="USA")
        # The normalized_join field is what the entity-resolution embedding consumes.
        self.assertEqual(r.normalized_join, "SMITH John")

    def test_empty_input(self) -> None:
        r = normalize_name("")
        self.assertEqual(r.surname_main, "")
        self.assertEqual(r.given_names, ())

    def test_none_input(self) -> None:
        r = normalize_name(None)  # type: ignore[arg-type]
        self.assertEqual(r.surname_main, "")


# ─────────────────────────────────────────────────────────────────────────────
# Dates — 4-rule precedence + ambiguity
# ─────────────────────────────────────────────────────────────────────────────


class DateTests(unittest.TestCase):
    def test_iso_format(self) -> None:
        r = parse_date("2025-04-03")
        self.assertEqual(r.iso, "2025-04-03")
        self.assertEqual(r.rule_used, "iso")
        self.assertGreaterEqual(r.confidence, 0.99)

    def test_iso_with_slashes(self) -> None:
        r = parse_date("2025/04/03")
        self.assertEqual(r.iso, "2025-04-03")
        self.assertEqual(r.rule_used, "iso")

    def test_iso_invalid_date(self) -> None:
        r = parse_date("2025-02-30")
        # Falls through to ambiguous/freeform — should still not crash and yield None.
        self.assertTrue(r.iso is None or r.confidence < 0.85)

    def test_mrz_yymmdd(self) -> None:
        r = parse_date("740812")  # 12 Aug 1974
        self.assertEqual(r.iso, "1974-08-12")
        self.assertEqual(r.rule_used, "mrz")

    def test_mrz_post_pivot_century(self) -> None:
        r = parse_date("250115")  # 15 Jan 2025
        self.assertEqual(r.iso, "2025-01-15")

    def test_locale_dmy_fr(self) -> None:
        r = parse_date("03/04/2025", locale_hint="FR")
        self.assertEqual(r.iso, "2025-04-03")
        self.assertEqual(r.rule_used, "locale_dmy")

    def test_locale_dmy_de(self) -> None:
        r = parse_date("12.08.1974", locale_hint="DE")
        self.assertEqual(r.iso, "1974-08-12")

    def test_locale_dmy_no(self) -> None:
        r = parse_date("12-08-1974", locale_hint="NO")
        self.assertEqual(r.iso, "1974-08-12")

    def test_locale_mdy_us(self) -> None:
        r = parse_date("04/03/2025", locale_hint="US")
        self.assertEqual(r.iso, "2025-04-03")
        self.assertEqual(r.rule_used, "locale_mdy")

    def test_ambiguous_no_hint_emits_finding(self) -> None:
        # Validation criterion #4: 03/04/2025 with no hint → confidence ≤ 0.6
        # AND a LocaleHintSuggestion finding.
        r = parse_date("03/04/2025")
        self.assertLessEqual(r.confidence, 0.6)
        self.assertEqual(r.rule_used, "ambiguous_no_hint")
        self.assertTrue(any(isinstance(f, LocaleHintSuggestion) for f in r.findings))

    def test_unambiguous_no_hint_works(self) -> None:
        # 13/04/2025 only fits DMY (month 13 invalid under MDY)
        r = parse_date("13/04/2025")
        self.assertEqual(r.iso, "2025-04-13")
        self.assertGreater(r.confidence, 0.6)

    def test_year_two_digits_pivot(self) -> None:
        # Under the < 50 pivot rule
        r = parse_date("01/02/49", locale_hint="FR")
        self.assertEqual(r.iso, "2049-02-01")
        r = parse_date("01/02/50", locale_hint="FR")
        self.assertEqual(r.iso, "1950-02-01")

    def test_freeform_with_hint(self) -> None:
        r = parse_date("12 August 1974", locale_hint="GB")
        self.assertEqual(r.iso, "1974-08-12")

    def test_empty_and_none(self) -> None:
        self.assertIsNone(parse_date("").iso)
        self.assertIsNone(parse_date(None).iso)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Addresses — FR / DE / NO + permissive IN + US / UK
# ─────────────────────────────────────────────────────────────────────────────


class AddressTests(unittest.TestCase):
    def test_fr_basic(self) -> None:
        a = parse_address("10 Rue de la Paix, 75002 Paris", country_iso3="FRA")
        self.assertEqual(a.country_iso3, "FRA")
        self.assertEqual(a.postal_code, "75002")
        self.assertIn("Paris", a.locality)
        self.assertIn("Rue de la Paix", a.street_line_1 or "")
        self.assertEqual(len(a.normalized_hash), 64)

    def test_fr_uppercase_locality(self) -> None:
        a = parse_address("18 Avenue Foch, 75116 PARIS", country_iso3="FRA")
        self.assertEqual(a.postal_code, "75116")
        self.assertIn("PARIS", (a.locality or "").upper())

    def test_de_basic(self) -> None:
        a = parse_address("Hauptstraße 5, 10117 Berlin", country_iso3="DEU")
        self.assertEqual(a.country_iso3, "DEU")
        self.assertEqual(a.postal_code, "10117")
        self.assertIn("Berlin", a.locality)

    def test_no_basic(self) -> None:
        a = parse_address("Karl Johans gate 1, 0154 Oslo", country_iso3="NOR")
        self.assertEqual(a.country_iso3, "NOR")
        self.assertEqual(a.postal_code, "0154")
        self.assertIn("Oslo", a.locality)

    def test_us_with_state_and_zip(self) -> None:
        a = parse_address("1600 Pennsylvania Ave NW, Washington, DC 20500", country_iso3="USA")
        self.assertEqual(a.country_iso3, "USA")
        self.assertEqual(a.region, "DC")
        self.assertEqual(a.postal_code, "20500")

    def test_uk_postcode(self) -> None:
        a = parse_address("10 Downing Street, London SW1A 2AA", country_iso3="GBR")
        self.assertEqual(a.country_iso3, "GBR")
        self.assertIn("SW1A 2AA", a.postal_code or "")
        self.assertIn("London", a.locality)

    def test_in_permissive_fallback(self) -> None:
        # Validation criterion #5: Indian addresses fall to permissive schema.
        text = "B-12, Lajpat Nagar, New Delhi 110024, India"
        a = parse_address(text, country_iso3="IND")
        self.assertEqual(a.country_iso3, "IND")
        # Permissive path: the whole address ends up on street_line_1.
        self.assertIn("Lajpat Nagar", a.street_line_1 or "")
        # Confidence is low for the permissive bucket.
        self.assertLess(a.confidence, 0.7)

    def test_normalized_hash_stable(self) -> None:
        a1 = parse_address("10 Rue de la Paix, 75002 Paris", country_iso3="FRA")
        a2 = parse_address("10 Rue de la Paix,   75002   Paris", country_iso3="FRA")
        self.assertEqual(a1.normalized_hash, a2.normalized_hash)

    def test_no_country_hint_autodetect_fr(self) -> None:
        a = parse_address("10 Rue de la Paix, 75002 Paris")
        # Should still resolve to FRA via the postcode pattern.
        self.assertEqual(a.country_iso3, "FRA")

    def test_empty_and_none(self) -> None:
        self.assertIsNone(parse_address("").street_line_1)
        self.assertIsNone(parse_address(None).street_line_1)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Employers — legal-suffix stripping + registry-id detection (PF-1)
# ─────────────────────────────────────────────────────────────────────────────


class EmployerTests(unittest.TestCase):
    def test_fr_sarl(self) -> None:
        r = normalize_employer("Acme SARL", country_iso3="FRA")
        self.assertEqual(r.legal_suffix, "SARL")
        self.assertEqual(r.legal_name_stripped, "ACME")

    def test_fr_sas_with_dots(self) -> None:
        r = normalize_employer("Acme S.A.S.", country_iso3="FRA")
        self.assertEqual(r.legal_suffix, "SAS")
        self.assertEqual(r.legal_name_stripped, "ACME")

    def test_de_gmbh(self) -> None:
        r = normalize_employer("Beispiel GmbH", country_iso3="DEU")
        self.assertEqual(r.legal_suffix, "GMBH")
        self.assertEqual(r.legal_name_stripped, "BEISPIEL")

    def test_de_ag(self) -> None:
        r = normalize_employer("Siemens AG", country_iso3="DEU")
        self.assertEqual(r.legal_suffix, "AG")

    def test_no_as(self) -> None:
        r = normalize_employer("Equinor AS", country_iso3="NOR")
        self.assertEqual(r.legal_suffix, "AS")

    def test_us_inc(self) -> None:
        r = normalize_employer("Acme Inc.", country_iso3="USA")
        self.assertEqual(r.legal_suffix, "INC")
        self.assertEqual(r.legal_name_stripped, "ACME")

    def test_uk_ltd(self) -> None:
        r = normalize_employer("Beta Ltd", country_iso3="GBR")
        self.assertEqual(r.legal_suffix, "LTD")

    def test_in_private_limited(self) -> None:
        # Must match the multi-word suffix before single-word 'LIMITED'
        r = normalize_employer("Wipro Private Limited", country_iso3="IND")
        self.assertEqual(r.legal_suffix, "PRIVATE LIMITED")
        self.assertEqual(r.legal_name_stripped, "WIPRO")

    def test_no_suffix(self) -> None:
        r = normalize_employer("Acme", country_iso3="FRA")
        self.assertIsNone(r.legal_suffix)
        self.assertEqual(r.legal_name_stripped, "ACME")

    def test_diacritic_strip_on_stripped_name(self) -> None:
        r = normalize_employer("Société Générale SA", country_iso3="FRA")
        self.assertEqual(r.legal_suffix, "SA")
        # Diacritics removed for indexing form.
        self.assertEqual(r.legal_name_stripped, "SOCIETE GENERALE")

    # PF-1 registry-id format flexibility ----------------------------------

    def test_registry_siren(self) -> None:
        r = normalize_employer("Acme SARL", country_iso3="FRA", registry_id="552 100 554")
        self.assertEqual(r.registry_id_kind, "SIREN")

    def test_registry_hrb(self) -> None:
        r = normalize_employer("Beispiel GmbH", country_iso3="DEU", registry_id="HRB 12345")
        self.assertEqual(r.registry_id_kind, "HRB")

    def test_registry_orgnr(self) -> None:
        r = normalize_employer("Equinor AS", country_iso3="NOR", registry_id="923 609 016")
        self.assertEqual(r.registry_id_kind, "ORGNR")

    def test_registry_fein(self) -> None:
        r = normalize_employer("Acme Inc.", country_iso3="USA", registry_id="12-3456789")
        self.assertEqual(r.registry_id_kind, "FEIN")

    def test_registry_unknown_format_passes_through(self) -> None:
        # PF-1: no hardcoded rejection of unknown formats.
        r = normalize_employer("Acme Inc.", country_iso3="USA", registry_id="OFFICE-OF-WEIRD")
        # Pass-through means the registry_id is preserved even when kind is None.
        self.assertEqual(r.registry_id, "OFFICE-OF-WEIRD")
        self.assertIsNone(r.registry_id_kind)


# ─────────────────────────────────────────────────────────────────────────────
# Money — locale-aware parsing + currency disambiguation
# ─────────────────────────────────────────────────────────────────────────────


class MoneyTests(unittest.TestCase):
    def test_de_format(self) -> None:
        m = parse_money("1.234,56 €", locale_hint="DE")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertEqual(m.currency_iso3, "EUR")

    def test_fr_format_with_spaces(self) -> None:
        m = parse_money("1 234,56 €", locale_hint="FR")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertEqual(m.currency_iso3, "EUR")

    def test_no_kroner_with_hint(self) -> None:
        # Validation criterion #6: '1 234,56 kr' → Decimal('1234.56'), 'NOK'
        m = parse_money("1 234,56 kr", locale_hint="NO")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertEqual(m.currency_iso3, "NOK")

    def test_no_kroner_iso(self) -> None:
        m = parse_money("NOK 1 234,56")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertEqual(m.currency_iso3, "NOK")

    def test_us_dollars(self) -> None:
        m = parse_money("$1,234.56")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertEqual(m.currency_iso3, "USD")

    def test_uk_pound(self) -> None:
        m = parse_money("£1,234.56")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertEqual(m.currency_iso3, "GBP")

    def test_inr_lakhs_grouping(self) -> None:
        # Indian thousands grouping is unusual (lakhs/crores) — 12,34,567.00
        m = parse_money("₹ 12,34,567.00")
        self.assertEqual(m.amount, Decimal("1234567.00"))
        self.assertEqual(m.currency_iso3, "INR")

    def test_kr_no_hint_defaults_nok(self) -> None:
        m = parse_money("100 kr")
        # Default for 'kr' without hint is NOK per the spec.
        self.assertEqual(m.currency_iso3, "NOK")

    def test_kr_with_se_hint(self) -> None:
        m = parse_money("100 kr", locale_hint="SE")
        self.assertEqual(m.currency_iso3, "SEK")

    def test_no_currency_low_confidence(self) -> None:
        m = parse_money("1,234.56")
        self.assertEqual(m.amount, Decimal("1234.56"))
        self.assertIsNone(m.currency_iso3)
        self.assertLess(m.confidence, 0.7)

    def test_garbage_input(self) -> None:
        m = parse_money("not a price")
        self.assertIsNone(m.amount)

    def test_decimal_not_float(self) -> None:
        # Critical: returned amount must be Decimal, not float.
        m = parse_money("1.234,56 €", locale_hint="DE")
        self.assertIsInstance(m.amount, Decimal)


class AnnualizeTests(unittest.TestCase):
    def test_monthly_to_annual(self) -> None:
        self.assertEqual(annualize(Decimal("1000"), "month"), Decimal("12000.00"))

    def test_hourly_to_annual(self) -> None:
        self.assertEqual(annualize(Decimal("30"), "hour"), Decimal("60000.00"))

    def test_year_identity(self) -> None:
        self.assertEqual(annualize(Decimal("50000"), "year"), Decimal("50000.00"))

    def test_unknown_period_raises(self) -> None:
        with self.assertRaises(ValueError):
            annualize(Decimal("100"), "fortnightly")


if __name__ == "__main__":
    unittest.main()

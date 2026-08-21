"""
[AIQ-2033] "Indian" resolved to a nationality; "India" did not.

nationality_class.classify is the single source of truth for "does this person
have free movement?", and every downstream permit decision keys off it. None means
the employee gets a coverage gap instead of an answer.

Verified against the values actually stored in wizard_cases (prod, 2026-08-21):
"Hong Kong" and "India" resolved to None while FR, NL, IN, Singapore, Norway,
Norwegian, United Kingdom, Germany, France, United States and the rest resolved
fine.

The asymmetry was the tell. `_COUNTRY_NAME` began life as the free-movement set —
every entry an EU/EEA member — while `_ADJECTIVAL` grew non-EU entries (INDIAN,
AMERICAN, SINGAPOREAN, BRITISH). The gap stayed invisible because `to_iso()`
resolves seeded DESTINATIONS by name: "Germany" and "France" worked as places we
sell relocations TO, while "India" and "Hong Kong" — real nationalities, not
destinations — fell through.

**Nationality ranges over every country. The destination catalog does not.**

`test_every_country_resolves_in_both_forms` is the durable guard: it iterates both
tables rather than spot-checking the two values that happen to be in production
today, so the asymmetry cannot quietly return.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.nationality_class import (  # noqa: E402
    _ADJECTIVAL,
    _COUNTRY_NAME,
    _nationality_to_iso,
    classify,
)

DEST = "IRELAND"


class ProductionValuesResolveTests(unittest.TestCase):
    def test_the_two_values_that_failed_in_production(self) -> None:
        self.assertEqual(classify("India", DEST), "THIRD_COUNTRY")
        self.assertEqual(classify("Hong Kong", DEST), "THIRD_COUNTRY")

    def test_a_country_name_agrees_with_its_adjectival_form(self) -> None:
        self.assertEqual(classify("India", DEST), classify("Indian", DEST))

    def test_every_other_production_value_still_resolves(self) -> None:
        """Regression net over the real corpus — nothing that worked may stop."""
        for value in ("FR", "NL", "IN", "ES", "CA", "GB", "NO", "AD", "LB", "de",
                      "Singapore", "Norway", "Norwegian", "norwegian", "norway",
                      "United Kingdom", "Germany", "France", "United States",
                      "French", "Austrian"):
            self.assertIsNotNone(classify(value, DEST), f"{value!r} stopped resolving")


class AndreaTests(unittest.TestCase):
    """AIQ-1993 names Andrea, a Venezuelan national, as the first real ES->IE case.
    Anticipated rather than observed — no Venezuelan nationality is stored in
    production yet — but the same defect, and it would have met her on arrival."""

    def test_venezuela_resolves_in_every_form(self) -> None:
        for form in ("Venezuelan", "Venezuela", "VE", "venezuelan"):
            self.assertEqual(classify(form, DEST), "THIRD_COUNTRY", form)


class SymmetryTests(unittest.TestCase):
    def test_every_country_resolves_in_both_forms(self) -> None:
        """The durable guard. Iterates the tables instead of spot-checking, so a
        future country added to one table alone fails here rather than in prod."""
        adjectival = set(_ADJECTIVAL.values())
        by_name = set(_COUNTRY_NAME.values())
        self.assertEqual(
            adjectival - by_name, set(),
            "these have an adjectival form but no country name",
        )
        self.assertEqual(
            by_name - adjectival, set(),
            "these have a country name but no adjectival form",
        )

    def test_both_forms_of_each_country_agree(self) -> None:
        by_iso_adj = {iso: word for word, iso in _ADJECTIVAL.items()}
        for word, iso in _COUNTRY_NAME.items():
            self.assertEqual(
                _nationality_to_iso(word), iso, f"{word} -> wrong ISO",
            )
            adj = by_iso_adj.get(iso)
            if adj:
                self.assertEqual(
                    _nationality_to_iso(adj), _nationality_to_iso(word),
                    f"{adj} and {word} disagree",
                )

    def test_resolution_does_not_depend_on_the_destination_catalog(self) -> None:
        """Venezuela is not a seeded destination. If this passes only because
        someone later adds it to DESTINATIONS, the bug is back and hidden again."""
        from backend.app.services.nationality_class import _COUNTRY_NAME as names
        self.assertIn("VENEZUELA", names)
        self.assertEqual(_nationality_to_iso("Venezuela"), "VE")


class JunkStillRejectedTests(unittest.TestCase):
    """Production genuinely holds these. The module refuses unrecognised input
    because a stray keystroke landing on an EU alpha-2 code would fabricate a right
    of free movement — the expensive direction to be wrong in."""

    def test_junk_returns_none(self) -> None:
        for junk in ("asdas", "1212", "f", "dfgdfg", "ccvxcv", "sddvfd", "123", "33"):
            self.assertIsNone(classify(junk, DEST), f"{junk!r} resolved")

    def test_empty_and_none_return_none(self) -> None:
        self.assertIsNone(classify("", DEST))
        self.assertIsNone(classify(None, DEST))

    def test_a_typo_cannot_invent_free_movement(self) -> None:
        """The dangerous direction: an unrecognised value must never come back
        EU_EEA, because that tells someone they need no permit."""
        for junk in ("asdas", "dfgdfg", "zz", "qq", "xx"):
            self.assertNotEqual(classify(junk, DEST), "EU_EEA", junk)


if __name__ == "__main__":
    unittest.main()

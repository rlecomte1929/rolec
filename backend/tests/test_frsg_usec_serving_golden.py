"""Serving-scope golden test for the two non-EEA corridors FR→SG (Adrien) and US→EC (Abraham).

Companion to `test_esie_andrea_golden_fixture.py`. That fixture guards the hard case — an EEA
free mover who must still see the audience-scope rules but none of the nationality-determined
ones. SG and EC have NO free-movement scheme, so every foreign national is `THIRD_COUNTRY`
there; the failure mode to guard here is the opposite and simpler one: **a fact scoped
`nationality: "non-EEA"` must actually reach a French national moving to Singapore and a US
national moving to Ecuador.** If `nationality_applies` ever stopped classifying `FR→SG` /
`US→EC` as third-country, the whole corridor would silently serve nobody — exactly the
`public_corridor` nationality-gate regression this repo has hit before.

The batches these load are the ones committed for the two corridors; the personas mirror the
live `/api/public/corridor-requirements` response (nationality_class `THIRD_COUNTRY`, verified
2026-08-30).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.app.services.applies_to_matcher import apply_applies_to

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPORTS = REPO_ROOT / "docs" / "imports"

# The committed fact batches for each corridor (clean.ndjson = verify_ledger-confirmed rows).
_BATCHES = [
    "fr-sg-facts-2026-08-30",
    "us-ec-facts-2026-08-30",
    "sg-ec-browser-grounded-2026-08-30",
    "sg-ec-browser-grounded-2-2026-08-30",
]

ADRIEN = {"nationality": "France", "origin_country": "FR", "destination_country": "SG"}
ABRAHAM = {"nationality": "United States", "origin_country": "US", "destination_country": "EC"}
# EEA controls: an EU/EEA national going to the SAME non-EEA destination is ALSO third-country
# there (no free movement), so they must be served identically — a German moving to Singapore
# needs the work-pass facts as much as Adrien does.
GERMAN_TO_SG = {"nationality": "Germany", "origin_country": "DE", "destination_country": "SG"}


def _facts_for(dest: str) -> list[dict]:
    rows: list[dict] = []
    for batch in _BATCHES:
        clean = IMPORTS / batch / "clean.ndjson"
        if not clean.exists():
            continue
        for line in clean.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("destination_country") == dest:
                rows.append(r)
    return rows


def _served(facts: list[dict], persona: dict) -> set[str]:
    return {r["fact_key"] for r in facts if apply_applies_to(r.get("applies_to") or {}, persona)}


class FrSgServingGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts = _facts_for("SG")

    def test_the_corridor_has_committed_facts(self) -> None:
        # If this drops to zero the batches moved/renamed and the rest of the file is vacuous.
        self.assertGreaterEqual(len(self.facts), 17, "FR→SG fact batches missing")

    def test_adrien_is_served_every_fact(self) -> None:
        """A French national moving to Singapore is third-country there and must see all of it.
        A wrongful hide here is the corridor serving nobody."""
        served = _served(self.facts, ADRIEN)
        missing = {r["fact_key"] for r in self.facts} - served
        self.assertEqual(missing, set(), f"facts hidden from Adrien (FR→SG): {sorted(missing)}")

    def test_an_eea_national_to_singapore_is_served_identically(self) -> None:
        """No free movement into Singapore — an EU national is third-country there too."""
        self.assertEqual(_served(self.facts, GERMAN_TO_SG), _served(self.facts, ADRIEN))

    def test_every_fact_is_scoped_non_eea_professional(self) -> None:
        for r in self.facts:
            ap = r.get("applies_to") or {}
            self.assertEqual(ap.get("nationality"), "non-EEA", r["fact_key"])
            self.assertEqual(ap.get("status"), "professional", r["fact_key"])


class UsEcServingGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts = _facts_for("EC")

    def test_the_corridor_has_committed_facts(self) -> None:
        self.assertGreaterEqual(len(self.facts), 12, "US→EC fact batches missing")

    def test_abraham_is_served_every_fact(self) -> None:
        served = _served(self.facts, ABRAHAM)
        missing = {r["fact_key"] for r in self.facts} - served
        self.assertEqual(missing, set(), f"facts hidden from Abraham (US→EC): {sorted(missing)}")

    def test_every_fact_is_scoped_non_eea_professional(self) -> None:
        for r in self.facts:
            ap = r.get("applies_to") or {}
            self.assertEqual(ap.get("nationality"), "non-EEA", r["fact_key"])
            self.assertEqual(ap.get("status"), "professional", r["fact_key"])


if __name__ == "__main__":
    unittest.main()

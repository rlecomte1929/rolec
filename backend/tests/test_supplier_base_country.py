"""[Stage 9 · Phase 1] Deciding where a supplier is based, and how strong that claim is.

The point of these tests is the TIER boundary. A register and a directory listing are both
"a country", and treating them as the same claim is the defect already found in the Den Norske
Advokatforening rows — a Brønnøysund organisation number sitting under a bar's name, looking
exactly like a confirmation.
"""
from __future__ import annotations

import unittest

from backend.imports.suppliers.base_country import (
    SRC_BRONNOYSUND,
    SRC_CATALOG,
    SRC_DE_CHAMBER,
    SRC_FIDI,
    SRC_FINANSTILSYNET,
    SRC_GB_REGISTER,
    SRC_SIRENE,
    SupplierEvidence,
    resolve,
    summarise,
)

_FIDI_PAGE = "SANTA FE RELOCATION - PARIS address 6, RUE RENE RAZEL SACLAY France"


def _ev(**kw) -> SupplierEvidence:
    base = dict(supplier_id="s1", name="Example", accreditations=(),
                catalog_country=None, fidi_page_text=None, membership_numbers=())
    base.update(kw)
    return SupplierEvidence(**base)


class RegistryTierTests(unittest.TestCase):
    def test_a_fidi_page_naming_one_country_resolves_it(self) -> None:
        r = resolve(_ev(accreditations=(("FIDI Global Alliance / FAIM (auditor: EY)", "u"),),
                        fidi_page_text=_FIDI_PAGE))
        self.assertEqual((r.country, r.source), ("FR", SRC_FIDI))
        self.assertTrue(r.is_registry_grade)

    def test_page_chrome_does_not_defeat_the_address(self) -> None:
        """EVERY FIDI page says "Belgium" — FIDI is headquartered in Brussels. A whole-page
        scan therefore finds two countries on every page, and an exactly-one rule resolves
        nothing: it returned 0 of 21 on the first live run."""
        page = ("FIDI Global Alliance Brussels Belgium ... address 6, RUE RENE RAZEL "
                "SACLAY France ... Certificate validity FAIM Expiry date: 2029")
        r = resolve(_ev(accreditations=(("FIDI FAIM", "u"),), fidi_page_text=page))
        self.assertEqual((r.country, r.source), ("FR", SRC_FIDI))

    def test_an_ambiguous_address_block_is_not_evidence(self) -> None:
        r = resolve(_ev(accreditations=(("FIDI FAIM", "u"),),
                        fidi_page_text="address offices in France and Germany"))
        self.assertIsNone(r.country)

    def test_a_page_with_no_address_block_is_not_evidence(self) -> None:
        r = resolve(_ev(accreditations=(("FIDI FAIM", "u"),),
                        fidi_page_text="Brussels Belgium navigation only"))
        self.assertIsNone(r.country)

    def test_raw_html_is_normalised_by_the_function_itself(self) -> None:
        """The first live run passed raw HTML straight through, so `address` matched a markup
        attribute and the window was tags: FIDI resolved 3 of 21. The function normalises its
        own input rather than trusting the caller to have done it."""
        html_page = (
            '<div class="address-block"><span>nav</span></div>'
            '<section><h2>address</h2><p>H\u00c5NDVERKSVEIEN 11 OSLO Norway</p></section>'
        )
        r = resolve(_ev(accreditations=(("FIDI FAIM", "u"),), fidi_page_text=html_page))
        self.assertEqual((r.country, r.source), ("NO", SRC_FIDI))

    def test_an_unfetched_fidi_page_falls_through_rather_than_guessing(self) -> None:
        r = resolve(_ev(accreditations=(("FIDI FAIM", "u"),), catalog_country="NO"))
        self.assertEqual((r.country, r.source), ("NO", SRC_CATALOG))
        self.assertFalse(r.is_registry_grade)

    def test_sirene_implies_france_and_captures_the_siren(self) -> None:
        r = resolve(_ev(accreditations=(("INSEE SIRENE / recherche-entreprises (FR)", "u"),),
                        membership_numbers=("525031522",)))
        self.assertEqual((r.country, r.source), ("FR", SRC_SIRENE))
        self.assertEqual(r.legal_registration_number, "525031522")

    def test_finanstilsynet_implies_norway(self) -> None:
        r = resolve(_ev(accreditations=(("Finanstilsynet (Norwegian FSA)", "u"),)))
        self.assertEqual((r.country, r.source), ("NO", SRC_FINANSTILSYNET))

    def test_a_bronnoysund_number_evidences_the_COUNTRY_even_though_not_the_bar(self) -> None:
        """The nuance that matters: the Advokatforening rows cannot evidence bar membership,
        but the org number does evidence a Norwegian company registration — which is exactly
        what a base country is."""
        r = resolve(_ev(accreditations=(("Den Norske Advokatforening", "u"),),
                        membership_numbers=("917 334 110",)))
        self.assertEqual((r.country, r.source), ("NO", SRC_BRONNOYSUND))
        self.assertEqual(r.legal_registration_number, "917334110")
        self.assertIn("not bar membership", r.reason)

    def test_german_registers_imply_germany(self) -> None:
        for body in ("BaFin (Federal Financial Supervisory Authority)",
                     "Rechtsanwaltskammer Berlin", "Hanseatische RAK Hamburg",
                     "Steuerberaterkammer Berlin", "IVD Immobilienverband Deutschland"):
            r = resolve(_ev(accreditations=((body, "u"),)))
            self.assertEqual((r.country, r.source), ("DE", SRC_DE_CHAMBER), body)

    def test_uk_registers_imply_gb_and_are_registry_grade(self) -> None:
        for body in ("Solicitors Regulation Authority (SRA)", "Financial Conduct Authority",
                     "ICAEW", "British Association of Removers", "Propertymark / NAEA",
                     "Royal Institution of Chartered Surveyors (RICS)"):
            r = resolve(_ev(accreditations=((body, "u"),)))
            self.assertEqual((r.country, r.source), ("GB", SRC_GB_REGISTER), body)
            self.assertTrue(r.is_registry_grade, body)

    def test_a_uk_register_beats_a_catalog_listing(self) -> None:
        """A GB register must win over a directory's placement, same as every other register."""
        r = resolve(_ev(accreditations=(("Financial Conduct Authority", "u"),),
                        catalog_country="SG"))
        self.assertEqual((r.country, r.source), ("GB", SRC_GB_REGISTER))


class ProxyTierTests(unittest.TestCase):
    def test_a_catalog_listing_is_labelled_as_a_proxy(self) -> None:
        r = resolve(_ev(catalog_country="NO"))
        self.assertEqual((r.country, r.source), ("NO", SRC_CATALOG))
        self.assertFalse(r.is_registry_grade)
        self.assertIn("NOT a register", r.reason)

    def test_a_register_always_beats_a_catalog_listing(self) -> None:
        """Both present, and the catalog disagrees. The register wins."""
        r = resolve(_ev(accreditations=(("Finanstilsynet (Norwegian FSA)", "u"),),
                        catalog_country="SG"))
        self.assertEqual((r.country, r.source), ("NO", SRC_FINANSTILSYNET))

    def test_the_registry_prefix_is_what_separates_the_tiers(self) -> None:
        registry = resolve(_ev(accreditations=(("Finanstilsynet", "u"),)))
        proxy = resolve(_ev(catalog_country="NO"))
        self.assertTrue(registry.source.startswith("registry:"))
        self.assertFalse(proxy.source.startswith("registry:"))


class NoEvidenceTests(unittest.TestCase):
    def test_nothing_known_leaves_null(self) -> None:
        r = resolve(_ev())
        self.assertIsNone(r.country)
        self.assertIsNone(r.source)
        self.assertFalse(r.writes)
        self.assertIn("not eligible", r.reason)

    def test_an_unrecognised_body_alone_is_not_evidence(self) -> None:
        r = resolve(_ev(accreditations=(("Some Association Nobody Modelled", "u"),)))
        self.assertIsNone(r.country)


class SummaryTests(unittest.TestCase):
    def test_the_split_is_reported_not_just_the_total(self) -> None:
        """'109 populated' alone would overstate what is known."""
        out = summarise([
            resolve(_ev(supplier_id="a", accreditations=(("Finanstilsynet", "u"),))),
            resolve(_ev(supplier_id="b", catalog_country="FR")),
            resolve(_ev(supplier_id="c")),
        ], dry_run=True)
        self.assertIn("registry-grade :   1", out)
        self.assertIn("proxy (catalog):   1", out)
        self.assertIn("left NULL      :   1", out)
        self.assertIn("DRY RUN", out)

    def test_the_proxy_line_warns_it_is_not_a_register(self) -> None:
        out = summarise([resolve(_ev(catalog_country="FR"))], dry_run=True)
        self.assertIn("not a register", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

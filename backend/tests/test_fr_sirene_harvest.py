"""[AIQ-1827] The French open-register harvest, and what its rows are allowed to claim.

The load-bearing tests here are the ones that stop a tier-2 entity record from being dressed
up as a professional accreditation — the exact defect found in the Den Norske Advokatforening
rows, where a Brønnøysund organisation number sat under a bar's name.
"""
from __future__ import annotations

import re
import unittest

from backend.app.services.accreditation_hardening import (
    ACTION_KEEP_CLAIMED,
    AccreditationRow,
    Capability,
    LookupResult,
    decide,
    policy_for_body,
)
from backend.app.services.registry_sources import ingestable_sources, sources_for
from backend.app.services.vendor_harvester import HarvestRejected, validate
from backend.imports.suppliers.fr_sirene import (
    NAF_BY_CATEGORY,
    PARIS_POSTCODES,
    SOURCE_NAME,
    harvest,
    source_for,
    to_candidate,
)


def _result(**kw):
    base = {
        "siren": "525031522",
        "nom_complet": "CABINET EXEMPLE AVOCATS",
        "nom_raison_sociale": "CABINET EXEMPLE",
        "activite_principale": "69.10Z",
        "tranche_effectif_salarie": "32",
        "nombre_etablissements_ouverts": 4,
        "siege": {"libelle_commune": "PARIS 8", "code_postal": "75008"},
    }
    base.update(kw)
    return base


class CatalogueTests(unittest.TestCase):
    def test_the_source_is_declared_for_all_four_categories(self) -> None:
        for cat in NAF_BY_CATEGORY:
            self.assertEqual(source_for(cat).name, SOURCE_NAME)

    def test_it_is_tier_2_not_tier_1(self) -> None:
        """The whole honesty argument rests on this. A registration is not an accreditation."""
        self.assertEqual(source_for("legal_admin").tier, 2)

    def test_banks_are_not_served_by_it(self) -> None:
        self.assertNotIn(SOURCE_NAME, [s.name for s in sources_for("FR-NO", "banks")])

    def test_it_does_not_leak_into_fr_de(self) -> None:
        """FR-DE housing_agencies must stay empty — recon proved IVD and FNAIM unusable, and
        a French entity register does not make German housing coverage real."""
        self.assertEqual([s.name for s in ingestable_sources("FR-DE", "housing_agencies")], [])

    def test_the_evidence_url_pattern_accepts_only_a_single_entity_page(self) -> None:
        pat = re.compile(source_for("movers").entry_url_pattern)
        self.assertTrue(pat.match("https://annuaire-entreprises.data.gouv.fr/entreprise/525031522"))
        # the search page evidences nobody
        self.assertFalse(pat.match("https://recherche-entreprises.api.gouv.fr/search?q=avocat"))
        self.assertFalse(pat.match("https://annuaire-entreprises.data.gouv.fr/entreprise/abc"))


class CandidateShapeTests(unittest.TestCase):
    def test_a_result_becomes_a_valid_candidate(self) -> None:
        cand = to_candidate(_result(), "legal_admin")
        self.assertIsNotNone(cand)
        validate(cand)  # must not raise
        self.assertEqual(cand.accreditation_number, "525031522")
        self.assertEqual(cand.country_code, "FR")
        self.assertEqual(cand.corridor, "FR-NO")

    def test_the_body_names_the_register_that_answered_not_a_profession(self) -> None:
        """`body` must never say CNB / carte T / Ordre des Experts-Comptables — SIRENE did
        not evidence any of those."""
        cand = to_candidate(_result(), "legal_admin")
        self.assertEqual(cand.accreditation_body, SOURCE_NAME)
        for forbidden in ("CNB", "avocat", "carte T", "Experts-Comptables", "Ordre"):
            self.assertNotIn(forbidden.lower(), cand.accreditation_body.lower())

    def test_no_city_is_claimed(self) -> None:
        """A registration postcode is not a coverage claim. Writing 'Paris' here would make
        a country-scoped capability contradict itself, which is a live defect on 4 NO rows."""
        self.assertIsNone(to_candidate(_result(), "movers").city)

    def test_the_evidence_url_is_per_entity(self) -> None:
        cand = to_candidate(_result(), "movers")
        self.assertEqual(
            cand.source_url,
            "https://annuaire-entreprises.data.gouv.fr/entreprise/525031522",
        )

    def test_the_note_states_the_limit_of_the_evidence(self) -> None:
        note = to_candidate(_result(), "tax_finance").notes
        self.assertIn("NOT a professional accreditation", note)

    def test_a_malformed_siren_is_dropped(self) -> None:
        for bad in ("", "12345", "abcdefghi", None):
            self.assertIsNone(to_candidate(_result(siren=bad), "movers"))

    def test_a_nameless_result_is_dropped(self) -> None:
        self.assertIsNone(
            to_candidate(_result(nom_complet="", nom_raison_sociale=""), "movers")
        )


class HonestyTests(unittest.TestCase):
    def test_this_body_can_never_be_auto_verified(self) -> None:
        """No BODY_POLICIES rule exists for it, deliberately. Even a page naming the entity
        must leave the row claimed — confirming a company exists is not confirming an
        accreditation."""
        self.assertIsNone(policy_for_body(SOURCE_NAME))
        row = AccreditationRow(
            accreditation_id="a1", supplier_id="s1",
            supplier_name="Cabinet Exemple Avocats", body=SOURCE_NAME, status="claimed",
            evidence_url="https://annuaire-entreprises.data.gouv.fr/entreprise/525031522",
            capabilities=(Capability(service_category="legal_admin", country_code="FR"),),
        )
        d = decide(row, LookupResult(ok=True, text="CABINET EXEMPLE AVOCATS"))
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)
        self.assertEqual(d.status, "claimed")
        self.assertFalse(d.writes)

    def test_a_tier_3_source_would_still_be_rejected(self) -> None:
        """Guard on validate()'s tier rule, so nobody 'fixes' a thin harvest by demoting
        the source to the provider's own website."""
        cand = to_candidate(_result(), "movers")
        thin = type(cand)(**{**cand.__dict__, "source": sources_for("FR-NO", "movers")[-1]})
        if thin.source.tier == 3:
            with self.assertRaises(HarvestRejected):
                validate(thin)


class SelectionTests(unittest.TestCase):
    def test_paris_postcodes_are_the_20_arrondissements(self) -> None:
        """`departement=75` returned Courbevoie, Mitry-Mory and Montbonnot-Saint-Martin, so
        the filter is postcode-based on purpose."""
        self.assertEqual(len(PARIS_POSTCODES), 20)
        self.assertEqual(PARIS_POSTCODES[0], "75001")
        self.assertEqual(PARIS_POSTCODES[-1], "75020")

    def test_results_are_deduped_by_siren_across_postcodes(self) -> None:
        """The same company can answer for several postcodes; it must appear once."""
        def fake(url: str):
            return {"results": [_result()]}

        got = harvest(["movers"], per_category=10, postcodes=("75001", "75002"), fetcher=fake)
        self.assertEqual(len(got["movers"]), 1)

    def test_bigger_firms_rank_first(self) -> None:
        def fake(url: str):
            return {"results": [
                _result(siren="111111111", nom_complet="TINY SARL",
                        tranche_effectif_salarie="01", nombre_etablissements_ouverts=1),
                _result(siren="222222222", nom_complet="BIG GROUP",
                        tranche_effectif_salarie="42", nombre_etablissements_ouverts=30),
            ]}

        got = harvest(["movers"], per_category=2, postcodes=("75001",), fetcher=fake)
        self.assertEqual([c.name for c in got["movers"]], ["BIG GROUP", "TINY SARL"])

    def test_an_unknown_headcount_band_sorts_last_and_does_not_crash(self) -> None:
        def fake(url: str):
            return {"results": [
                _result(siren="111111111", nom_complet="UNKNOWN SIZE",
                        tranche_effectif_salarie="NN", nombre_etablissements_ouverts=1),
                _result(siren="222222222", nom_complet="KNOWN SIZE",
                        tranche_effectif_salarie="11", nombre_etablissements_ouverts=1),
            ]}

        got = harvest(["movers"], per_category=2, postcodes=("75001",), fetcher=fake)
        self.assertEqual([c.name for c in got["movers"]], ["KNOWN SIZE", "UNKNOWN SIZE"])

    def test_a_dead_postcode_does_not_abort_the_harvest(self) -> None:
        calls = {"n": 0}

        def flaky(url: str):
            calls["n"] += 1
            if "75001" in url:
                raise TimeoutError("boom")
            return {"results": [_result()]}

        got = harvest(["movers"], per_category=5, postcodes=("75001", "75002"), fetcher=flaky)
        self.assertEqual(len(got["movers"]), 1)
        self.assertEqual(calls["n"], 2)

    def test_a_category_that_yields_nothing_is_reported_not_omitted(self) -> None:
        got = harvest(["movers"], postcodes=("75001",), fetcher=lambda url: {"results": []})
        self.assertIn("movers", got)
        self.assertEqual(got["movers"], [])

    def test_per_category_caps_the_pool(self) -> None:
        def fake(url: str):
            return {"results": [
                _result(siren=f"1000000{i:02d}", nom_complet=f"FIRM {i}") for i in range(10)
            ]}

        got = harvest(["movers"], per_category=3, postcodes=("75001",), fetcher=fake)
        self.assertEqual(len(got["movers"]), 3)


class PromoteScopingTests(unittest.TestCase):
    """[AIQ-1827] Unscoped promotion sweeps every abandoned candidate in the table.

    Measured 2026-08-13: `vendor_candidates` held 233 unpromoted rows with `corridor` NULL
    from an older import, so a 16-row French harvest previewed as "promote: 235 suppliers".
    """

    def test_an_empty_run_id_list_promotes_nothing(self) -> None:
        """The guard that matters: an empty scope must mean NOTHING, never EVERYTHING."""
        from backend.imports.suppliers.executor import promote

        class _Boom:
            def execute(self, *a, **kw):
                raise AssertionError("promote() queried the table despite an empty scope")

            def query(self, *a, **kw):
                raise AssertionError("promote() queried the table despite an empty scope")

        self.assertEqual(promote(_Boom(), dry_run=True, run_ids=[]), (0, 0, []))

    def test_scoped_and_unscoped_use_different_queries(self) -> None:
        from backend.imports.suppliers import executor

        scoped = str(executor._PROMOTABLE_BY_RUN)
        unscoped = str(executor._PROMOTABLE)
        self.assertIn("run_id", scoped)
        self.assertNotIn("run_id", unscoped)

    def test_the_default_is_still_unscoped_for_the_existing_caller(self) -> None:
        """scripts/import_supplier_candidates.py calls promote(session, dry_run=...) with no
        run_ids and must keep its old behaviour."""
        import inspect

        from backend.imports.suppliers.executor import promote

        self.assertIsNone(inspect.signature(promote).parameters["run_ids"].default)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

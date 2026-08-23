"""The promoter must read both batch vocabularies and refuse to invent a domain.

Two batch shapes exist in docs/imports/ and neither is going away: ES→IE nests the entity,
NO→FR is flat (`entity_topic_key`) — the shape `backend/imports/otto/parsers.read_jsonl`
actually requires. A promoter that understands only one makes the other unpromotable for a
reason that has nothing to do with the facts.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "promote_requirement_facts",
    Path(__file__).resolve().parents[2] / "scripts" / "promote_requirement_facts.py",
)
prf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prf)


class ReadEntityTests(unittest.TestCase):
    def test_reads_the_nested_shape(self):
        ent = prf.read_entity({
            "destination_country": "IE",
            "entity": {"topic_key": "ES-IE:thirdcountry:ppsn", "title": "PPSN",
                       "domain_area": "social_security"},
        })
        self.assertEqual(ent["topic_key"], "ES-IE:thirdcountry:ppsn")
        self.assertEqual(ent["domain_area"], "social_security")

    def test_reads_the_flat_shape(self):
        ent = prf.read_entity({
            "destination_country": "FR",
            "entity_topic_key": "french_tax_domicile_eea",
            "entity_title": "French tax domicile",
        })
        self.assertEqual(ent["topic_key"], "french_tax_domicile_eea")
        self.assertEqual(ent["title"], "French tax domicile")

    def test_a_record_with_neither_is_refused(self):
        with self.assertRaises(SystemExit):
            prf.read_entity({"destination_country": "FR", "fact_key": "x"})

    def test_the_title_falls_back_to_the_topic_key(self):
        self.assertEqual(
            prf.read_entity({"destination_country": "FR",
                             "entity_topic_key": "a1_posted_worker_eea"})["title"],
            "a1_posted_worker_eea")


class DeriveDomainAreaTests(unittest.TestCase):
    """Derivation from a delivered field is allowed; inventing a classification is not."""

    def test_an_explicit_domain_always_wins(self):
        self.assertEqual(prf.derive_domain_area("french_tax_domicile_eea", "healthcare"),
                         "healthcare")

    def test_derives_only_what_the_topic_key_states(self):
        self.assertEqual(prf.derive_domain_area("french_tax_domicile_eea"), "tax")
        self.assertEqual(prf.derive_domain_area("a1_posted_worker_eea"), "social_security")
        self.assertEqual(prf.derive_domain_area("french_social_security_number_eea"),
                         "social_security")
        self.assertEqual(prf.derive_domain_area("eea_residence_card"), "immigration")
        self.assertEqual(prf.derive_domain_area("work_authorization_non_eea"), "immigration")
        self.assertEqual(prf.derive_domain_area("entry_no_visa_eea"), "immigration")

    def test_a_key_that_states_nothing_is_not_guessed(self):
        """`other` means "the batch did not classify it", not "we decided it is misc".

        `eea_unemployment_residence_right` is the real case: it names unemployment AND a
        residence right, and a reader could argue either social_security or immigration. The
        key does not settle it, so neither does this function — guessing would put an invented
        classification on a served fact.
        """
        self.assertEqual(prf.derive_domain_area("eea_unemployment_residence_right"), "other")
        self.assertEqual(prf.derive_domain_area("something_entirely_opaque"), "other")

    def test_every_derived_value_satisfies_the_column_constraint(self):
        allowed = {"immigration", "registration", "tax", "social_security", "healthcare",
                   "housing", "other", "vehicle", "vehicle_import", "domestic_move",
                   "financial", "employer_compliance", "pet"}
        for key in ("french_tax_domicile_eea", "a1_posted_worker_eea", "eea_residence_card",
                    "entry_no_visa_eea", "opaque_key", "health_entitlements",
                    "isd_irp_registration"):
            self.assertIn(prf.derive_domain_area(key), allowed, key)


if __name__ == "__main__":
    unittest.main()

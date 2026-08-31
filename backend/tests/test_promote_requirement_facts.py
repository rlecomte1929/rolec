"""The promoter must read both batch vocabularies and refuse to invent a domain.

Two batch shapes exist in docs/imports/ and neither is going away: ES→IE nests the entity,
NO→FR is flat (`entity_topic_key`) — the shape `backend/imports/otto/parsers.read_jsonl`
actually requires. A promoter that understands only one makes the other unpromotable for a
reason that has nothing to do with the facts.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "promote_requirement_facts",
    REPO / "scripts" / "promote_requirement_facts.py",
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


class GeneratedSqlInvariantsTests(unittest.TestCase):
    """The four promises AIQ-2148 turns on, pinned to CI against the real ES→IE batch.

    `scripts/promote_requirement_facts.py` makes them by construction — INSERT-only,
    `status='pending'`, `evidence_verified` NULL, and a re-run that inserts nothing — and the
    dry-run doc (`docs/promotions/es-ie-thirdcountry-2026-08-22-dry-run.md`) asserts them once,
    by hand, inside a `BEGIN … ROLLBACK` probe against production. That probe cannot run in CI
    and does not re-run on a code change. These tests do, so a later edit to the emitter cannot
    quietly reopen the gate that keeps an unreviewed corridor fact away from a mover.

    The generator is invoked exactly as an operator invokes it — as a subprocess emitting SQL to
    stdout, no database — and every assertion targets a specific SQL keyword form rather than a
    bare word, so a government page's own prose embedded in `text_content` cannot trip it.
    """

    BATCH = REPO / "docs/imports/es-ie-thirdcountry-requirements-2026-08-22"

    @classmethod
    def setUpClass(cls):
        if not cls.BATCH.exists():
            raise unittest.SkipTest(f"batch fixture missing: {cls.BATCH}")
        cls.manifest = json.loads((cls.BATCH / "manifest.json").read_text())
        cls.sql = cls._emit()
        cls.sql_again = cls._emit()

    @classmethod
    def _emit(cls) -> str:
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "promote_requirement_facts.py"), str(cls.BATCH)],
            capture_output=True, text=True, cwd=str(REPO),
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"generator refused the batch (exit {proc.returncode}):\n{proc.stderr}")
        return proc.stdout

    def test_reconciles_against_the_manifest(self):
        """One INSERT per fact, entity and source document the manifest declares."""
        counts = self.manifest["counts"]
        self.assertEqual(self.sql.count("INSERT INTO public.requirement_facts"),
                         counts["records_total"])
        self.assertEqual(self.sql.count("INSERT INTO public.requirement_entities"),
                         counts["distinct_topics"])
        self.assertEqual(self.sql.count("INSERT INTO public.knowledge_docs"),
                         counts["distinct_source_urls"])

    def test_every_fact_is_pending_and_unverified(self):
        """`…, 'pending', NULL` is the fact template's tail — the two-column pair the serving
        predicate (`status='approved' AND COALESCE(evidence_verified, TRUE)`) cannot satisfy.
        One per fact, and the batch writes nothing `'approved'`, so promotion serves no one."""
        self.assertEqual(self.sql.count("'pending', NULL"),
                         self.manifest["counts"]["records_total"])
        self.assertNotIn("'approved'", self.sql)

    def test_insert_only(self):
        """No UPDATE is issued anywhere — the 25 already-reviewed IE rows cannot be touched —
        and idempotency does not lean on ON CONFLICT (the table has no unique key to match)."""
        self.assertNotIn("UPDATE public.", self.sql)
        self.assertNotIn("DO UPDATE", self.sql)
        self.assertNotIn("ON CONFLICT", self.sql)

    def test_every_insert_is_not_exists_guarded(self):
        """Each INSERT carries its own WHERE NOT EXISTS on a deterministic uuid5, so a re-apply
        inserts 0 duplicate rows despite the table having only its primary key."""
        self.assertEqual(self.sql.count("INSERT INTO public."),
                         self.sql.count("WHERE NOT EXISTS"))

    def test_two_runs_are_byte_identical(self):
        """The only ids are uuid5 over natural keys and the only timestamp is SQL now(); nothing
        is nondeterministic, so a second emission is the same bytes — what a safe re-apply needs."""
        self.assertEqual(self.sql, self.sql_again)


if __name__ == "__main__":
    unittest.main()

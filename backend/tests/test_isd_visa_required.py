"""The lookup the CSEP pathway declares, and the artifact behind it.

`corridors/ES_IE/pathways/CSEP_2026/v1.yaml` declares
``visa_required_nationality: EXTERNAL_LOOKUP -> isd_visa_required.{nationality_iso}``. This
pins both halves: that the data file stays what its manifest says it is, and that the module
answers three-valued rather than guessing.

The integrity half exists because `scripts/check_otto_batches.py` — the usual batch gate —
is NOT on main (it lives in unmerged PR #1971), and is a fact-stream gate that does not model
a lookup table anyway. A committed artifact nobody re-hashes is a file that can drift silently.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from backend.app.services import isd_visa_required as lookup

_BATCH = Path(__file__).resolve().parents[2] / "docs" / "imports" / "ie-isd-visa-required-2026-08-22"
_ARTIFACT = _BATCH / "isd_visa_required.json"
_MANIFEST = _BATCH / "manifest.json"


class ArtifactIntegrity(unittest.TestCase):
    def test_sha256_matches_the_manifest(self):
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        digest = hashlib.sha256(_ARTIFACT.read_bytes()).hexdigest()
        self.assertEqual(
            digest, manifest["sha256"],
            "the artifact changed without its manifest — re-hash it, and say why in the commit",
        )

    def test_counts_reconcile(self):
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        data = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(len(data["visa_free_nationalities"]), manifest["visa_free_nationality_count"])
        self.assertEqual(len(data["structural_exemptions"]), manifest["structural_exemption_count"])

    def test_every_exempt_row_has_an_iso_and_a_name(self):
        data = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        for row in data["visa_free_nationalities"]:
            self.assertRegex(row["iso"], r"^[A-Z]{2}$", f"bad iso in {row!r}")
            self.assertTrue(row["name"].strip(), f"missing name in {row!r}")

    def test_isos_are_unique(self):
        data = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
        isos = [r["iso"] for r in data["visa_free_nationalities"]]
        self.assertEqual(len(isos), len(set(isos)), "duplicate ISO in the exempt table")

    def test_the_manifest_names_no_target_table(self):
        """A lookup is not a fact stream. Naming a target table is how the ES->IE batch came to
        point at `requirement_facts`, which has no fact_uid column and two NOT NULL uuid FKs."""
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        self.assertIsNone(manifest["target_table"])


class VisaRequired(unittest.TestCase):
    def test_andreas_household(self):
        """The case this was built for: Venezuelan principal, Macedonian spouse. Both need a visa."""
        self.assertIs(lookup.visa_required("Venezuela"), True)
        self.assertIs(lookup.visa_required("VE"), True)
        self.assertIs(lookup.visa_required("North Macedonia"), True)
        self.assertIs(lookup.visa_required("MK"), True)

    def test_exempt_nationalities_resolve_by_name_not_only_by_code(self):
        """`nationality_class._COUNTRY_NAME` holds almost none of these, so without the
        artifact's own name index the lookup would answer None for most of its own table."""
        for name in ("Brazil", "Japan", "Uruguay", "United States of America", "Vatican City"):
            self.assertIs(lookup.visa_required(name), False, name)

    def test_free_movement_nationals_need_no_visa(self):
        for name in ("Spain", "France", "Ireland", "Switzerland", "United Kingdom"):
            self.assertIs(lookup.visa_required(name), False, name)

    def test_an_unresolvable_nationality_is_none_never_true_and_never_false(self):
        """Production holds 'f', 'asdas' and '1212' in this free-text field. False would tell a
        visa-required national they need nothing; True would invent a requirement from a typo."""
        for junk in ("Wakanda", "asdas", "1212", "f", "", None):
            self.assertIsNone(lookup.visa_required(junk), repr(junk))

    def test_the_unlisted_but_real_country_is_visa_required(self):
        """Absence from the exempt table IS the answer, once the input is a real ISO code."""
        self.assertIs(lookup.visa_required("CN"), True)
        self.assertIs(lookup.visa_required("NG"), True)


class Preclearance(unittest.TestCase):
    def test_a_csep_spouse_from_a_visa_exempt_country_still_needs_preclearance(self):
        self.assertIs(
            lookup.preclearance_required("US", relationship="csep_holder_spouse_or_partner"), True
        )

    def test_swiss_and_uk_are_excluded_by_the_rule_itself(self):
        for iso in ("CH", "GB"):
            self.assertIs(
                lookup.preclearance_required(iso, relationship="csep_holder_spouse_or_partner"),
                False, iso,
            )

    def test_an_unknown_relationship_is_none_because_the_rule_turns_on_the_relationship(self):
        self.assertIsNone(lookup.preclearance_required("US", relationship=None))

    def test_an_unrelated_relationship_does_not_trigger_it(self):
        self.assertIs(lookup.preclearance_required("US", relationship="colleague"), False)


class Exemptions(unittest.TestCase):
    def test_the_two_exemptions_an_iso_code_cannot_settle_are_reported(self):
        keys = {e["key"] for e in lookup.exemptions_not_resolvable_from_nationality()}
        self.assertEqual(keys, {"eea_family_member_residence_card", "uk_short_stay_visa_waiver"})

    def test_each_carries_a_verbatim_quote(self):
        for e in lookup.exemptions_not_resolvable_from_nationality():
            self.assertTrue(e["quote"].strip(), e["key"])

    def test_source_is_carried_for_anything_rendered_to_a_person(self):
        src = lookup.source()
        self.assertTrue(src["url"].startswith("https://"))
        self.assertEqual(src["verification_status"], "representative")


if __name__ == "__main__":
    unittest.main()

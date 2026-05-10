"""Guards: section refs (2.1) are provenance, not amounts; durations and currency caps preserved."""
from __future__ import annotations

import os
import sys
import unittest
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_normalization import normalize_clauses_to_objects
from backend.services.policy_source_provenance import (
    build_source_provenance,
    filter_candidate_numeric_values,
    looks_like_dotted_section_number,
    primary_section_reference_from_hints,
    resolve_section_reference,
    scrub_amount_if_section_reference,
    should_exclude_numeric_as_section_reference,
    strip_section_reference_tokens_for_display,
)


class PolicySourceProvenanceTests(unittest.TestCase):
    def test_2_1_preserved_as_source_not_amount(self) -> None:
        hints = {"summary_row_candidate": {"section_reference": "2.1"}}
        self.assertEqual(resolve_section_reference(hints, "Housing cap EUR 5000"), "2.1")
        self.assertTrue(should_exclude_numeric_as_section_reference(2.1, "Policy section 2.1 applies"))
        self.assertIsNone(scrub_amount_if_section_reference(2.1, "See 2.1 for details", hints))

    def test_30_days_not_section_ref(self) -> None:
        self.assertFalse(looks_like_dotted_section_number(30.0))
        self.assertFalse(should_exclude_numeric_as_section_reference(30, "Up to 30 days temporary housing"))

    def test_eur_5000_remains_amount(self) -> None:
        self.assertFalse(should_exclude_numeric_as_section_reference(5000, "EUR 5000 cap for housing"))
        nums = filter_candidate_numeric_values([2.1, 5000.0], "EUR 5000 per policy 2.1")
        self.assertIn(5000.0, nums)
        self.assertNotIn(2.1, nums)

    def test_heading_or_ref_not_value_payload(self) -> None:
        """Dotted section-like number without amount context is excluded from hint nums."""
        nums = filter_candidate_numeric_values([8.3], "8.3")
        self.assertEqual(nums, [])

    def test_strip_display_trailing_ref(self) -> None:
        s = strip_section_reference_tokens_for_display("Temporary housing up to 90 days 6.5")
        self.assertNotIn("6.5", s)
        self.assertIn("90 days", s)

    def test_build_provenance_shape(self) -> None:
        p = build_source_provenance(
            document_id="doc-1",
            page_start=2,
            page_end=2,
            section_ref="3.7",
            source_label="Housing",
            source_excerpt="EUR 4000 cap",
            clause_id="c1",
        )
        self.assertEqual(p["schema"], "policy_source_v1")
        self.assertEqual(p["section_ref"], "3.7")
        self.assertEqual(p["document_id"], "doc-1")

    def test_normalize_benefit_metadata_contains_provenance(self) -> None:
        cid = str(uuid.uuid4())
        clauses = [
            {
                "id": cid,
                "clause_type": "benefit",
                "raw_text": "Temporary housing allowance EUR 5000 maximum (policy ref 8.3)",
                "normalized_hint_json": {"candidate_currency": "EUR", "candidate_numeric_values": [5000.0, 8.3]},
                "section_label": "Housing",
                "confidence": 0.9,
            }
        ]
        out = normalize_clauses_to_objects(clauses, "doc-prov")
        self.assertEqual(len(out["benefit_rules"]), 1)
        br = out["benefit_rules"][0]
        self.assertEqual(br.get("amount_value"), 5000.0)
        meta = br.get("metadata_json") or {}
        sp = meta.get("source_provenance") or {}
        self.assertEqual(sp.get("section_ref"), "8.3")
        self.assertNotIn("8.3", br.get("description") or "")

    def test_primary_from_metadata_roundtrip(self) -> None:
        hints = {"source_provenance": {"section_ref": "6.5"}}
        self.assertEqual(primary_section_reference_from_hints(hints), "6.5")


if __name__ == "__main__":
    unittest.main()

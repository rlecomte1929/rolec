"""Canonical LTA key matcher: disambiguation and confusion-pair regression tests."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_canonical_key_matcher import (
    resolve_primary_canonical_lta_key,
    score_canonical_lta_keys_for_debug,
)
from backend.services.policy_row_to_template_mapper import map_single_row_candidate
from backend.services.policy_summary_row_parser import PolicyRowCandidate


def _rc(
    summary: str,
    *,
    label: str | None = None,
    section: str | None = None,
) -> PolicyRowCandidate:
    return PolicyRowCandidate(
        row_id="t1",
        source_document_id="d1",
        page_number=1,
        section_context=section,
        component_label=label,
        summary_text=summary,
        section_reference="1",
    )


class CanonicalKeyMatcherConfusionTests(unittest.TestCase):
    def test_host_housing_vs_temporary_living_explicit_labels(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Host housing",
                "Capped rent support in host location.",
                "Housing and accommodation",
            ),
            "host_housing",
        )
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Temporary accommodation",
                "Hotel or serviced apartment up to 30 nights on arrival.",
                "Housing and accommodation",
            ),
            "temporary_living_outbound",
        )

    def test_child_education_vs_language_training(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Language training",
                "Five weeks of local language course for assignee.",
                "Pre-departure support",
            ),
            "language_training",
        )
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Schooling",
                "International school fees and tuition reimbursement for dependents.",
                "Family support",
            ),
            "child_education",
        )
        # Language school without tuition/fees → not child_education
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Benefits",
                "Enrollment at a language school for the assignee only.",
                "Education",
            ),
            "language_training",
        )

    def test_school_search_distinct(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "School search",
                "Assistance finding a school placement in host city.",
                "Family support",
            ),
            "school_search",
        )

    def test_spouse_support_vs_family_housing(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Partner career",
                "Dual career coaching and partner support allowance.",
                "Family support",
            ),
            "spouse_support",
        )
        k = resolve_primary_canonical_lta_key(
            "Spouse support",
            "No mention of rent, lease, or accommodation.",
            "Family support",
        )
        self.assertEqual(k, "spouse_support")

    def test_transportation_vs_housing_section_context(self) -> None:
        """Explicit transport label must not collapse into host housing under a housing-ish section."""
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Local transportation",
                "Company car and driving licence support in host country.",
                "Housing and local benefits",
            ),
            "host_transportation",
        )

    def test_tax_equalization_vs_relocation_allowance(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Tax",
                "Hypothetical tax and tax equalization for long-term assignees.",
                "Compensation and payroll",
            ),
            "tax_equalization",
        )
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Mobility benefit",
                "Relocation lump sum paid on start date.",
                "Move logistics",
            ),
            "relocation_allowance",
        )

    def test_tax_return_vs_equalization(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Tax support",
                "Tax return preparation and filing support for assignee.",
                "Compensation and payroll",
            ),
            "tax_return_support",
        )

    def test_temporary_living_return_signals(self) -> None:
        self.assertEqual(
            resolve_primary_canonical_lta_key(
                "Bridge housing",
                "Temporary accommodation upon return at end of assignment.",
                "Repatriation",
            ),
            "temporary_living_return",
        )

    def test_compensation_heading_does_not_map_host_housing(self) -> None:
        k = resolve_primary_canonical_lta_key(
            "Compensation",
            "Overview of host and home payroll split; no housing detail in this row.",
            "Compensation and payroll",
        )
        self.assertNotEqual(k, "host_housing")

    def test_language_training_not_schooling_when_only_school_word(self) -> None:
        scores = score_canonical_lta_keys_for_debug(
            "Assignee benefits",
            "Short assignment language immersion program for employee.",
            "Training",
        )
        self.assertGreater(
            scores.get("language_training", 0),
            scores.get("child_education", 0),
        )

    def test_map_row_end_to_end_transport(self) -> None:
        m = map_single_row_candidate(
            _rc(
                "Car allowance and driving test fees reimbursed.",
                label="Transportation",
                section="Housing and mobility",
            )
        )
        self.assertEqual(m.primary_canonical_key, "host_transportation")


if __name__ == "__main__":
    unittest.main()

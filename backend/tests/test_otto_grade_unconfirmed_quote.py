"""`grade()` must not badge a row `auto_accepted` on a quote nobody re-checked.

`auto_accepted` is awarded for an official publisher plus a quotable line of evidence. A
research batch can satisfy both while having captured the quote and never re-read it against
the source page — it says so itself, with `quote_verbatim_confirmed: false`. Until this guard
existed the grader had no vocabulary for that flag, so an unchecked quote scored exactly like a
checked one, including on rows flagged `needs_lawyer_review`.

Measured on `ve-ie-entry-family-2026-08-20` (AIQ-2027), 9 rows all carrying the flag as false:

    new | auto_accepted | 4 | 1 counsel-flagged   <-- dependant_join_family_d_visa_required
    new | needs_review  | 5 | 3 counsel-flagged

The backward-compatibility tests below matter as much as the fix. B3 and every earlier batch
OMIT the key; re-grading them would invalidate reviews already done, so an absent key must
behave exactly as it did before. That is why the guard tests `is False` rather than falsiness —
`None` and a missing key are not the same claim as an explicit "not confirmed".

DB-free.
"""
from __future__ import annotations

import unittest

from backend.imports.otto.parsers import (
    TIER_AUTO,
    TIER_REVIEW,
    FactRow,
    classify_source,
    grade,
)

OFFICIAL_URL = "https://www.irishimmigration.ie/registering-your-immigration-permission/"


def graded(applies_to, *, evidence_quote: str | None = "a real quote from the page") -> FactRow:
    """An otherwise auto-acceptable row: official publisher, real quote, known confidence."""
    row = FactRow(
        destination_country="IE",
        entity_topic_key="dependant_join_family_d_visa_required",
        fact_key="es_ie_dependant_join_family_d_visa_required",
        fact_text="Dependants need their own Join Family 'D' visa.",
        source_url=OFFICIAL_URL,
        batch_id="test-batch",
        entity_title="Ireland — dependant join family d visa required",
        applies_to=applies_to,
        evidence_quote=evidence_quote,
        confidence="medium",
    )
    row.source_class = classify_source(row.source_url)
    return grade(row)


class TestUnconfirmedQuoteIsDowngraded(unittest.TestCase):
    def test_explicit_false_downgrades_to_needs_review(self) -> None:
        row = graded({"nationality": "non-EEA", "quote_verbatim_confirmed": False})
        self.assertEqual(row.accuracy_tier, TIER_REVIEW)

    def test_the_reason_is_recorded_for_the_reviewer(self) -> None:
        """A downgrade with no stated reason is indistinguishable from a bug."""
        row = graded({"quote_verbatim_confirmed": False})
        self.assertTrue(
            any("verbatim" in d for d in row.downgrades),
            f"no verbatim reason in downgrades: {row.downgrades}",
        )

    def test_a_counsel_flagged_row_is_never_auto_accepted(self) -> None:
        """The case this guard exists for: AIQ-2027's dependant-visa row."""
        row = graded({"needs_lawyer_review": True, "quote_verbatim_confirmed": False})
        self.assertNotEqual(row.accuracy_tier, TIER_AUTO)


class TestBackwardCompatibility(unittest.TestCase):
    """Absent means "not claimed", not "not confirmed". B3 and earlier batches omit the key."""

    def test_absent_key_still_auto_accepts(self) -> None:
        self.assertEqual(graded({"nationality": "non-EEA"}).accuracy_tier, TIER_AUTO)

    def test_absent_applies_to_entirely_still_auto_accepts(self) -> None:
        self.assertEqual(graded(None).accuracy_tier, TIER_AUTO)

    def test_explicit_true_still_auto_accepts(self) -> None:
        self.assertEqual(graded({"quote_verbatim_confirmed": True}).accuracy_tier, TIER_AUTO)

    def test_none_is_not_treated_as_false(self) -> None:
        """`None` is an absent claim. Truthiness testing would wrongly downgrade it."""
        self.assertEqual(graded({"quote_verbatim_confirmed": None}).accuracy_tier, TIER_AUTO)

    def test_the_absent_key_case_records_no_downgrade_at_all(self) -> None:
        self.assertEqual(graded({"nationality": "non-EEA"}).downgrades, [])


class TestGuardDoesNotMaskOtherDowngrades(unittest.TestCase):
    def test_a_missing_quote_is_still_its_own_downgrade(self) -> None:
        row = graded({"quote_verbatim_confirmed": False}, evidence_quote=None)
        self.assertEqual(row.accuracy_tier, TIER_REVIEW)
        self.assertTrue(any("no evidence_quote" in d for d in row.downgrades))
        self.assertTrue(any("verbatim" in d for d in row.downgrades))
        self.assertEqual(len(row.downgrades), 2, row.downgrades)


if __name__ == "__main__":
    unittest.main()

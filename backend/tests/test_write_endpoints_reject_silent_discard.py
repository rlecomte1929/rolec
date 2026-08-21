"""
[AIQ-1885 / T18-11] Write endpoints returned 200 for payloads they discarded.

"200 means received, not stored." Two endpoints accepted a body they could not
use, returned success with a fresh timestamp, and dropped the contents — so a
caller had no way to tell success from silent loss, and the failure surfaced much
later as an unexplained empty state. This cost a full campaign to characterise.

Reproduced in prod 2026-08-20:

  PUT /api/employee/cases/{id}/relocation-profile  {"totally":"unrecognised"}
      -> 200 {"profile": {all six fields null}, "completion_pct": 0,
              "last_updated_at": null}

and, per the T18 campaign, PATCH .../intake-draft with a nested camelCase draft
-> 200 + a fresh intakeUpdatedAt, stored verbatim, echoed back by GET, and then
rejected hours later by submit with all six relocationBasics fields "missing"
while plainly present in the stored draft.

Enforced rather than warn-and-logged, per the decision on the ticket.

The hard constraint is criterion 4 — no regression in the wizard's normal flat
snake_case path. The wizard autosaves on a ~700ms debounce as the employee types,
so a draft holding one key, or none at all on the first save, is NORMAL. The guard
therefore refuses only a draft that carries content and not one convertible key:
the difference between "partially filled in" and "wrong shape entirely".
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

import pydantic

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.intake_draft_to_case_draft import (  # noqa: E402
    RECOGNISED_INTAKE_KEYS,
    intake_draft_to_case_draft,
    unreadable_draft_reason,
)
from backend.app.routers.relocation_profile import RelocationProfilePayload  # noqa: E402


class WizardPathUnaffectedTests(unittest.TestCase):
    """Criterion 4. These must keep returning None (i.e. keep saving)."""

    def test_empty_first_autosave_is_accepted(self) -> None:
        self.assertIsNone(unreadable_draft_reason({}))
        self.assertIsNone(unreadable_draft_reason(None))

    def test_a_single_key_partial_draft_is_accepted(self) -> None:
        """The employee has typed one field. This is the common case."""
        self.assertIsNone(unreadable_draft_reason({"origin_country": "ES"}))

    def test_a_realistic_wizard_draft_is_accepted(self) -> None:
        draft = {
            "origin_country": "ES", "origin_city": "Madrid",
            "dest_country": "IE", "dest_city": "Dublin",
            "purpose": "employment", "target_date": "2026-11-01",
            "full_name": "Lucia Fernandez", "members": [],
        }
        self.assertIsNone(unreadable_draft_reason(draft))
        # …and it still converts to the canonical shape.
        converted = intake_draft_to_case_draft(draft)
        self.assertEqual(converted["relocationBasics"]["destCountry"], "IE")

    def test_a_draft_with_one_good_key_among_unknowns_is_accepted(self) -> None:
        """Forward compatibility: the wizard may add fields the backend has not
        learned yet. One convertible key is enough."""
        self.assertIsNone(
            unreadable_draft_reason({"dest_country": "IE", "some_future_field": 1})
        )


class UnreadableDraftIsRejectedTests(unittest.TestCase):
    def test_nested_camelcase_draft_is_rejected_by_name(self) -> None:
        """THE reported shape. The message must say what to send instead, because
        the whole cost of this bug was diagnosis time."""
        reason = unreadable_draft_reason({"relocationBasics": {"destCountry": "IE"}})
        self.assertIsNotNone(reason)
        self.assertIn("relocationBasics", reason)
        self.assertIn("flat", reason.lower())
        self.assertIn("snake_case", reason)

    def test_entirely_unrecognised_body_is_rejected(self) -> None:
        reason = unreadable_draft_reason({"totally": "unrecognised", "shape": 1})
        self.assertIsNotNone(reason)
        self.assertIn("origin_country", reason)  # names what IS expected

    def test_rejection_names_the_keys_it_got(self) -> None:
        reason = unreadable_draft_reason({"alpha": 1, "beta": 2})
        self.assertIn("alpha", reason)
        self.assertIn("beta", reason)


class RecognisedKeysMatchTheConverterTests(unittest.TestCase):
    """Drift guard. The constant lives beside the converter precisely so it cannot
    fall out of step with what the mapping actually consumes — but only a test that
    reads the source can prove it."""

    def test_constant_matches_the_keys_the_converter_reads(self) -> None:
        source = (
            Path(_REPO_ROOT) / "backend" / "intake_draft_to_case_draft.py"
        ).read_text(encoding="utf-8")
        body = source.split("def intake_draft_to_case_draft", 1)[1]
        actual = set(re.findall(r'data\.get\("([a-z_0-9]+)"', body))
        self.assertEqual(
            actual, set(RECOGNISED_INTAKE_KEYS),
            "RECOGNISED_INTAKE_KEYS has drifted from the converter's own reads",
        )


class RelocationProfileRejectsUnknownBodyTests(unittest.TestCase):
    def test_unrecognised_body_is_rejected(self) -> None:
        """Was: 200 with every field null and completion_pct 0."""
        with self.assertRaises(pydantic.ValidationError) as ctx:
            RelocationProfilePayload(totally="unrecognised", shape=123)
        self.assertIn("totally", str(ctx.exception))

    def test_a_valid_body_still_saves(self) -> None:
        p = RelocationProfilePayload(additional_notes="prefers ground floor")
        self.assertEqual(p.additional_notes, "prefers ground floor")

    def test_the_frontends_exact_field_set_is_accepted(self) -> None:
        """frontend/src/api/relocationProfile.ts sends exactly these six and no
        others — the reason forbidding extras is safe for the real caller."""
        for field in ("origin_housing", "housing_preferences", "household",
                      "temp_housing", "financial", "additional_notes"):
            self.assertIn(field, RelocationProfilePayload.model_fields)

    def test_empty_body_remains_a_legitimate_no_op(self) -> None:
        """Clearing the profile is not the bug; an unrecognised body was."""
        self.assertIsNotNone(RelocationProfilePayload())


if __name__ == "__main__":
    unittest.main()

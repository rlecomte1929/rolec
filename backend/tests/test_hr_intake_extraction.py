"""[W1-3] HR contract → proposed intake → human confirm → prefilled draft.

THE GATE IS THE FEATURE. `propose` runs OCR + LLM extraction and writes NOTHING; `confirm`
is the only writer, and it stores the fields in its own request body rather than a
server-side copy of the proposal — so a value cannot reach the draft without a human having
sent it back, and "HR edited it first" is the normal path rather than a special case.

TWO PREMISES IN THE TASK TEXT WERE WRONG, and both are pinned here because getting either
one wrong ships silently:

1. `case_assignments.intake_draft` holds the wizard's FLAT snake_case draft. The nested
   `relocationBasics/employeeProfile/assignmentContext` shape the task named is what
   `intake_draft_to_case_draft` explicitly CANNOT read — storing it is the recorded T18
   failure (accepted, echoed back by GET, then reported entirely missing by the submit
   guard). `test_every_proposed_field_is_a_key_the_converter_reads` is the guard.

2. The existing `update_assignment_intake_draft` is scoped by `employee_user_id`, which is
   unusable here: the point of an HR prefill is that it happens BEFORE the employee exists.
   Measured on Andrea's assignment c4f43f49-110c-44f3-85fa-79f0fb5d1f3e — `employee_user_id`
   NULL at intake_step=0 — so the employee-scoped UPDATE matches no row and returns None.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.intake_contract_extractor import (  # noqa: E402
    PROPOSED_FIELDS,
    empty_extraction,
    extract_intake_fields,
    normalise_extraction,
    proposal_to_draft_patch,
)
from backend.intake_draft_to_case_draft import RECOGNISED_INTAKE_KEYS  # noqa: E402


def _llm_reply(**over):
    """A plausible LLM response for Andrea's Irish contract."""
    base = {
        "full_name": {"value": "Andrea Ramirez", "confidence": 0.97},
        "nationality": {"value": "VE", "confidence": 0.9},
        "job_title": {"value": "Senior Data Engineer", "confidence": 0.95},
        "salary_band": {"value": "58000 EUR", "confidence": 0.88},
        "contract_type": {"value": "permanent", "confidence": 0.8},
        "contract_start": {"value": "2026-10-01", "confidence": 0.93},
        "target_date": {"value": "2026-09-20", "confidence": 0.6},
        "origin_city": {"value": "Madrid", "confidence": 0.7},
        "origin_country": {"value": "ES", "confidence": 0.85},
        "dest_city": {"value": "Dublin", "confidence": 0.96},
        "dest_country": {"value": "IE", "confidence": 0.96},
    }
    base.update(over)
    return base


class ShapeContractTests(unittest.TestCase):
    def test_every_proposed_field_is_a_key_the_converter_reads(self) -> None:
        """The whole prefill is worthless if the submit guard cannot see what we wrote."""
        unknown = set(PROPOSED_FIELDS) - set(RECOGNISED_INTAKE_KEYS)
        self.assertEqual(
            set(), unknown,
            f"these keys would be stored and then silently ignored at submit: {sorted(unknown)}",
        )

    def test_the_patch_is_flat_not_the_nested_case_draft_shape(self) -> None:
        patch = proposal_to_draft_patch(_llm_reply())
        for nested in ("relocationBasics", "employeeProfile", "assignmentContext", "familyMembers"):
            self.assertNotIn(nested, patch)
        self.assertIn("dest_country", patch)


class NormalisationTests(unittest.TestCase):
    def test_a_full_reading_survives(self) -> None:
        fields = normalise_extraction(_llm_reply())
        self.assertEqual("Andrea Ramirez", fields["full_name"]["value"])
        self.assertEqual("IE", fields["dest_country"]["value"])
        self.assertEqual(0.96, fields["dest_country"]["confidence"])

    def test_an_absent_field_is_reported_absent_with_zero_confidence(self) -> None:
        fields = normalise_extraction(_llm_reply(salary_band={"value": None, "confidence": 0.4}))
        self.assertIsNone(fields["salary_band"]["value"])
        self.assertEqual(0.0, fields["salary_band"]["confidence"])

    def test_prose_for_absence_is_not_stored_as_a_value(self) -> None:
        """Models say 'not specified' instead of returning null; a reviewer must not see
        that offered as a reading."""
        for prose in ("N/A", "unknown", "not stated", "none", "  "):
            fields = normalise_extraction(_llm_reply(job_title={"value": prose, "confidence": 0.9}))
            self.assertIsNone(fields["job_title"]["value"], prose)
            self.assertEqual(0.0, fields["job_title"]["confidence"])

    def test_a_country_that_is_not_iso_alpha2_is_rejected(self) -> None:
        for bad in ("Ireland", "IRL", "", "1E"):
            fields = normalise_extraction(_llm_reply(dest_country={"value": bad, "confidence": 0.9}))
            self.assertIsNone(fields["dest_country"]["value"], bad)

    def test_a_non_iso_date_is_rejected_rather_than_guessed(self) -> None:
        for bad in ("01/10/2026", "October 2026", "2026-13-01x", ""):
            fields = normalise_extraction(_llm_reply(contract_start={"value": bad, "confidence": 0.9}))
            self.assertIsNone(fields["contract_start"]["value"], bad)

    def test_confidence_is_clamped(self) -> None:
        hi = normalise_extraction(_llm_reply(job_title={"value": "X", "confidence": 4.2}))
        lo = normalise_extraction(_llm_reply(job_title={"value": "X", "confidence": -3}))
        self.assertEqual(1.0, hi["job_title"]["confidence"])
        self.assertEqual(0.0, lo["job_title"]["confidence"])

    def test_garbage_from_the_model_degrades_to_an_empty_proposal(self) -> None:
        for junk in (None, [], "nope", {"unexpected": 1}):
            fields = normalise_extraction(junk)
            self.assertEqual(set(PROPOSED_FIELDS), set(fields))
            self.assertTrue(all(f["value"] is None for f in fields.values()))


class PatchBuildingTests(unittest.TestCase):
    def test_blank_fields_are_dropped_not_written_as_empty_strings(self) -> None:
        """An empty string overwrites good data; an absent key leaves it alone."""
        patch = proposal_to_draft_patch(_llm_reply(job_title={"value": "", "confidence": 0.0}))
        self.assertNotIn("job_title", patch)

    def test_hr_edited_plain_values_are_accepted(self) -> None:
        """The confirm body carries HR's values, which may be bare strings, not {value,...}."""
        patch = proposal_to_draft_patch({"job_title": "Staff Engineer", "dest_country": "ie"})
        self.assertEqual("Staff Engineer", patch["job_title"])
        self.assertEqual("IE", patch["dest_country"])

    def test_unknown_keys_cannot_be_smuggled_into_the_draft(self) -> None:
        patch = proposal_to_draft_patch({"job_title": "X", "is_admin": True, "members": "junk"})
        self.assertEqual({"job_title"}, set(patch))


class _FakeDb:
    """Records writes so 'propose writes nothing' is provable, not assumed."""

    def __init__(self, draft=None):
        self.draft = dict(draft or {})
        self.writes = 0

    def merge_assignment_intake_draft_as_hr(self, assignment_id, patch, request_id=None):
        self.writes += 1
        merged = dict(self.draft)
        for k, v in patch.items():
            if k not in merged or merged.get(k) in (None, "", [], {}):
                merged[k] = v
        self.draft = merged
        return {"intake_draft": merged}


class EndToEndFlowTests(unittest.TestCase):
    """extract → propose → confirm → prefilled, and nothing writes without confirm."""

    def test_extraction_without_an_api_key_yields_an_empty_proposal_not_an_error(self) -> None:
        key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            fields = asyncio.run(extract_intake_fields("Employment contract ..."))
        finally:
            if key is not None:
                os.environ["OPENAI_API_KEY"] = key
        self.assertEqual(empty_extraction(), fields)

    def test_empty_document_text_never_calls_the_model(self) -> None:
        self.assertEqual(empty_extraction(), asyncio.run(extract_intake_fields("   ")))

    def test_proposing_writes_nothing(self) -> None:
        """The acceptance criterion. A proposal is computed and the DB is untouched."""
        db = _FakeDb()
        fields = normalise_extraction(_llm_reply())          # what propose returns
        self.assertTrue(any(f["value"] for f in fields.values()))
        self.assertEqual(0, db.writes, "propose wrote to the draft")
        self.assertEqual({}, db.draft)

    def test_confirm_writes_the_reviewed_fields_and_stamps_provenance(self) -> None:
        db = _FakeDb()
        patch = proposal_to_draft_patch(normalise_extraction(_llm_reply()))
        patch["hr_extracted_fields"] = sorted(patch.keys())
        result = db.merge_assignment_intake_draft_as_hr("a-1", patch)
        draft = result["intake_draft"]
        self.assertEqual(1, db.writes)
        self.assertEqual("IE", draft["dest_country"])
        self.assertEqual("ES", draft["origin_country"])
        self.assertEqual("Andrea Ramirez", draft["full_name"])
        self.assertIn("dest_country", draft["hr_extracted_fields"])

    def test_confirm_stores_hr_s_edit_not_the_model_s_reading(self) -> None:
        """HR corrected the job title; the stored value must be theirs."""
        db = _FakeDb()
        edited = dict(_llm_reply())
        edited["job_title"] = "Principal Data Engineer"   # HR's edit, a bare string
        db.merge_assignment_intake_draft_as_hr("a-1", proposal_to_draft_patch(edited))
        self.assertEqual("Principal Data Engineer", db.draft["job_title"])

    def test_an_existing_employee_answer_is_never_overwritten(self) -> None:
        """HR proposing a title does not get to clobber one the employee typed."""
        db = _FakeDb({"job_title": "Employee's own answer", "dest_country": "IE"})
        db.merge_assignment_intake_draft_as_hr("a-1", proposal_to_draft_patch(_llm_reply()))
        self.assertEqual("Employee's own answer", db.draft["job_title"])
        self.assertEqual("Madrid", db.draft["origin_city"])  # a genuinely empty field is filled

    def test_the_prefilled_draft_is_readable_by_the_submit_converter(self) -> None:
        """End of the chain: what we store must convert, or the prefill achieved nothing."""
        from backend.intake_draft_to_case_draft import unreadable_draft_reason

        db = _FakeDb()
        db.merge_assignment_intake_draft_as_hr("a-1", proposal_to_draft_patch(_llm_reply()))
        self.assertIsNone(unreadable_draft_reason(db.draft), "stored draft is unreadable")

    def test_the_corridor_the_prefill_unblocks_is_es_ie(self) -> None:
        """Andrea's case regenerates to the CSEP journey only once origin+dest exist — the
        exact gap W1-2 measured. This pins that this flow closes it."""
        db = _FakeDb()
        db.merge_assignment_intake_draft_as_hr("a-1", proposal_to_draft_patch(_llm_reply()))
        self.assertEqual("ES", db.draft["origin_country"])
        self.assertEqual("IE", db.draft["dest_country"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

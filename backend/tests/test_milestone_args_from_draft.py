"""`milestone_args_from_draft` — the one copy of the seed context extraction.

WHY IT IS EXTRACTED. This logic lived inline in the `ensure_defaults` arm of
`GET /api/cases/{id}/timeline`. The admin regenerate endpoint needs exactly the same
context, and if the two ever disagree a regenerated plan silently differs from the one the
case was seeded with. The contract-type mapping is the sharp edge: `contract_type` gates
which PHASES are active (`plan_scope.active_phases_for_case_type`), so a missed mapping
makes whole groups of steps appear or vanish for reasons unrelated to the corridor — and
nothing about the resulting plan looks obviously wrong.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.timeline_service import milestone_args_from_draft  # noqa: E402


@pytest.mark.parametrize(
    "wizard_label,internal_token",
    [("assignment", "lta"), ("permanent", "permanent_transfer"), ("contract", "short_term_project")],
)
def test_wizard_contract_labels_map_to_internal_tokens(wizard_label, internal_token):
    """The wizard says 'assignment'; plan_scope says 'lta'. Unmapped, phases go wrong."""
    args = milestone_args_from_draft({"assignment": {"contractType": wizard_label}})
    assert args["contract_type"] == internal_token


def test_the_mapping_is_case_insensitive():
    assert milestone_args_from_draft(
        {"assignment": {"contractType": "Permanent"}}
    )["contract_type"] == "permanent_transfer"


def test_an_unknown_contract_type_passes_through_untranslated():
    """Don't invent a mapping: an unrecognised value is handed on as-is for the caller
    to treat as unknown, not silently coerced into one of the three we know."""
    assert milestone_args_from_draft(
        {"assignment": {"contractType": "secondment"}}
    )["contract_type"] == "secondment"


def test_contract_type_precedence_assignment_then_context_then_basics():
    draft = {
        "assignment": {"contractType": "permanent"},
        "assignmentContext": {"contractType": "contract"},
        "relocationBasics": {"contractType": "assignment"},
    }
    assert milestone_args_from_draft(draft)["contract_type"] == "permanent_transfer"
    draft.pop("assignment")
    assert milestone_args_from_draft(draft)["contract_type"] == "short_term_project"
    draft.pop("assignmentContext")
    assert milestone_args_from_draft(draft)["contract_type"] == "lta"


def test_nationality_precedence_primary_applicant_wins():
    draft = {
        "primaryApplicant": {"nationality": "VE"},
        "employeeProfile": {"nationality": "ES", "nationalityCountry": "PT"},
        "relocationBasics": {"nationality": "FR"},
    }
    assert milestone_args_from_draft(draft)["nationality"] == "VE"


def test_nationality_falls_through_to_nationalityCountry():
    draft = {"employeeProfile": {"nationalityCountry": "PT"}}
    assert milestone_args_from_draft(draft)["nationality"] == "PT"


def test_both_destination_key_spellings_are_accepted():
    """The draft carries destCountry in some versions and destination_country in others."""
    assert milestone_args_from_draft(
        {"relocationBasics": {"destCountry": "IE", "originCountry": "ES"}}
    ) | {} == {
        "contract_type": None, "family_profile": None,
        "destination_country": "IE", "origin_country": "ES", "nationality": None,
    }
    snake = milestone_args_from_draft(
        {"relocationBasics": {"destination_country": "IE", "origin_country": "ES"}}
    )
    assert (snake["destination_country"], snake["origin_country"]) == ("IE", "ES")


def test_an_empty_draft_yields_all_none_and_does_not_raise():
    assert milestone_args_from_draft({}) == {
        "contract_type": None, "family_profile": None,
        "destination_country": None, "origin_country": None, "nationality": None,
    }
    assert milestone_args_from_draft(None)["contract_type"] is None


def test_andreas_shape_resolves_end_to_end():
    """The ES→IE case this work exists for: Venezuelan national, Spain to Ireland."""
    args = milestone_args_from_draft({
        "assignment": {"contractType": "assignment"},
        "relocationBasics": {"destCountry": "IE", "originCountry": "ES"},
        "primaryApplicant": {"nationality": "VE"},
    })
    assert args == {
        "contract_type": "lta", "family_profile": None,
        "destination_country": "IE", "origin_country": "ES", "nationality": "VE",
    }


def test_the_result_splats_into_compute_default_milestones():
    """Contract check: the keys must be exactly that function's context kwargs.

    A renamed key would raise TypeError at the call site rather than here, in a
    background task whose failures are swallowed — so pin the names.
    """
    import inspect

    from backend.app.services.timeline_service import compute_default_milestones

    params = set(inspect.signature(compute_default_milestones).parameters)
    assert set(milestone_args_from_draft({})).issubset(params)

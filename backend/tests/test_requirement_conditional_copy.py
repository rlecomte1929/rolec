"""AIQ-1969 — a conditional requirement must render WITH its condition, never as a flat claim.

The failure this guards: Andrea (ES→IE, EEA) is shown "you are exempt from Emergency Tax".
Relief is conditional — on holding a PPS number AND the employer operating a correct RPN. Shown
flat, it tells her to expect a normal first payslip when she may well be taxed at 40%.

Pure unit tests: no DB, no network, no LLM. The module under test is dependency-free so both
serving surfaces (`roadmap_requirement_copy` and the sufficiency serializer) can share it.
"""
from __future__ import annotations

import pytest

from backend.app.services.requirement_conditional_copy import (
    CONDITION_LEAD,
    EASY_TO_MISS_LEAD,
    UNVERIFIED_CONDITION_LEAD,
    build_render_flags,
    render_requirement_copy,
)

BODY = "Emergency Tax does not apply once your job is registered."
CONDITION = "you hold a PPS number and your employer has a valid RPN"


# --- unconditional facts are left alone -------------------------------------------------


def test_plain_fact_is_unchanged():
    assert render_requirement_copy(BODY) == BODY


def test_assertion_mode_unconditional_is_unchanged():
    assert render_requirement_copy(BODY, assertion_mode="unconditional") == BODY


def test_condition_without_conditional_mode_is_still_rendered():
    """A `conditional_on` present without the mode is still a condition — render it.

    Otto's records carry `conditional_on` more consistently than `assertion_mode`; dropping
    the condition because a sibling field was absent is exactly the silent-flattening bug.
    """
    out = render_requirement_copy(BODY, conditional_on=CONDITION)
    assert CONDITION in out
    assert CONDITION_LEAD in out


# --- conditional facts carry their condition --------------------------------------------


def test_conditional_fact_renders_with_its_condition():
    out = render_requirement_copy(BODY, assertion_mode="conditional", conditional_on=CONDITION)
    assert BODY in out
    assert CONDITION in out
    assert CONDITION_LEAD in out


def test_conditional_fact_never_reads_as_a_flat_exemption():
    out = render_requirement_copy(
        "You are exempt from Emergency Tax.",
        assertion_mode="conditional",
        conditional_on=CONDITION,
    ).lower()
    # The exemption may still be stated, but never without the condition attached.
    assert CONDITION.lower() in out
    assert CONDITION_LEAD.lower() in out


def test_conditional_with_missing_condition_hedges_instead_of_asserting():
    """The dangerous case: mode says conditional, but nothing records the condition.

    Rendering the body alone would restate it as unconditional fact. Hedge instead.
    """
    out = render_requirement_copy(BODY, assertion_mode="conditional", conditional_on=None)
    assert UNVERIFIED_CONDITION_LEAD in out
    assert BODY in out


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_condition_is_treated_as_missing(blank):
    out = render_requirement_copy(BODY, assertion_mode="conditional", conditional_on=blank)
    assert UNVERIFIED_CONDITION_LEAD in out


def test_condition_is_not_duplicated_when_already_in_the_body():
    body = f"Emergency Tax stops once {CONDITION}."
    out = render_requirement_copy(body, assertion_mode="conditional", conditional_on=CONDITION)
    assert out.lower().count(CONDITION.lower()) == 1


# --- non_obvious is flagged easy-to-miss -------------------------------------------------


def test_non_obvious_is_flagged():
    out = render_requirement_copy(BODY, non_obvious=True)
    assert EASY_TO_MISS_LEAD in out
    assert BODY in out


def test_non_obvious_false_adds_nothing():
    assert EASY_TO_MISS_LEAD not in render_requirement_copy(BODY, non_obvious=False)


def test_non_obvious_and_conditional_compose():
    out = render_requirement_copy(
        BODY, assertion_mode="conditional", conditional_on=CONDITION, non_obvious=True
    )
    assert EASY_TO_MISS_LEAD in out
    assert CONDITION in out
    assert BODY in out


def test_rendering_is_idempotent():
    """Re-rendering already-rendered copy must not stack leads (the overlay can re-run)."""
    once = render_requirement_copy(
        BODY, assertion_mode="conditional", conditional_on=CONDITION, non_obvious=True
    )
    twice = render_requirement_copy(
        once, assertion_mode="conditional", conditional_on=CONDITION, non_obvious=True
    )
    assert once == twice


# --- degrade safely ----------------------------------------------------------------------


def test_empty_body_returns_empty():
    assert render_requirement_copy("") == ""
    assert render_requirement_copy(None) == ""


def test_unknown_assertion_mode_is_treated_as_unconditional():
    assert render_requirement_copy(BODY, assertion_mode="probably") == BODY


# --- structured flags for the frontend ---------------------------------------------------


def test_flags_expose_condition_for_styling_not_string_parsing():
    flags = build_render_flags(
        assertion_mode="conditional", conditional_on=CONDITION, non_obvious=True
    )
    assert flags == {
        "isConditional": True,
        "conditionText": CONDITION,
        "conditionVerified": True,
        "easyToMiss": True,
    }


def test_flags_for_a_plain_fact():
    flags = build_render_flags()
    assert flags == {
        "isConditional": False,
        "conditionText": None,
        "conditionVerified": True,
        "easyToMiss": False,
    }


def test_flags_mark_an_unrecorded_condition_unverified():
    flags = build_render_flags(assertion_mode="conditional", conditional_on=None)
    assert flags["isConditional"] is True
    assert flags["conditionVerified"] is False
    assert flags["conditionText"] is None

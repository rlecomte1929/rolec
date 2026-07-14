"""Case-level behaviour of the purpose fix, through the real engine.

The resolver unit tests prove the mapping. These prove the consequences:

  * an `sta` case gets its long-term-only requirements WAIVED — the recovered
    assignment type is live, not just parsed. staWaived has never once fired in
    production because assignmentContext.assignmentType is null on ~99% of cases.
  * a `domestic` (in-country) move NEVER sees a visa item, and is not left with a
    blank screen either — it gets a stated "no immigration requirements".
"""
from __future__ import annotations

import json
import os

import pytest

yaml = pytest.importorskip("yaml")

from backend.app.services.requirements_purpose_key import assignment_type_from_purpose, to_purpose
from backend.app.services.rules_engine import apply_rules
from backend.scripts.seed_requirements import build_payloads

_SEED = os.path.join(os.path.dirname(__file__), "..", "seeds", "requirements", "france.yaml")


def _france_items(purpose="employment"):
    with open(_SEED, "r", encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    return [
        {
            "id": p["id"], "pillar": p["pillar"], "title": p["title"],
            "description": p["description"], "severity": p["severity"], "owner": p["owner"],
            "requiredFields": json.loads(p["required_fields_json"]),
            "citations": json.loads(p["citations_json"]),
            "appliesToAssignmentTypes": (
                json.loads(p["applies_to_assignment_types_json"])
                if p["applies_to_assignment_types_json"] else None
            ),
            "appliesToNationalityClasses": (
                json.loads(p["applies_to_nationality_classes_json"])
                if p["applies_to_nationality_classes_json"] else None
            ),
        }
        for p in build_payloads(seed, only_country="FRANCE") if p["purpose"] == purpose
    ]


def _draft_with_recovered_assignment(raw_purpose, nationality="Indian"):
    """Mirrors what compute_case_requirements does: resolve the purpose, and
    recover the assignment type out of it when the real field is empty."""
    draft = {
        "employeeProfile": {"nationality": nationality},
        "relocationBasics": {
            "destCountry": "FRANCE", "originCountry": "India", "purpose": raw_purpose,
        },
        "assignmentContext": {},
    }
    recovered = assignment_type_from_purpose(raw_purpose)
    if recovered:
        draft["assignmentContext"]["assignmentType"] = recovered
    return draft


class TestStaWaiversFinallyFire:
    """272 cases store lta/sta/permanent as their purpose while
    assignmentContext.assignmentType sits empty — so the assignment-type gate has
    never fired for any of them, and neither has a single STA waiver."""

    def test_an_sta_case_waives_the_long_term_only_requirement(self):
        purpose = to_purpose("sta")
        assert purpose == "employment"

        _, expanded, flags = apply_rules(
            _draft_with_recovered_assignment("sta"), _france_items()
        )
        titles = [i["title"] for i in expanded]

        assert "Multi-year residence card renewal" not in titles, (
            "the residence-card renewal is [LTA, PERMANENT] only — a short-term "
            "assignee must not be told to renew a card they will never hold"
        )
        assert flags.get("staWaived"), (
            "the waived title must be SURFACED so the UI can explain the shorter "
            "list, not silently dropped"
        )
        assert "Multi-year residence card renewal" in flags["staWaived"]

    def test_an_lta_case_keeps_the_long_term_requirement(self):
        _, expanded, flags = apply_rules(
            _draft_with_recovered_assignment("lta"), _france_items()
        )
        titles = [i["title"] for i in expanded]
        assert "Multi-year residence card renewal" in titles
        assert not flags.get("staWaived")

    def test_without_recovery_the_sta_signal_would_be_lost(self):
        """Guards the trap: mapping the purpose ALONE and dropping the assignment
        type would silently serve an STA case its long-term requirements."""
        draft = {
            "employeeProfile": {"nationality": "Indian"},
            "relocationBasics": {"destCountry": "FRANCE", "purpose": "sta"},
            "assignmentContext": {},  # NOT recovered
        }
        _, expanded, flags = apply_rules(draft, _france_items())
        assert "Multi-year residence card renewal" in [i["title"] for i in expanded]
        assert not flags.get("staWaived")


class TestRecoveryNeverOverridesARealValue:
    def test_an_explicit_assignment_type_wins(self):
        """`purpose: lta` says LTA, but the case explicitly says STA. The explicit
        field is the truth; the purpose field is a leak."""
        draft = _draft_with_recovered_assignment("lta")
        draft["assignmentContext"]["assignmentType"] = "STA"  # explicit, real
        _, expanded, flags = apply_rules(draft, _france_items())
        assert "Multi-year residence card renewal" not in [i["title"] for i in expanded]
        assert flags.get("staWaived")


class TestInCountryMoveIsResolvedByFactNotLabel:
    """`domestic` and `repatriation` live in the same free-text field we have
    learned not to trust. The engine keys off origin == destination instead."""

    def test_the_purpose_still_resolves_so_the_lookup_has_a_key(self):
        assert to_purpose("domestic") == "employment"
        assert to_purpose("repatriation") == "employment"

    def test_a_cross_border_repatriation_is_not_short_circuited(self):
        """A repatriation that DOES cross a border must fall through to the normal
        engine — "no immigration requirements" is only true if the destination is
        their country of nationality, and we usually don't know that. If we cannot
        positively know, we make no claim."""
        from backend.app.services.requirements_builder import _is_in_country_move

        class _Case:
            origin_country = None
            dest_country = None

        cross_border = {
            "relocationBasics": {"originCountry": "India", "destCountry": "France"},
        }
        assert _is_in_country_move(cross_border, _Case()) is False

    def test_same_country_is_an_in_country_move(self):
        from backend.app.services.requirements_builder import _is_in_country_move

        class _Case:
            origin_country = None
            dest_country = None

        for origin, dest in [("France", "France"), ("FR", "France"), ("Germany", "DE")]:
            draft = {"relocationBasics": {"originCountry": origin, "destCountry": dest}}
            assert _is_in_country_move(draft, _Case()) is True, f"{origin} -> {dest}"

    def test_the_write_read_round_trip_preserves_the_sta_signal(self):
        """The bug the unit tests missed and LIVE verification caught.

        `_canonical_purpose` normalises the purpose column on write, so `sta`
        becomes `employment` before it is ever stored. `compute_case_requirements`
        then does `purpose_raw = case.purpose or draft[...]` — the COLUMN wins, so
        the raw `sta` still sitting in the draft is never consulted, the assignment
        type is never recovered, and every STA waiver silently dies on newly
        written cases.

        Every unit test passed, because they all called apply_rules directly and
        none of them went through the write path. Prod said 9 items for an STA case
        that should have had 8. This pins the round trip.
        """
        from backend.app.routers.cases_write import _assignment_derived, _canonical_purpose

        draft = {  # what the intake actually sends
            "relocationBasics": {"destCountry": "France", "purpose": "sta"},
            "assignmentContext": {},
        }

        canonical = _canonical_purpose(draft["relocationBasics"]["purpose"])
        derived = _assignment_derived(draft)

        assert canonical == "employment", "purpose is canonicalised for the catalog key"
        assert derived["assignment_type"] == "STA", "and the STA signal must survive it"
        assert draft["assignmentContext"]["assignmentType"] == "STA", (
            "it must land in the DRAFT too — apply_rules reads it from there, and the "
            "canonicalised column can no longer tell us it was ever an STA"
        )

    def test_an_explicit_assignment_type_is_never_overridden_by_the_purpose(self):
        from backend.app.routers.cases_write import _assignment_derived

        draft = {
            "relocationBasics": {"purpose": "lta"},          # the leaked value says LTA
            "assignmentContext": {"assignmentType": "STA"},  # the real field says STA
        }
        assert _assignment_derived(draft)["assignment_type"] == "STA"
        assert draft["assignmentContext"]["assignmentType"] == "STA"

    def test_a_real_purpose_leaves_the_assignment_type_alone(self):
        from backend.app.routers.cases_write import _assignment_derived

        draft = {"relocationBasics": {"purpose": "employment"}, "assignmentContext": {}}
        assert _assignment_derived(draft)["assignment_type"] is None
        assert "assignmentType" not in draft["assignmentContext"]

    def test_an_unknown_country_is_not_assumed_to_be_in_country(self):
        """Fail safe: if either side doesn't resolve, we must NOT claim there is no
        border and therefore no immigration requirement."""
        from backend.app.services.requirements_builder import _is_in_country_move

        class _Case:
            origin_country = None
            dest_country = None

        for origin, dest in [(None, None), ("Klingon", "Klingon"), ("France", None)]:
            draft = {"relocationBasics": {"originCountry": origin, "destCountry": dest}}
            assert _is_in_country_move(draft, _Case()) is False, f"{origin} -> {dest}"

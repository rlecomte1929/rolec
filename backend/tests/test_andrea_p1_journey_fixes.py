"""[ANDREA-P1] Regressions found while running Andrea Peinado (ES→IE, VE national, spouse +
two children) through the platform as a relocation specialist on 2026-09-12.

Each test pins one production failure observed on her live case:

1. HR-entered household with ``fullName: null`` crashed the whole roadmap (500) in
   ``roadmap_builder._initials``.
2. ``maritalStatus: "married"`` (HR / API vocabulary) produced no family track and no
   FAMILY_REGISTRATION corridor step; only the wizard's ``partner_kids`` did.
3. Otto-promoted departure rows carry UUID ids and were silently withheld by the
   direction gate even though every citation states ``corridor: "ES->IE"``.
4. ``pre_departure_origin_NN`` milestones must land in the pre_departure phase.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.services import household
from backend.app.services.departure_requirements import _citation_origin_iso, _row_origin_iso
from backend.app.services.roadmap_builder import _build_family_track, _first_name, _initials
from backend.relocation_plan_service import _phase_and_seq_from_synthetic_code


# ── 1. None-safe names ────────────────────────────────────────────────────────────────

def test_initials_and_first_name_tolerate_none():
    assert _initials(None) == ""
    assert _first_name(None) == ""
    assert _initials("Andrea Peinado") == "AP"


def test_family_track_survives_null_member_names():
    case = {
        "draft": {
            "familyMembers": {
                "maritalStatus": "partner_kids",
                "spouse": {"fullName": None, "nationality": "MK", "wantsToWork": True},
                "children": [{"fullName": None}, {"fullName": None}],
            }
        }
    }
    track = _build_family_track(case)
    assert track is not None
    titles = [s["title"] for s in track["steps"]]
    assert any("Dependent permit" in t for t in titles)
    assert sum("Child documents" in t for t in titles) == 2
    # Placeholder names are distinct so two unnamed children do not collide on key.
    keys = [s["key"] for s in track["steps"] if s["key"].startswith("child-permit-")]
    assert len(keys) == len(set(keys))


# ── 2. Household vocabulary ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "family, expect_partner, expect_kids",
    [
        ({"maritalStatus": "partner_kids"}, True, True),
        ({"maritalStatus": "partner"}, True, False),
        ({"maritalStatus": "kids_only"}, False, True),
        ({"maritalStatus": "married", "spouse": {"nationality": "MK"}}, True, False),
        ({"maritalStatus": "married", "spouse": {"nationality": "MK"}, "children": [{"fullName": "A"}]}, True, True),
        ({"maritalStatus": "single"}, False, False),
        ({}, False, False),
        (None, False, False),
    ],
)
def test_household_reads_wizard_and_plain_vocabulary(family, expect_partner, expect_kids):
    draft = {"familyMembers": family} if family is not None else {}
    assert household.has_partner(draft) is expect_partner
    assert household.has_children(draft) is expect_kids
    assert household.has_family_relocating(draft) is (expect_partner or expect_kids)


def test_display_name_applies_fallback_for_explicit_null():
    assert household.display_name(None, "Your partner") == "Your partner"
    assert household.display_name("  ", "Child 1") == "Child 1"
    assert household.display_name("Maria", "x") == "Maria"


# ── 3. Departure direction gate accepts citation corridor ─────────────────────────────

def test_citation_corridor_gives_origin_iso():
    assert _citation_origin_iso('[{"url": "https://x", "corridor": "ES->IE"}]') == "ES"
    assert _citation_origin_iso([{"corridor": "IE-ES"}]) == "IE"
    assert _citation_origin_iso("not json") is None
    assert _citation_origin_iso(None) is None


def test_row_origin_prefers_id_then_falls_back_to_citations():
    tagged = SimpleNamespace(id="ES:ES-IE:departure_baja_padron", citations_json='[{"corridor": "IE->ES"}]')
    assert _row_origin_iso(tagged) == "ES"  # the id wins
    promoted = SimpleNamespace(id="2ad01056-ac2f-569a-86ad-0c42e47e5162", citations_json='[{"corridor": "ES->IE"}]')
    assert _row_origin_iso(promoted) == "ES"
    reverse = SimpleNamespace(id="ES:IE-ES:tax_beckham_regime", citations_json=None)
    assert _row_origin_iso(reverse) == "IE"  # Spain-as-destination row is withheld for an ES origin


# ── 4. Origin milestones land in pre_departure ────────────────────────────────────────

def test_origin_marker_parses_into_pre_departure_phase():
    assert _phase_and_seq_from_synthetic_code("pre_departure_origin_03") == ("pre_departure", 3)
    assert _phase_and_seq_from_synthetic_code("post_arrival_corridor_07") == ("post_arrival", 7)

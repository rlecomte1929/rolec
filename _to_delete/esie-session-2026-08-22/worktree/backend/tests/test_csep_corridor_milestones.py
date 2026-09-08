"""[AIQ-1867] The milestone-backed plan view must serve the corridor's real journey.

#1929 wired `corridors/ES_IE/pathways/CSEP_2026/v1.yaml` into `roadmap_builder`. That is
not the surface the employee opens: `GET /api/relocation-plans/{case}/view` is served by
`relocation_plan_view_service`, which builds phases from `case_milestones` — rows produced
by `timeline_service.compute_default_milestones` from the GENERIC task library.

Measured on Andrea's live case (6ecadafe-0fdb-43c5-b8dc-0284e323cf51, ES→IE, Venezuelan,
family of 4) on 2026-08-21: 16 milestones, 0 corridor steps, and all three of
`task_visa_docs_prep` / `task_visa_submit` / `task_biometrics` — the generic copy the
ticket exists to remove. These tests pin the milestone path specifically, so a future
change to roadmap_builder alone cannot make them pass.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.timeline_service import compute_default_milestones  # noqa: E402

GENERIC_VISA = {"task_visa_docs_prep", "task_visa_submit", "task_biometrics"}


def _milestones(*, nationality, origin="ES", destination="IE", family=True):
    draft = {
        "relocationBasics": {
            "originCountry": origin,
            "destCountry": destination,
            "nationality": nationality,
        },
        "familyProfile": {"hasSpouse": True, "childrenCount": 2} if family else {},
    }
    return compute_default_milestones(
        case_id="test-case",
        case_draft=draft,
        destination_country=destination,
        origin_country=origin,
        nationality=nationality,
    )


def _corridor(rows):
    return [r for r in rows if "_corridor_" in r["milestone_type"]]


def _titles(rows):
    return " | ".join(r["title"] for r in rows)


# ── the third-country route: what Andrea should actually see ──────────────────────

def test_a_third_country_national_gets_the_csep_journey_not_the_generic_pack():
    rows = _milestones(nationality="VE")
    corridor = _corridor(rows)
    assert corridor, "ES_IE declares CSEP_2026; a Venezuelan national must get its steps"
    blob = _titles(corridor)
    assert "Critical Skills Employment Permit" in blob
    assert "'D' Employment visa" in blob or "D' Employment visa" in blob


def test_the_generic_visa_pack_is_superseded_not_shown_alongside():
    """Showing both is worse than showing only the generic one — the employee cannot tell
    which is real."""
    rows = _milestones(nationality="VE")
    assert not [r for r in rows if r["milestone_type"] in GENERIC_VISA]


def test_the_csep_steps_land_in_their_real_phases_not_all_in_pre_departure():
    """`{phase}_corridor_{NN}` exists so relocation_plan_service can place each step. An
    unparsed code collapses everything into pre_departure/999 and the journey renders as
    one undifferentiated block."""
    corridor = _corridor(_milestones(nationality="VE"))
    phases = {r["milestone_type"].split("_corridor_")[0] for r in corridor}
    assert "immigration" in phases
    assert len(phases) > 1, f"every step landed in one phase: {phases}"


def test_the_irp_registration_step_is_present_for_a_third_country_national():
    """Registration at Burgh Quay within 90 days is the step with a real deadline, and the
    one entirely absent from the generic scaffold."""
    blob = _titles(_corridor(_milestones(nationality="VE")))
    assert "IRP" in blob or "Irish Residence Permit" in blob or "immigration registration" in blob.lower()


# ── free movement: the same corridor, a different person ──────────────────────────

def test_an_eu_national_on_the_same_corridor_gets_no_permit_or_visa_steps():
    corridor = _corridor(_milestones(nationality="ES"))
    assert not [r for r in corridor if r["milestone_type"].startswith("immigration_corridor_")]


def test_an_eu_national_still_gets_the_settlement_steps():
    """Free movement removes the permit, not the PPSN or the Revenue registration."""
    blob = _titles(_corridor(_milestones(nationality="ES")))
    assert "PPSN" in blob


# ── every other corridor must be untouched ────────────────────────────────────────

def test_in_de_now_serves_its_blue_card_journey():
    """CHANGED from #1938, deliberately. That PR made IN_DE fall back because its step ids
    were not in _CORRIDOR_STEP_PHASE and position was not yet derived. Phase now comes from
    the pathway's own arrival_anchor, so BLUECARD_2026 serves — and because it describes
    pre-departure work, it supersedes the generic pack rather than rendering "D-visa
    application at the German mission in Bangalore" next to "Prepare visa / work permit
    application pack"."""
    rows = _milestones(nationality="IN", origin="IN", destination="DE")
    assert _corridor(rows)
    assert not [r for r in rows if r["milestone_type"] in GENERIC_VISA]


def test_fr_no_serves_its_free_movement_journey_without_striping_the_visa_track():
    """CHANGED from #1938, deliberately. FR_NO's EEA_FREEDOM_2026 now serves its
    register-on-arrival steps. It contributes nothing before travel, so it does NOT
    supersede the generic visa pack — a third-country national routed onto an EEA pathway
    keeps that guidance, because the pathway does not describe their route."""
    rows = _milestones(nationality="IN", origin="FR", destination="NO")
    assert _corridor(rows)
    assert [r for r in rows if r["milestone_type"] in GENERIC_VISA]


def test_an_unknown_corridor_is_unchanged():
    assert not _corridor(_milestones(nationality="US", origin="US", destination="JP"))


def test_a_malformed_draft_never_breaks_milestone_generation():
    """The generic scaffold is the fallback and must survive any overlay failure."""
    rows = compute_default_milestones(case_id="t", case_draft={"relocationBasics": None})
    assert rows, "milestone generation must not return empty on a malformed draft"


# ── [AIQ-1867 follow-up] every authored corridor, not just ES_IE ──────────────────
#
# #1938 gated on _CORRIDOR_STEP_PHASE, a hand-written map of the 13 CSEP step ids, so ten
# corridors with an authored pathway served the generic scaffold anyway — 82 distinct
# unmapped step ids, NO_FR alone declaring 30. Phase is now derived from the pathway's own
# arrival_anchor, which every pathway sets on exactly one step.

from collections import Counter  # noqa: E402

import pytest  # noqa: E402

_AUTHORED = [
    ("ES", "IE"), ("IN", "DE"), ("FR", "NO"), ("FR", "DE"), ("FR", "ES"),
    ("FR", "NL"), ("ES", "NL"), ("FR", "CH"), ("DE", "NO"), ("IE", "ES"),
]


def _phases(rows):
    return Counter(
        r["milestone_type"].split("_corridor_")[0]
        for r in rows if "_corridor_" in r["milestone_type"]
    )


@pytest.mark.parametrize("origin,dest", _AUTHORED)
def test_every_authored_corridor_serves_its_own_journey(origin, dest):
    rows = _milestones(nationality="IN", origin=origin, destination=dest)
    assert _corridor(rows), f"{origin}_{dest} declares a pathway and must serve it"


@pytest.mark.parametrize("origin,dest", _AUTHORED)
def test_no_corridor_collapses_into_a_single_phase(origin, dest):
    """The #1938 defect by name: 13 of IN_DE's 14 steps once landed in pre_departure,
    which is a worse plan than the generic scaffold it replaced."""
    phases = _phases(_milestones(nationality="IN", origin=origin, destination=dest))
    assert len(phases) > 1, f"{origin}_{dest} put every step in one phase: {dict(phases)}"


def test_a_pathway_whose_order_is_not_chronological_falls_back():
    """NO_FR's RETURNING_EEA_CITIZEN_2026 lists `A0_DEPART_NO` first, then 29 steps — several
    of which are Norwegian EXIT tasks that must happen BEFORE departure ("Preserve BankID
    before deregistration disables it"). Position would place them after she lands in
    France, which is worse than saying nothing."""
    rows = _milestones(nationality="IN", origin="NO", destination="FR")
    assert not _corridor(rows)


def test_es_ie_keeps_the_finer_explicit_placement():
    """The derived rule is coarse — it cannot say "immigration". ES_IE is in the explicit
    map precisely so its permit and visa steps land in the immigration phase, which is what
    AIQ-1867 asked for. The override must keep winning over the derivation."""
    phases = _phases(_milestones(nationality="VE"))
    assert "immigration" in phases
    assert phases["immigration"] >= 4

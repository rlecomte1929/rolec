"""The NO→FR corridor, and the honesty gates from ReloPass_Fixture_NO-FR.md §3.

This is the acceptance fixture: a French national who has ALREADY left Norway,
stays on his Norwegian payroll, and is self-relocating to Paris with no HR and no
employer support.

§3 gives four gates. They are two-sided on purpose — it is not enough to show the
right things, we must also NOT show the wrong ones:

  1. Anti-silence   — immigration must be a STATED nothing_to_do with a reason.
  2. Pending, not asserted — the five open counsel questions must appear as
     PENDING and must NOT appear as asserted content.
  3. Advice-line routing — personalised determinations route to a professional.
  4. Verified-as-hard — every fixture HARD row asserts at its stated value.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.relopass.corridors import load_corridor
from backend.relopass.corridors.responsibility import (
    EMPLOYER_ABSENT,
    is_employee_actionable,
    resolve_responsible_party,
)
from backend.relopass.corridors.scheduler import (
    classify_step_flags,
    compute_deadlines,
    schedule_steps,
    triage_summary,
)

PATHWAY = (
    Path(__file__).resolve().parents[2]
    / "corridors/NO_FR/pathways/RETURNING_EEA_CITIZEN_2026/v1.yaml"
)
ANCHOR = "A0_DEPART_NO"
TODAY = date(2026, 7, 13)
DEPARTED_DAYS_AGO = 45


@pytest.fixture(scope="module")
def corridor():
    return load_corridor(PATHWAY)


@pytest.fixture(scope="module")
def steps(corridor):
    return corridor.step_graph


@pytest.fixture(scope="module")
def flags(steps):
    departure = TODAY - timedelta(days=DEPARTED_DAYS_AGO)
    schedule = schedule_steps(steps, departure, actual_completions={ANCHOR: departure})
    deadlines = compute_deadlines(steps, departure, schedule=schedule)
    return classify_step_flags(
        steps,
        schedule=schedule,
        deadlines=deadlines,
        today=TODAY,
        completed_step_ids={ANCHOR},
    )


def _by_id(steps):
    return {s.step_id: s for s in steps}


class TestCorridorLoads:
    def test_the_corridor_loads_and_topo_sorts(self, corridor, flags):
        # A cycle in the step graph would raise in schedule_steps.
        assert corridor.corridor_id == "NO_FR_RETURNING_EEA_2026"
        assert flags  # scheduling succeeded

    def test_it_is_deterministic(self, steps):
        """Same inputs, same ordered step list — ten times over. No LLM variance
        in WHICH requirements appear."""
        departure = TODAY - timedelta(days=DEPARTED_DAYS_AGO)
        runs = []
        for _ in range(10):
            sched = schedule_steps(steps, departure, actual_completions={ANCHOR: departure})
            dl = compute_deadlines(steps, departure, schedule=sched)
            f = classify_step_flags(
                steps, schedule=sched, deadlines=dl, today=TODAY,
                completed_step_ids={ANCHOR},
            )
            runs.append(sorted(f.items()))
        assert all(r == runs[0] for r in runs)


class TestGate1AntiSilence:
    """A correct answer of 'none' must be STATED, not implied by omission."""

    def test_immigration_is_a_stated_nothing_to_do(self, steps, flags):
        imm = _by_id(steps)["C2_IMMIGRATION_RIGHT_OF_RETURN"]
        assert imm.outcome_type == "nothing_to_do"
        assert flags["C2_IMMIGRATION_RIGHT_OF_RETURN"] == "confirmed"

    def test_immigration_is_present_not_absent(self, steps):
        # The failure mode this guards: immigration simply missing from the graph.
        assert "C2_IMMIGRATION_RIGHT_OF_RETURN" in _by_id(steps)

    def test_the_confirmation_carries_a_reason(self, steps):
        imm = _by_id(steps)["C2_IMMIGRATION_RIGHT_OF_RETURN"]
        # The name states the answer; the citation states why.
        assert "no visa" in imm.name.lower()
        assert imm.cite == "EU_FREE_MOVEMENT"

    def test_all_nothing_to_do_items_confirm_positively(self, steps, flags):
        confirmations = [s for s in steps if s.outcome_type == "nothing_to_do"]
        # Immigration, population registration, D-number N/A.
        assert len(confirmations) == 3
        for s in confirmations:
            assert flags[s.step_id] == "confirmed", f"{s.step_id} must never read as risk"


class TestGate2PendingNotAsserted:
    """Two-sided: present-as-pending AND absent-as-fact."""

    COUNSEL_QUESTIONS = [
        "Q1_TREATY_ART15_ALLOCATION",
        "Q2_NO_SOURCE_TAXATION",
        "Q3_NO_COVERAGE_CLOSURE",
        "Q4_URSSAF_MECHANICS",
        "Q5_PUMA_VS_WORKER_AFFILIATION",
    ]

    def test_all_five_counsel_questions_are_present(self, steps):
        ids = _by_id(steps)
        for q in self.COUNSEL_QUESTIONS:
            assert q in ids, f"{q} must be surfaced, not dropped"

    def test_all_five_are_marked_PENDING_not_HARD(self, steps):
        ids = _by_id(steps)
        for q in self.COUNSEL_QUESTIONS:
            assert ids[q].assertion == "PENDING", f"{q} must not be asserted as fact"

    def test_all_five_route_to_a_professional(self, steps):
        ids = _by_id(steps)
        for q in self.COUNSEL_QUESTIONS:
            assert ids[q].advice_boundary == "route_to_professional"

    def test_nothing_pending_is_dressed_up_as_a_hard_action(self, steps):
        # The absent-as-fact half: no PENDING step may masquerade as settled
        # guidance the employee should just go and do.
        for s in steps:
            if s.assertion == "PENDING":
                assert s.advice_boundary == "route_to_professional", (
                    f"{s.step_id} is unresolved but reads as actionable advice"
                )


class TestGate3AdviceLineRouting:
    def test_personalised_tax_determination_routes_out(self, steps):
        # His Norwegian tax-residence STATUS is a personalised determination.
        assert _by_id(steps)["A3_NO_TAX_RESIDENCE"].advice_boundary == "route_to_professional"

    def test_employer_duty_routes_out(self, steps):
        assert _by_id(steps)["B3_EMPLOYER_URSSAF"].advice_boundary == "route_to_professional"


class TestGate4VerifiedAsHard:
    """Every fixture HARD row asserts at its stated value."""

    @pytest.mark.parametrize("step_id", [
        "B1_APPLICABLE_LEGISLATION",   # applicable legislation = FRANCE
        "B2_A1_FROM_FRANCE",           # A1 issued by France, not Norway
        "A5_FOLKETRYGDEN_EXIT",        # exits folketrygden despite NO employer
        "B3_EMPLOYER_URSSAF",          # the foreign employer's duty exists
        "A3_NO_TAX_RESIDENCE",         # NO residency does NOT end on the move
    ])
    def test_hard_rows_are_asserted(self, steps, step_id):
        assert _by_id(steps)[step_id].assertion == "HARD"

    def test_the_fixture_correction_is_encoded(self, steps):
        """An external draft said Norwegian tax residence ceases around departure.
        The fixture says it does NOT end on the physical move. The fixture wins."""
        step = _by_id(steps)["A3_NO_TAX_RESIDENCE"]
        assert "does not end" in step.name.lower()
        assert step.cite == "NO_TAX_EMIGRATION"


class TestEmployerAbsent:
    """No employer is engaged on this case."""

    def test_employer_obligations_surface_as_absent(self, steps):
        ids = _by_id(steps)
        for step_id in ("B3_EMPLOYER_URSSAF", "B4_PE_RISK"):
            resolved = resolve_responsible_party(
                ids[step_id].responsible_party, employer_engaged=False
            )
            assert resolved == EMPLOYER_ABSENT

    def test_they_never_become_employee_checkboxes(self, steps):
        ids = _by_id(steps)
        for step_id in ("B3_EMPLOYER_URSSAF", "B4_PE_RISK"):
            resolved = resolve_responsible_party(
                ids[step_id].responsible_party, employer_engaged=False
            )
            assert not is_employee_actionable(resolved), (
                f"{step_id} is the employer's — the employee cannot discharge it"
            )


class TestRetrospectiveTriage:
    """He left 45 days ago. The engine must be able to say he is late."""

    def test_the_folkeregister_window_has_elapsed(self, flags):
        # 8-day window, 45 days ago, not done.
        assert flags["A1_FOLKEREGISTER"] == "red_late"

    def test_the_triage_band_has_something_red_and_something_confirmed(self, flags):
        counts = triage_summary(flags)
        assert counts["red_late"] >= 1
        assert counts["confirmed"] >= 2
        assert counts["blocked"] >= 1

    def test_non_obvious_traps_are_flagged(self, steps):
        non_obvious = {s.step_id for s in steps if s.non_obvious}
        # The ones a mover would never think to look for.
        assert "A2_PRESERVE_BANKID" in non_obvious       # sequencing trap
        assert "D1_HOUSEHOLD_GOODS" in non_obvious       # EEA != EU customs union
        assert "C1_CPAM" in non_obvious                  # HELFO->CPAM coverage gap
        assert "A5_FOLKETRYGDEN_EXIT" in non_obvious     # exit despite NO employer

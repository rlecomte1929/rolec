"""employer_absent (Gap 4).

The architectural rule under test: an empty HR layer does NOT push its
obligations down onto the employee — it leaves them visibly orphaned.
"""
from __future__ import annotations

import pytest

from backend.relopass.corridors.responsibility import (
    BOTH,
    EMPLOYEE,
    EMPLOYER,
    EMPLOYER_ABSENT,
    is_employee_actionable,
    resolve_responsible_party,
)


class TestUnsupportedMove:
    """employer_engaged = False — the real validation case."""

    def test_employer_step_becomes_employer_absent(self):
        # B2 (URSSAF / Art. 21) is the employer's, but no employer is engaged.
        assert resolve_responsible_party(EMPLOYER, employer_engaged=False) == EMPLOYER_ABSENT

    def test_employer_absent_step_stays_absent(self):
        # B3 (permanent-establishment risk) is authored EMPLOYER_ABSENT.
        assert resolve_responsible_party(EMPLOYER_ABSENT, employer_engaged=False) == EMPLOYER_ABSENT

    def test_orphaned_obligation_is_NOT_reassigned_to_the_employee(self):
        # The load-bearing assertion of this whole module.
        resolved = resolve_responsible_party(EMPLOYER, employer_engaged=False)
        assert resolved != EMPLOYEE
        assert not is_employee_actionable(resolved)

    def test_employee_steps_are_untouched(self):
        assert resolve_responsible_party(EMPLOYEE, employer_engaged=False) == EMPLOYEE
        assert is_employee_actionable(EMPLOYEE)

    def test_both_is_not_downgraded(self):
        # The employee still has their own half to do; collapsing BOTH to
        # EMPLOYER_ABSENT would hide real employee work.
        assert resolve_responsible_party(BOTH, employer_engaged=False) == BOTH
        assert is_employee_actionable(BOTH)


class TestEmployerEngaged:
    def test_employer_step_stays_with_the_employer(self):
        assert resolve_responsible_party(EMPLOYER, employer_engaged=True) == EMPLOYER

    def test_absent_step_is_re_resolved_to_the_employer_not_hidden(self):
        # Engaging an employer makes the obligation theirs to DO — it does not
        # make it disappear. HR inherits a populated list.
        assert resolve_responsible_party(EMPLOYER_ABSENT, employer_engaged=True) == EMPLOYER

    def test_employer_work_never_becomes_an_employee_checkbox(self):
        assert not is_employee_actionable(EMPLOYER)
        assert not is_employee_actionable(EMPLOYER_ABSENT)


class TestTemplateIsNeverRewritten:
    def test_resolution_is_a_pure_function_of_authored_party_and_engagement(self):
        # Toggling engagement round-trips: nothing is lost, so the YAML template
        # never needs mutating.
        for authored in (EMPLOYEE, EMPLOYER, BOTH, EMPLOYER_ABSENT):
            off = resolve_responsible_party(authored, employer_engaged=False)
            on = resolve_responsible_party(authored, employer_engaged=True)
            assert off and on

    @pytest.mark.parametrize("messy", ["employer", "  Employer  ", "EMPLOYER"])
    def test_authored_party_is_case_and_space_insensitive(self, messy):
        assert resolve_responsible_party(messy, employer_engaged=False) == EMPLOYER_ABSENT

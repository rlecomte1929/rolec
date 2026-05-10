"""
test_s4_family_propagation.py

S4 Spike validation — family workstream propagation and dependency gating.

Covers:
  - Scenario 2: Camille, Paris→Madrid, couple + 2 children
  - Scenario 4: Lucia, Madrid→Amsterdam, permanent transfer + non-EU partner
  - Adrien (Scenario 1): single employee — no family workstreams
  - Dependency gating: spouse/child questions only shown when appropriate

Run with:
    pytest backend/tests/test_s4_family_propagation.py -v
"""
import pytest
from backend.services.family_propagation import FamilyPropagator, WorkstreamRequirement
from backend.agents.orchestrator import IntakeOrchestrator
from backend.question_bank import get_question_by_id


# ─── shared fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def propagator():
    return FamilyPropagator()


@pytest.fixture
def orchestrator():
    return IntakeOrchestrator()


# ─── Scenario 2: Camille — Paris → Madrid, couple + 2 children ──────────────

class TestScenario2CamilleFamily:
    """
    Camille, 38, French. Paris → Madrid. LTA.
    Partner + 2 children. Both Camille and partner are EU nationals.

    Expected:
    - school_enrollment workstream (2 children)
    - NO partner visa workstream (EU partner → free movement)
    - spouse_work_authorization IF partner intends to work
    """

    def test_school_enrollment_generated_for_two_children(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 2,
                "partnerVisaStatus": "eu_citizen",
                "spouseEmploymentIntent": "no",
            },
            destination_country="Spain",
            origin_country="France",
        )
        ids = {r.workstream_id for r in result}
        assert "school_enrollment" in ids

    def test_no_partner_visa_for_eu_partner(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 2,
                "partnerVisaStatus": "eu_citizen",
                "spouseEmploymentIntent": "no",
            },
            destination_country="Spain",
            origin_country="France",
        )
        ids = {r.workstream_id for r in result}
        assert "partner_mvv" not in ids
        assert "partner_family_visa" not in ids
        assert "dependent_visa" not in ids

    def test_spouse_work_authorization_when_partner_wants_to_work(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 2,
                "partnerVisaStatus": "eu_citizen",
                "spouseEmploymentIntent": "yes",
            },
            destination_country="Spain",
            origin_country="France",
        )
        ids = {r.workstream_id for r in result}
        assert "spouse_work_authorization" in ids

    def test_no_spouse_work_authorization_when_partner_not_working(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 2,
                "partnerVisaStatus": "eu_citizen",
                "spouseEmploymentIntent": "no",
            },
            destination_country="Spain",
            origin_country="France",
        )
        ids = {r.workstream_id for r in result}
        assert "spouse_work_authorization" not in ids

    def test_school_enrollment_lead_time_is_reasonable(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={"hasSpouse": False, "childCount": 2},
            destination_country="Spain",
        )
        school = next(r for r in result if r.workstream_id == "school_enrollment")
        assert school.typical_lead_time_weeks >= 8, "School enrollment should have significant lead time"

    def test_school_enrollment_requests_child_ages(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={"hasSpouse": False, "childCount": 1},
            destination_country="Spain",
        )
        school = next(r for r in result if r.workstream_id == "school_enrollment")
        assert "child_ages" in school.additional_questions_required


# ─── Scenario 4: Lucia — Madrid → Amsterdam, permanent + non-EU partner ──────

class TestScenario4LuciaNonEuPartner:
    """
    Lucia, 34, Spanish. Madrid → Amsterdam. Permanent transfer.
    Life partner is non-EU national (no current permit).

    Expected:
    - partner_mvv workstream (Netherlands-specific, non-EU partner)
    - partner_mvv is CRITICAL priority
    - school_enrollment NOT generated (no children)
    """

    def test_partner_mvv_generated_for_non_eu_partner_in_nl(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
                "spouseEmploymentIntent": "unknown",
            },
            destination_country="Netherlands",
            origin_country="Spain",
        )
        ids = {r.workstream_id for r in result}
        assert "partner_mvv" in ids

    def test_partner_mvv_is_critical_priority(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
                "spouseEmploymentIntent": "unknown",
            },
            destination_country="Netherlands",
            origin_country="Spain",
        )
        mvv = next(r for r in result if r.workstream_id == "partner_mvv")
        assert mvv.priority == "critical"

    def test_partner_mvv_lead_time_is_at_least_10_weeks(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Netherlands",
        )
        mvv = next(r for r in result if r.workstream_id == "partner_mvv")
        assert mvv.typical_lead_time_weeks >= 10

    def test_no_school_enrollment_without_children(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Netherlands",
        )
        ids = {r.workstream_id for r in result}
        assert "school_enrollment" not in ids

    def test_partner_with_permit_in_nl_still_gets_mvv(self, propagator):
        """Non-EU partner with a permit from another country still needs NL MVV."""
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_with_permit",
            },
            destination_country="Netherlands",
        )
        ids = {r.workstream_id for r in result}
        assert "partner_mvv" in ids

    def test_eu_partner_does_not_get_mvv(self, propagator):
        """EU partner moving to Netherlands does NOT need an MVV."""
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "eu_citizen",
            },
            destination_country="Netherlands",
        )
        ids = {r.workstream_id for r in result}
        assert "partner_mvv" not in ids


# ─── Scenario 1: Adrien — single, no family workstreams ──────────────────────

class TestScenario1AdrienSingle:
    """
    Single employee. No spouse. No children. No family workstreams expected.
    """

    def test_no_workstreams_for_single_employee(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": False,
                "childCount": 0,
            },
            destination_country="Spain",
            origin_country="Germany",
        )
        assert result == []

    def test_no_workstreams_for_empty_profile(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={},
            destination_country="Spain",
        )
        assert result == []


# ─── Non-EU destination: Singapore / US dependent visa ───────────────────────

class TestNonEuDestinationDependentVisa:
    """
    Covers the case where a partner needs a dependent visa for a non-EU destination
    (Singapore Employment Pass dependent, US L2 visa, etc.).
    """

    def test_dependent_visa_generated_for_sg(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "same_as_employee",
                "spouseEmploymentIntent": "no",
            },
            destination_country="Singapore",
            origin_country="Norway",
        )
        ids = {r.workstream_id for r in result}
        assert "dependent_visa" in ids

    def test_no_mvv_for_singapore_destination(self, propagator):
        result = propagator.get_required_workstreams(
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Singapore",
        )
        ids = {r.workstream_id for r in result}
        assert "partner_mvv" not in ids
        assert "dependent_visa" in ids


# ─── Dependency gating: orchestrator _check_dependencies ────────────────────

class TestDependencyGating:
    """
    Verifies the IntakeOrchestrator._check_dependencies() implementation.
    Spouse/child detail questions must be gated by the new gating questions.
    """

    def test_spouse_name_gated_by_has_spouse(self, orchestrator):
        q_spouse_name = get_question_by_id("q_spouse_name")
        assert q_spouse_name is not None, "q_spouse_name not found in question bank"

        # Profile where has_spouse = False → spouse name should be skipped
        profile_no_spouse = {"family": {"hasSpouse": False}}
        assert not orchestrator._check_dependencies(q_spouse_name, profile_no_spouse)

        # Profile where has_spouse = True → spouse name should appear
        profile_with_spouse = {"family": {"hasSpouse": True}}
        assert orchestrator._check_dependencies(q_spouse_name, profile_with_spouse)

    def test_child1_name_gated_by_child_count(self, orchestrator):
        q = get_question_by_id("q_child1_name")
        assert q is not None

        # No children → blocked
        assert not orchestrator._check_dependencies(q, {"family": {"childCount": "0"}})

        # 1 child → shown
        assert orchestrator._check_dependencies(q, {"family": {"childCount": "1"}})
        assert orchestrator._check_dependencies(q, {"family": {"childCount": "2"}})

    def test_child2_name_only_shown_for_2_plus_children(self, orchestrator):
        q = get_question_by_id("q_child2_name")
        assert q is not None

        # 1 child → blocked (child2 not needed)
        assert not orchestrator._check_dependencies(q, {"family": {"childCount": "1"}})

        # 2+ children → shown
        assert orchestrator._check_dependencies(q, {"family": {"childCount": "2"}})
        assert orchestrator._check_dependencies(q, {"family": {"childCount": "3"}})

    def test_unanswered_prerequisite_blocks_dependent_question(self, orchestrator):
        """If the gate question hasn't been answered, dependent question is not shown."""
        q_spouse_name = get_question_by_id("q_spouse_name")
        # Empty profile — has_spouse not set yet
        assert not orchestrator._check_dependencies(q_spouse_name, {})

    def test_spouse_employment_intent_gated_by_has_spouse(self, orchestrator):
        q = get_question_by_id("q_spouse_employment_intent")
        assert q is not None

        assert not orchestrator._check_dependencies(q, {"family": {"hasSpouse": False}})
        assert orchestrator._check_dependencies(q, {"family": {"hasSpouse": True}})

    def test_partner_visa_status_gated_by_has_spouse(self, orchestrator):
        q = get_question_by_id("q_partner_visa_status")
        assert q is not None

        assert not orchestrator._check_dependencies(q, {"family": {"hasSpouse": False}})
        assert orchestrator._check_dependencies(q, {"family": {"hasSpouse": True}})

    def test_s3_contract_type_question_has_no_dependency(self, orchestrator):
        """q_contract_type is always shown (no dependsOn)."""
        q = get_question_by_id("q_contract_type")
        assert q is not None
        # Always passes regardless of profile state
        assert orchestrator._check_dependencies(q, {})
        assert orchestrator._check_dependencies(q, {"assignment": {"contractType": "lta"}})

    def test_assignment_end_suppressed_for_permanent_transfer(self, orchestrator):
        """q_assignment_end should not show for permanent_transfer (no end date)."""
        q = get_question_by_id("q_assignment_end")
        assert q is not None

        # permanent_transfer → not in the allowed list → suppressed
        assert not orchestrator._check_dependencies(
            q, {"assignment": {"contractType": "permanent_transfer"}}
        )

        # lta → shown
        assert orchestrator._check_dependencies(
            q, {"assignment": {"contractType": "lta"}}
        )


# ─── Task library: S4 task codes present and valid ───────────────────────────

class TestS4TaskLibrary:
    def test_all_s4_task_codes_present(self):
        from backend.relocation_plan_task_library import TASK_BY_CODE
        expected = [
            "school_enrollment_research",
            "school_enrollment_application",
            "spouse_work_authorization",
            "partner_family_visa_application",
            "partner_mvv_application",
            "dependent_visa_application",
        ]
        for code in expected:
            assert code in TASK_BY_CODE, f"Missing task_code: {code}"

    def test_existing_task_codes_unchanged(self):
        from backend.relocation_plan_task_library import TASK_BY_CODE
        original_codes = [
            "confirm_employee_core_profile",
            "confirm_family_details",
            "upload_passport_copy",
            "upload_assignment_letter",
            "verify_destination_route",
            "hr_review_case_data",
            "schedule_immigration_review",
            "prepare_visa_pack",
            "submit_visa_application",
            "book_biometrics",
            "arrange_temporary_housing",
            "arrange_movers",
            "coordinate_relocation_providers",
            "plan_travel",
            "complete_arrival_registration",
            "tax_local_registration",
            "settle_in",
        ]
        for code in original_codes:
            assert code in TASK_BY_CODE, f"Existing task_code was removed: {code}"

    def test_partner_mvv_is_critical(self):
        from backend.relocation_plan_task_library import TASK_BY_CODE
        assert TASK_BY_CODE["partner_mvv_application"].priority == "critical"

    def test_family_tasks_in_correct_phases(self):
        from backend.relocation_plan_task_library import TASK_BY_CODE
        assert TASK_BY_CODE["school_enrollment_research"].phase_key == "pre_departure"
        assert TASK_BY_CODE["school_enrollment_application"].phase_key == "immigration"
        assert TASK_BY_CODE["partner_mvv_application"].phase_key == "immigration"
        assert TASK_BY_CODE["spouse_work_authorization"].phase_key == "immigration"

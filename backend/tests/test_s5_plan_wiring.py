"""
test_s5_plan_wiring.py

S5 Spike validation — wiring of S3/S4 services into plan generation.

Covers:
  - compute_default_milestones(): phase-gating via contract_type
  - compute_default_milestones(): family milestone injection via family_profile
  - _profile_from_wizard_draft(): extraction of S3/S4 fields from wizard draft

Run with:
    pytest backend/tests/test_s5_plan_wiring.py -v
"""
import pytest
from backend.app.services.timeline_service import compute_default_milestones
from backend.services.wizard_draft_mapper import extract_profile_from_wizard_draft as _profile_from_wizard_draft


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _milestone_types(milestones):
    return {m["milestone_type"] for m in milestones}


# ─── Phase-gating via contract_type ──────────────────────────────────────────

class TestPhaseGating:
    """compute_default_milestones() should suppress tasks in inactive phases."""

    def test_no_contract_type_returns_all_defaults(self):
        result = compute_default_milestones(case_id="test-no-ct")
        types = _milestone_types(result)
        # All standard immigration tasks should be present
        assert "task_visa_docs_prep" in types
        assert "task_visa_submit" in types
        assert "task_immigration_review" in types

    def test_domestic_move_suppresses_immigration_tasks(self):
        result = compute_default_milestones(
            case_id="test-domestic",
            contract_type="domestic_move",
        )
        types = _milestone_types(result)
        assert "task_visa_docs_prep" not in types
        assert "task_visa_submit" not in types
        assert "task_immigration_review" not in types
        assert "task_biometrics" not in types

    def test_domestic_move_keeps_pre_departure_tasks(self):
        result = compute_default_milestones(
            case_id="test-domestic-pre",
            contract_type="domestic_move",
        )
        types = _milestone_types(result)
        # Pre-departure tasks should remain
        assert "task_profile_core" in types
        assert "task_family_dependents" in types
        assert "task_passport_upload" in types

    def test_domestic_move_keeps_logistics_and_arrival(self):
        result = compute_default_milestones(
            case_id="test-domestic-logistics",
            contract_type="domestic_move",
        )
        types = _milestone_types(result)
        assert "task_temp_housing" in types
        assert "task_movers_shipment" in types
        assert "task_arrival_registration" in types

    def test_short_term_project_suppresses_logistics(self):
        result = compute_default_milestones(
            case_id="test-stp",
            contract_type="short_term_project",
        )
        types = _milestone_types(result)
        assert "task_movers_shipment" not in types
        assert "task_temp_housing" not in types

    def test_short_term_project_keeps_immigration(self):
        result = compute_default_milestones(
            case_id="test-stp-imm",
            contract_type="short_term_project",
        )
        types = _milestone_types(result)
        assert "task_visa_docs_prep" in types
        assert "task_visa_submit" in types

    def test_lta_keeps_all_standard_phases(self):
        result = compute_default_milestones(
            case_id="test-lta",
            contract_type="lta",
        )
        types = _milestone_types(result)
        assert "task_visa_docs_prep" in types
        assert "task_temp_housing" in types
        assert "task_settling_in" in types

    def test_unknown_contract_type_is_backward_compatible(self):
        result = compute_default_milestones(
            case_id="test-unknown-ct",
            contract_type="unknown",
        )
        types = _milestone_types(result)
        # Should behave the same as no contract_type
        assert "task_visa_docs_prep" in types
        assert "task_temp_housing" in types


# ─── Family milestone injection ───────────────────────────────────────────────

class TestFamilyMilestoneInjection:
    """compute_default_milestones() should inject family workstream milestones."""

    def test_no_family_profile_no_family_milestones(self):
        result = compute_default_milestones(case_id="test-no-family")
        types = _milestone_types(result)
        assert "task_partner_mvv" not in types
        assert "task_school_research" not in types
        assert "task_spouse_work_permit" not in types

    def test_empty_family_profile_no_family_milestones(self):
        result = compute_default_milestones(
            case_id="test-empty-family",
            family_profile={},
        )
        types = _milestone_types(result)
        assert "task_partner_mvv" not in types
        assert "task_school_research" not in types

    def test_nl_non_eu_partner_injects_mvv(self):
        result = compute_default_milestones(
            case_id="test-nl-mvv",
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Netherlands",
        )
        types = _milestone_types(result)
        assert "task_partner_mvv" in types

    def test_nl_mvv_is_critical(self):
        result = compute_default_milestones(
            case_id="test-nl-mvv-crit",
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Netherlands",
        )
        mvv = next(m for m in result if m["milestone_type"] == "task_partner_mvv")
        assert mvv["criticality"] == "critical"

    def test_children_inject_school_milestones(self):
        result = compute_default_milestones(
            case_id="test-school",
            family_profile={
                "hasSpouse": False,
                "childCount": 2,
            },
            destination_country="Spain",
        )
        types = _milestone_types(result)
        assert "task_school_research" in types
        assert "task_school_application" in types

    def test_eu_partner_in_eu_destination_no_mvv(self):
        result = compute_default_milestones(
            case_id="test-eu-no-mvv",
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "eu_citizen",
            },
            destination_country="Netherlands",
        )
        types = _milestone_types(result)
        assert "task_partner_mvv" not in types

    def test_sg_dependent_visa_injected(self):
        result = compute_default_milestones(
            case_id="test-sg-dep",
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "same_as_employee",
            },
            destination_country="Singapore",
        )
        types = _milestone_types(result)
        assert "task_dependent_visa" in types

    def test_spouse_work_intent_injects_work_permit(self):
        result = compute_default_milestones(
            case_id="test-spouse-work",
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "eu_citizen",
                "spouseEmploymentIntent": "yes",
            },
            destination_country="Spain",
        )
        types = _milestone_types(result)
        assert "task_spouse_work_permit" in types

    def test_domestic_move_suppresses_family_immigration_milestones(self):
        """partner_mvv is in the immigration phase — domestic_move should suppress it."""
        result = compute_default_milestones(
            case_id="test-domestic-family",
            contract_type="domestic_move",
            family_profile={
                "hasSpouse": True,
                "childCount": 0,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Netherlands",
        )
        types = _milestone_types(result)
        assert "task_partner_mvv" not in types

    def test_family_milestones_not_duplicated(self):
        result = compute_default_milestones(
            case_id="test-no-dupes",
            family_profile={
                "hasSpouse": False,
                "childCount": 1,
            },
            destination_country="Spain",
        )
        school_types = [m["milestone_type"] for m in result if m["milestone_type"] == "task_school_research"]
        assert len(school_types) == 1, "task_school_research should appear exactly once"

    def test_standard_milestones_still_present_with_family(self):
        """Family injection must not displace the standard task list."""
        result = compute_default_milestones(
            case_id="test-family-plus-std",
            family_profile={
                "hasSpouse": True,
                "childCount": 1,
                "partnerVisaStatus": "non_eu_no_permit",
            },
            destination_country="Netherlands",
        )
        types = _milestone_types(result)
        assert "task_profile_core" in types
        assert "task_passport_upload" in types
        assert "task_visa_docs_prep" in types
        assert "task_partner_mvv" in types
        assert "task_school_research" in types


# ─── _profile_from_wizard_draft() S3/S4 extraction ───────────────────────────

class TestProfileFromWizardDraftS3S4:
    """_profile_from_wizard_draft() must extract contract_type and family fields."""

    # ── contract_type (S3) ───────────────────────────────────────────────────

    def test_contract_type_from_assignment_context(self):
        draft = {"assignmentContext": {"contractType": "lta"}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("contract_type") == "lta"

    def test_contract_type_from_orchestrator_assignment_section(self):
        """Orchestrator stores answers at draft.assignment.contractType."""
        draft = {"assignment": {"contractType": "permanent_transfer"}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("contract_type") == "permanent_transfer"

    def test_contract_type_orchestrator_takes_precedence(self):
        draft = {
            "assignment": {"contractType": "domestic_move"},
            "assignmentContext": {"contractType": "lta"},
        }
        result = _profile_from_wizard_draft(draft)
        assert result.get("contract_type") == "domestic_move"

    def test_no_contract_type_absent_from_profile(self):
        draft = {"relocationBasics": {"destCountry": "Spain"}}
        result = _profile_from_wizard_draft(draft)
        assert "contract_type" not in result

    # ── family (S4) — orchestrator path ─────────────────────────────────────

    def test_family_has_spouse_from_orchestrator_path(self):
        draft = {"family": {"hasSpouse": True}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("family", {}).get("hasSpouse") is True

    def test_family_child_count_from_orchestrator_path(self):
        draft = {"family": {"hasSpouse": False, "childCount": 2}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("family", {}).get("childCount") == 2

    def test_family_partner_visa_status_extracted(self):
        draft = {"family": {
            "hasSpouse": True,
            "childCount": 0,
            "partnerVisaStatus": "non_eu_no_permit",
        }}
        result = _profile_from_wizard_draft(draft)
        assert result["family"]["partnerVisaStatus"] == "non_eu_no_permit"

    def test_family_spouse_employment_intent_extracted(self):
        draft = {"family": {
            "hasSpouse": True,
            "spouseEmploymentIntent": "yes",
        }}
        result = _profile_from_wizard_draft(draft)
        assert result["family"]["spouseEmploymentIntent"] == "yes"

    # ── family — wizard path (familyMembers) ─────────────────────────────────

    def test_family_has_spouse_from_wizard_marital_status(self):
        draft = {"familyMembers": {"maritalStatus": "married"}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("family", {}).get("hasSpouse") is True

    def test_family_has_spouse_false_for_single(self):
        draft = {"familyMembers": {"maritalStatus": "single"}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("family", {}).get("hasSpouse") is False

    def test_family_child_count_from_wizard_children_list(self):
        draft = {"familyMembers": {"children": [{"fullName": "Alice"}, {"fullName": "Bob"}]}}
        result = _profile_from_wizard_draft(draft)
        assert result.get("family", {}).get("childCount") == 2

    # ── no family section → no family key ────────────────────────────────────

    def test_no_family_data_no_family_key(self):
        draft = {"relocationBasics": {"destCountry": "France"}}
        result = _profile_from_wizard_draft(draft)
        assert "family" not in result

    # ── existing fields preserved ─────────────────────────────────────────────

    def test_existing_basics_still_extracted(self):
        draft = {
            "relocationBasics": {"originCountry": "France", "destCountry": "Spain"},
            "assignment": {"contractType": "lta"},
            "family": {"hasSpouse": True, "childCount": 1},
        }
        result = _profile_from_wizard_draft(draft)
        assert result["origin_country"] == "France"
        assert result["destination_country"] == "Spain"
        assert result["contract_type"] == "lta"
        assert result["family"]["hasSpouse"] is True
        assert result["family"]["childCount"] == 1

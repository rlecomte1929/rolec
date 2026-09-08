"""
test_s3_scenario_classification.py

S3 Spike validation tests — scenario-based classification and phase gating.

Tests the 8 persona scenarios from the ReloPass audit report against the
extended classify_case() function and the plan_scope module.

Run with:
    pytest backend/tests/test_s3_scenario_classification.py -v

No database connections required — all pure unit tests.
"""
import pytest
from backend.app.services.relocation_classifier import classify_case, CaseClassification
from backend.app.services.plan_scope import (
    active_phases_for_case_type,
    active_phases_for_classification,
    immigration_required,
    plan_scope_summary,
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_profile(**kwargs) -> dict:
    """Build a minimal profile dict with sensible defaults."""
    return {
        "origin_country": kwargs.get("origin_country", "France"),
        "destination_country": kwargs.get("destination_country", "Spain"),
        "employment_type": kwargs.get("employment_type", "employee"),
        "contract_type": kwargs.get("contract_type"),
        "works_remote": kwargs.get("works_remote"),
        "employer_country": kwargs.get("employer_country"),
        "move_date": kwargs.get("move_date", "2026-09-01"),
    }


def classify(profile: dict) -> CaseClassification:
    missing = [k for k, v in profile.items() if v is None]
    return classify_case(profile, missing)


# ─── Scenario 8: Valentine — Paris → Lyon, domestic move ─────────────────────

class TestScenario8Valentine:
    """
    Valentine, 29, French. Paris → Lyon.
    Domestic move within France. No immigration. No border crossing.

    P0 exit gate: this is the simplest suppression test. If domestic_move
    does not suppress immigration, the discriminator is broken.
    """

    def test_case_type_is_domestic_move(self):
        profile = make_profile(
            origin_country="France",
            destination_country="France",
            contract_type="domestic_move",
        )
        result = classify(profile)
        assert result.case_type == "domestic_move"

    def test_move_type_is_domestic(self):
        profile = make_profile(
            origin_country="France",
            destination_country="France",
            contract_type="domestic_move",
        )
        result = classify(profile)
        assert result.move_type == "domestic"

    def test_immigration_not_required(self):
        assert not immigration_required("domestic_move")

    def test_immigration_risk_flag_set(self):
        profile = make_profile(
            origin_country="France",
            destination_country="France",
            contract_type="domestic_move",
        )
        result = classify(profile)
        assert "immigration_not_required" in result.risk_flags

    def test_active_phases_excludes_immigration(self):
        phases = active_phases_for_case_type("domestic_move")
        assert "immigration" not in phases

    def test_active_phases_includes_logistics_and_arrival(self):
        phases = active_phases_for_case_type("domestic_move")
        assert "logistics" in phases
        assert "arrival" in phases
        assert "post_arrival" in phases
        assert "pre_departure" in phases

    def test_active_phases_from_classification(self):
        profile = make_profile(
            origin_country="France",
            destination_country="France",
            contract_type="domestic_move",
        )
        result = classify(profile)
        phases = active_phases_for_classification(result)
        assert "immigration" not in phases
        assert len(phases) == 4  # pre_departure, logistics, arrival, post_arrival

    def test_same_country_auto_detection_without_contract_type(self):
        """
        If contract_type is not set but origin == destination,
        move_type should still resolve to 'domestic' (legacy path safety).
        """
        profile = make_profile(
            origin_country="France",
            destination_country="France",
            contract_type=None,
            employment_type="employee",
        )
        result = classify(profile)
        assert result.move_type == "domestic"


# ─── Scenario 5: Anders — Oslo → Singapore, short-term project (3 months) ───

class TestScenario5Anders:
    """
    Anders, 27, Norwegian. Oslo → Singapore.
    Short-term project, 3 months. Single.

    Expected: short_term_project classification, reduced plan scope
    (immigration + arrival only — no full logistics or post_arrival).
    """

    def test_case_type_is_short_term_project(self):
        profile = make_profile(
            origin_country="Norway",
            destination_country="Singapore",
            contract_type="short_term_project",
        )
        result = classify(profile)
        assert result.case_type == "short_term_project"

    def test_move_type_is_international(self):
        profile = make_profile(
            origin_country="Norway",
            destination_country="Singapore",
            contract_type="short_term_project",
        )
        result = classify(profile)
        assert result.move_type == "international"

    def test_immigration_is_required(self):
        # Short-term project still needs immigration check (EP vs STVP for SG)
        assert immigration_required("short_term_project")

    def test_short_term_risk_flag_set(self):
        profile = make_profile(
            origin_country="Norway",
            destination_country="Singapore",
            contract_type="short_term_project",
        )
        result = classify(profile)
        assert "short_term_may_be_visa_free" in result.risk_flags

    def test_active_phases_excludes_logistics_and_post_arrival(self):
        phases = active_phases_for_case_type("short_term_project")
        assert "logistics" not in phases
        assert "post_arrival" not in phases

    def test_active_phases_includes_immigration_and_arrival(self):
        phases = active_phases_for_case_type("short_term_project")
        assert "pre_departure" in phases
        assert "immigration" in phases
        assert "arrival" in phases
        assert len(phases) == 3

    def test_plan_scope_summary(self):
        summary = plan_scope_summary("short_term_project")
        assert summary["immigration_required"] is True
        assert summary["logistics_included"] is False
        assert summary["post_arrival_included"] is False
        assert set(summary["suppressed_phases"]) == {"logistics", "post_arrival"}


# ─── Scenario 1: Adrien — Berlin → Barcelona, LTA 18 months ─────────────────

class TestScenario1Adrien:
    """
    Adrien, 31, French. Berlin → Barcelona.
    LTA, 18 months. Single. EU free movement.

    Expected: lta classification, all 5 phases active, work_permit_required flag.
    """

    def test_case_type_is_lta(self):
        profile = make_profile(
            origin_country="Germany",
            destination_country="Spain",
            contract_type="lta",
        )
        result = classify(profile)
        assert result.case_type == "lta"

    def test_all_phases_active(self):
        phases = active_phases_for_case_type("lta")
        assert phases == ["pre_departure", "immigration", "logistics", "arrival", "post_arrival"]

    def test_work_permit_required_flag(self):
        profile = make_profile(
            origin_country="Germany",
            destination_country="Spain",
            contract_type="lta",
        )
        result = classify(profile)
        assert "work_permit_required" in result.risk_flags

    def test_timeline_ready_flag(self):
        profile = make_profile(
            origin_country="Germany",
            destination_country="Spain",
            contract_type="lta",
            move_date="2026-10-01",
        )
        result = classify(profile)
        assert "timeline_ready" in result.risk_flags


# ─── Scenario 4: Lucia — Madrid → Amsterdam, permanent transfer ──────────────

class TestScenario4Lucia:
    """
    Lucia, 34, Spanish. Madrid → Amsterdam.
    Permanent transfer (no return date). Non-EU partner.

    Expected: permanent_transfer classification, all phases active.
    """

    def test_case_type_is_permanent_transfer(self):
        profile = make_profile(
            origin_country="Spain",
            destination_country="Netherlands",
            contract_type="permanent_transfer",
        )
        result = classify(profile)
        assert result.case_type == "permanent_transfer"

    def test_all_phases_active(self):
        phases = active_phases_for_case_type("permanent_transfer")
        assert phases == ["pre_departure", "immigration", "logistics", "arrival", "post_arrival"]

    def test_move_type_is_international(self):
        profile = make_profile(
            origin_country="Spain",
            destination_country="Netherlands",
            contract_type="permanent_transfer",
        )
        result = classify(profile)
        assert result.move_type == "international"


# ─── Scenario 7: Camille month 30 — repatriation ─────────────────────────────

class TestScenario7CamilleRepat:
    """
    Camille, 38, French. Returning to France from Madrid. Month 30 of 18-month LTA.

    Expected: repatriation classification. No immigration phase. admin_reinstatement instead.
    """

    def test_case_type_is_repatriation(self):
        profile = make_profile(
            origin_country="Spain",
            destination_country="France",
            contract_type="repatriation",
        )
        result = classify(profile)
        assert result.case_type == "repatriation"

    def test_move_type_is_return(self):
        profile = make_profile(
            origin_country="Spain",
            destination_country="France",
            contract_type="repatriation",
        )
        result = classify(profile)
        assert result.move_type == "return"

    def test_immigration_not_in_phases(self):
        phases = active_phases_for_case_type("repatriation")
        assert "immigration" not in phases

    def test_admin_reinstatement_in_phases(self):
        phases = active_phases_for_case_type("repatriation")
        assert "admin_reinstatement" in phases


# ─── Backward-compatibility: legacy employment_type path ─────────────────────

class TestLegacyBackwardCompatibility:
    """
    Ensure existing code that calls classify_case() with only employment_type
    (no contract_type) continues to work correctly.
    """

    def test_employee_sponsored_still_works(self):
        profile = make_profile(
            origin_country="France",
            destination_country="UK",
            contract_type=None,
            employment_type="employee",
            works_remote=False,
        )
        result = classify(profile)
        assert result.case_type == "employee_sponsored"

    def test_remote_worker_still_works(self):
        profile = make_profile(
            contract_type=None,
            employment_type="employee",
            works_remote=True,
        )
        result = classify(profile)
        assert result.case_type == "remote_worker"

    def test_student_still_works(self):
        profile = make_profile(
            contract_type=None,
            employment_type="student",
        )
        result = classify(profile)
        assert result.case_type == "student"

    def test_unknown_still_works(self):
        profile = make_profile(
            contract_type=None,
            employment_type=None,
        )
        result = classify(profile)
        assert result.case_type == "unknown"

    def test_active_phases_defaults_to_all_for_employee_sponsored(self):
        profile = make_profile(
            contract_type=None,
            employment_type="employee",
            works_remote=False,
        )
        result = classify(profile)
        phases = active_phases_for_classification(result)
        assert "immigration" in phases
        assert len(phases) == 5

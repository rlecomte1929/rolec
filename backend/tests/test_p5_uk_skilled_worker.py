"""
test_p5_uk_skilled_worker.py — P5: UK Skilled Worker visa pathway tests.

Covers (target: ~50 tests):

  Regime detection:
    - UK destinations resolve to uk_skilled_worker regime
    - US/Japan/EU/domestic not affected
    - UK regime has priority="critical", requires_employer_petition=True
    - UK regime returns 5 task codes
    - UK regime lead time is 8 weeks

  Task codes — relocation_plan_task_library.py:
    - All 5 UK task codes exist in TASK_BY_CODE
    - uk_cos_request is phase=immigration, owner=hr, priority=critical
    - uk_visa_application depends on uk_cos_request
    - uk_brp_collection is phase=arrival
    - uk_right_to_work_check depends on uk_brp_collection, phase=post_arrival

  Milestone specs — timeline_service.py:
    - uk_skilled_worker key exists in _REGIME_MILESTONE_SPECS
    - Has 5 milestone entries
    - task_uk_cos_request offset >= 60 days (before move)
    - task_uk_brp_collection offset == 0 (arrival day)
    - task_uk_right_to_work_check offset < 0 (after arrival)

  Exception checks — ExceptionRequestService:
    - No sponsor licence (None) → no_sponsoring_entity blocker
    - Sponsor licence explicitly False → no_sponsoring_entity blocker
    - Sponsor licence True → no no_sponsoring_entity flag
    - No points confirmed (None) → points_threshold_unconfirmed warning
    - Points threshold False → points_threshold_unconfirmed warning
    - Points threshold True → no points_threshold_unconfirmed flag
    - Timeline 4 weeks → timeline_breach blocker (< 8/2=4, edge case)
    - Timeline 5 weeks → timeline_breach warning (< 8 weeks)
    - Timeline 10 weeks → no timeline_breach
    - Cost over $150k → cost_threshold warning (cross-regime)
    - Cost under threshold → no cost_threshold
    - Profile all-clear → no flags

  Question bank — presence and structure:
    - q_uk_sponsor_licence_confirmed in QUESTION_BANK
    - q_uk_points_threshold_confirmed in QUESTION_BANK
    - Both have non-empty whyThisMatters
    - Both mapsTo assignment.uk*
    - Both gated on q_destination_region == "united_kingdom"
    - Both are boolean type

  Orchestrator gating (dependsOn evaluation):
    - UK questions shown when destination_region=united_kingdom
    - UK questions NOT shown for united_states destination
    - UK questions NOT shown for japan destination
    - UK questions NOT shown for eu_eea destination
    - UK questions NOT shown for short_term_project contract type

  wizard_draft_mapper.py — P5 field extraction:
    - ukSponsorLicenceConfirmed True → uk_sponsor_licence_confirmed True
    - ukSponsorLicenceConfirmed False → uk_sponsor_licence_confirmed False
    - ukSponsorLicenceConfirmed "true" (string) → True
    - ukSponsorLicenceConfirmed absent → key not in output
    - ukPointsThresholdConfirmed True → uk_points_threshold_confirmed True
    - ukPointsThresholdConfirmed False → uk_points_threshold_confirmed False
    - ukPointsThresholdConfirmed absent → key not in output

  End-to-end: wizard draft → profile → exception flags:
    - Marcus draft (UK, no sponsor licence) → no_sponsoring_entity blocker
    - Marcus draft (UK, licence=True, points=True, 12wk) → no flags
    - Marcus draft (UK, licence=True, points=False, 12wk) → points warning
    - Marcus draft (UK, licence=True, points=True, 3wk) → timeline_breach blocker
    - Non-UK draft → no UK-specific flags
"""
from __future__ import annotations

import sys
import os
from typing import Any, Dict, List

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.question_bank import QUESTION_BANK, P4_QUESTIONS, get_question_by_id
from backend.services.wizard_draft_mapper import extract_profile_from_wizard_draft
from backend.services.immigration_regime import ImmigrationRegimeRouter
from backend.services.exception_request_service import ExceptionRequestService, ExceptionFlag

# We access _REGIME_MILESTONE_SPECS from timeline_service directly (it's a module-level dict).
from backend.app.services import timeline_service as _ts

router = ImmigrationRegimeRouter()
svc = ExceptionRequestService()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _q(qid: str):
    q = get_question_by_id(qid)
    assert q is not None, f"Question {qid!r} not found in QUESTION_BANK"
    return q


def _flag_types(flags: List[ExceptionFlag]) -> List[str]:
    return [f.exception_type for f in flags]


def _flag_severities(flags: List[ExceptionFlag]) -> Dict[str, str]:
    return {f.exception_type: f.severity for f in flags}


def _uk_regime(destination: str = "United Kingdom", nationality: str = "Indian",
               contract_type: str = "lta"):
    return router.detect_regime(
        nationality=nationality,
        destination_country=destination,
        origin_country="India",
        contract_type=contract_type,
    )


def _evaluate_uk_questions(profile: Dict[str, Any]) -> Dict[str, bool]:
    """Check which UK questions pass dependsOn for a given in-flight profile."""
    from backend.agents.orchestrator import IntakeOrchestrator
    orch = IntakeOrchestrator()
    uk_qids = {"q_uk_sponsor_licence_confirmed", "q_uk_points_threshold_confirmed"}
    return {
        q.id: orch._check_dependencies(q, profile)
        for q in QUESTION_BANK
        if q.id in uk_qids
    }


def _profile_for(contract_type: str, destination_region: str = None) -> Dict[str, Any]:
    profile: Dict[str, Any] = {"assignment": {"contractType": contract_type}}
    if destination_region:
        profile["assignment"]["destinationRegion"] = destination_region
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# 1. Regime detection
# ─────────────────────────────────────────────────────────────────────────────

class TestUKRegimeDetection:

    @pytest.mark.parametrize("dest", [
        "United Kingdom", "uk", "UK", "Great Britain", "England", "Scotland",
        "Wales", "Northern Ireland",
    ])
    def test_uk_destinations_map_to_uk_regime(self, dest):
        r = router.detect_regime(destination_country=dest, origin_country="India",
                                 nationality="Indian", contract_type="lta")
        assert r.regime_id == "uk_skilled_worker", (
            f"{dest!r} should map to uk_skilled_worker, got {r.regime_id!r}"
        )

    def test_us_destination_is_not_uk_regime(self):
        r = router.detect_regime(destination_country="United States", nationality="British",
                                 origin_country="UK", contract_type="lta")
        assert r.regime_id == "us_l1b"

    def test_japan_destination_is_not_uk_regime(self):
        r = router.detect_regime(destination_country="Japan", nationality="British",
                                 origin_country="UK", contract_type="lta")
        assert r.regime_id == "japan_coe"

    def test_eu_national_to_eu_is_not_uk_regime(self):
        r = router.detect_regime(destination_country="France", nationality="Germany",
                                 origin_country="Germany", contract_type="lta")
        assert r.regime_id == "eu_free_movement"

    def test_domestic_uk_move_is_domestic(self):
        r = router.detect_regime(destination_country="United Kingdom",
                                 origin_country="United Kingdom", nationality="British",
                                 contract_type="lta")
        assert r.regime_id == "domestic"

    def test_uk_regime_is_critical_priority(self):
        r = _uk_regime()
        assert r.priority == "critical"

    def test_uk_regime_requires_employer_petition(self):
        r = _uk_regime()
        assert r.requires_employer_petition is True

    def test_uk_regime_has_five_task_codes(self):
        r = _uk_regime()
        assert len(r.task_codes) == 5

    def test_uk_regime_task_codes_are_correct(self):
        r = _uk_regime()
        expected = {
            "uk_cos_request",
            "uk_visa_application",
            "uk_biometric_appointment",
            "uk_brp_collection",
            "uk_right_to_work_check",
        }
        assert set(r.task_codes) == expected

    def test_uk_regime_lead_time_is_8_weeks(self):
        r = _uk_regime()
        assert r.typical_lead_time_weeks == 8


# ─────────────────────────────────────────────────────────────────────────────
# 2. Task codes — relocation_plan_task_library.py
# ─────────────────────────────────────────────────────────────────────────────

class TestUKTaskCodes:

    @pytest.fixture(scope="class")
    def task_lib(self):
        from backend.relocation_plan_task_library import TASK_BY_CODE
        return TASK_BY_CODE

    def test_all_uk_task_codes_in_library(self, task_lib):
        for code in ("uk_cos_request", "uk_visa_application", "uk_biometric_appointment",
                     "uk_brp_collection", "uk_right_to_work_check"):
            assert code in task_lib, f"task_code {code!r} missing from TASK_BY_CODE"

    def test_uk_cos_request_is_hr_owned(self, task_lib):
        entry = task_lib["uk_cos_request"]
        assert entry.default_owner == "hr"

    def test_uk_cos_request_is_immigration_phase(self, task_lib):
        entry = task_lib["uk_cos_request"]
        assert entry.phase_key == "immigration"

    def test_uk_cos_request_is_critical(self, task_lib):
        entry = task_lib["uk_cos_request"]
        assert entry.priority == "critical"

    def test_uk_visa_application_depends_on_cos(self, task_lib):
        entry = task_lib["uk_visa_application"]
        assert "uk_cos_request" in entry.depends_on

    def test_uk_visa_application_is_employee_owned(self, task_lib):
        entry = task_lib["uk_visa_application"]
        assert entry.default_owner == "employee"

    def test_uk_brp_collection_is_arrival_phase(self, task_lib):
        entry = task_lib["uk_brp_collection"]
        assert entry.phase_key == "arrival"

    def test_uk_right_to_work_check_is_post_arrival(self, task_lib):
        entry = task_lib["uk_right_to_work_check"]
        assert entry.phase_key == "post_arrival"

    def test_uk_right_to_work_depends_on_brp(self, task_lib):
        entry = task_lib["uk_right_to_work_check"]
        assert "uk_brp_collection" in entry.depends_on

    def test_uk_right_to_work_is_hr_owned(self, task_lib):
        entry = task_lib["uk_right_to_work_check"]
        assert entry.default_owner == "hr"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Milestone specs — timeline_service.py
# ─────────────────────────────────────────────────────────────────────────────

class TestUKMilestoneSpecs:

    @pytest.fixture(scope="class")
    def uk_specs(self):
        specs = _ts._REGIME_MILESTONE_SPECS.get("uk_skilled_worker")
        assert specs is not None, "uk_skilled_worker missing from _REGIME_MILESTONE_SPECS"
        return specs

    def test_uk_specs_has_five_entries(self, uk_specs):
        assert len(uk_specs) == 5

    def test_cos_request_milestone_present(self, uk_specs):
        types = {s[0] for s in uk_specs}
        assert "task_uk_cos_request" in types

    def test_cos_request_offset_at_least_60_days(self, uk_specs):
        cos = next(s for s in uk_specs if s[0] == "task_uk_cos_request")
        days_before_move = cos[5]
        assert days_before_move >= 60, (
            f"CoS request should be ≥60 days before move, got {days_before_move}"
        )

    def test_brp_collection_is_arrival_day(self, uk_specs):
        brp = next(s for s in uk_specs if s[0] == "task_uk_brp_collection")
        assert brp[5] == 0, f"BRP collection should be day 0, got {brp[5]}"

    def test_right_to_work_is_after_arrival(self, uk_specs):
        rtw = next(s for s in uk_specs if s[0] == "task_uk_right_to_work_check")
        assert rtw[5] < 0, f"Right-to-work check should be after arrival (negative days), got {rtw[5]}"

    def test_visa_application_is_before_biometric(self, uk_specs):
        # visa application should have more days_before_move than biometric
        visa = next(s for s in uk_specs if s[0] == "task_uk_visa_application")
        bio = next(s for s in uk_specs if s[0] == "task_uk_biometric_appointment")
        assert visa[5] > bio[5], "Visa application must come before biometric appointment"

    def test_all_immigration_steps_are_critical(self, uk_specs):
        for spec in uk_specs:
            _, _, _, criticality, _, _ = spec
            assert criticality == "critical", f"All UK Skilled Worker specs should be critical; {spec[0]} is {criticality!r}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Exception checks — ExceptionRequestService
# ─────────────────────────────────────────────────────────────────────────────

class TestUKExceptionChecks:

    def _eval(self, profile: Dict[str, Any]) -> List[ExceptionFlag]:
        regime = _uk_regime()
        return svc.evaluate_case(profile=profile, regime=regime)

    def test_no_sponsor_licence_none_is_blocker(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": None})
        sev = _flag_severities(flags)
        assert "no_sponsoring_entity" in sev
        assert sev["no_sponsoring_entity"] == "blocker"

    def test_sponsor_licence_absent_from_profile_is_blocker(self):
        # Key completely missing from profile (not asked yet)
        flags = self._eval({})
        sev = _flag_severities(flags)
        assert "no_sponsoring_entity" in sev
        assert sev["no_sponsoring_entity"] == "blocker"

    def test_sponsor_licence_false_is_blocker(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": False})
        sev = _flag_severities(flags)
        assert "no_sponsoring_entity" in sev
        assert sev["no_sponsoring_entity"] == "blocker"

    def test_sponsor_licence_true_clears_flag(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 20})
        types = _flag_types(flags)
        assert "no_sponsoring_entity" not in types

    def test_points_threshold_none_is_warning(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": None})
        sev = _flag_severities(flags)
        assert "points_threshold_unconfirmed" in sev
        assert sev["points_threshold_unconfirmed"] == "warning"

    def test_points_threshold_absent_is_warning(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True})
        sev = _flag_severities(flags)
        assert "points_threshold_unconfirmed" in sev

    def test_points_threshold_false_is_warning(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": False})
        sev = _flag_severities(flags)
        assert "points_threshold_unconfirmed" in sev
        assert sev["points_threshold_unconfirmed"] == "warning"

    def test_points_threshold_true_clears_flag(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 20})
        types = _flag_types(flags)
        assert "points_threshold_unconfirmed" not in types

    def test_timeline_5_weeks_is_warning(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 5})
        sev = _flag_severities(flags)
        assert "timeline_breach" in sev
        assert sev["timeline_breach"] == "warning"

    def test_timeline_3_weeks_is_blocker(self):
        # 3 < 8/2=4 → blocker
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 3})
        sev = _flag_severities(flags)
        assert "timeline_breach" in sev
        assert sev["timeline_breach"] == "blocker"

    def test_timeline_10_weeks_clears_breach(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 10})
        types = _flag_types(flags)
        assert "timeline_breach" not in types

    def test_cost_over_threshold_raises_warning(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 20,
                            "estimated_package_cost_usd": 175_000})
        sev = _flag_severities(flags)
        assert "cost_threshold" in sev
        assert sev["cost_threshold"] == "warning"

    def test_cost_under_threshold_no_flag(self):
        flags = self._eval({"uk_sponsor_licence_confirmed": True,
                            "uk_points_threshold_confirmed": True,
                            "weeks_to_move_date": 20,
                            "estimated_package_cost_usd": 50_000})
        types = _flag_types(flags)
        assert "cost_threshold" not in types

    def test_all_clear_profile_no_flags(self):
        flags = self._eval({
            "uk_sponsor_licence_confirmed": True,
            "uk_points_threshold_confirmed": True,
            "weeks_to_move_date": 12,
            "estimated_package_cost_usd": 80_000,
        })
        assert flags == [], f"Expected no flags, got {flags}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Question bank — presence and structure
# ─────────────────────────────────────────────────────────────────────────────

class TestP5QuestionPresence:

    def test_sponsor_licence_in_question_bank(self):
        bank_ids = {q.id for q in QUESTION_BANK}
        assert "q_uk_sponsor_licence_confirmed" in bank_ids

    def test_points_threshold_in_question_bank(self):
        bank_ids = {q.id for q in QUESTION_BANK}
        assert "q_uk_points_threshold_confirmed" in bank_ids

    def test_sponsor_licence_has_why_this_matters(self):
        q = _q("q_uk_sponsor_licence_confirmed")
        assert q.whyThisMatters.strip()

    def test_points_threshold_has_why_this_matters(self):
        q = _q("q_uk_points_threshold_confirmed")
        assert q.whyThisMatters.strip()

    def test_sponsor_licence_maps_to_assignment(self):
        q = _q("q_uk_sponsor_licence_confirmed")
        assert q.mapsTo.startswith("assignment.")

    def test_points_threshold_maps_to_assignment(self):
        q = _q("q_uk_points_threshold_confirmed")
        assert q.mapsTo.startswith("assignment.")

    def test_sponsor_licence_is_boolean_type(self):
        q = _q("q_uk_sponsor_licence_confirmed")
        assert q.type == "boolean"

    def test_points_threshold_is_boolean_type(self):
        q = _q("q_uk_points_threshold_confirmed")
        assert q.type == "boolean"

    def test_sponsor_licence_gated_on_united_kingdom(self):
        q = _q("q_uk_sponsor_licence_confirmed")
        assert q.dependsOn is not None
        assert q.dependsOn.get("q_destination_region") == "united_kingdom"

    def test_points_threshold_gated_on_united_kingdom(self):
        q = _q("q_uk_points_threshold_confirmed")
        assert q.dependsOn is not None
        assert q.dependsOn.get("q_destination_region") == "united_kingdom"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Orchestrator gating — which UK questions are shown per profile
# ─────────────────────────────────────────────────────────────────────────────

class TestP5OrchestratorGating:

    def test_uk_questions_shown_for_uk_destination(self):
        profile = _profile_for("lta", "united_kingdom")
        vis = _evaluate_uk_questions(profile)
        assert vis["q_uk_sponsor_licence_confirmed"] is True
        assert vis["q_uk_points_threshold_confirmed"] is True

    def test_uk_questions_hidden_for_us_destination(self):
        profile = _profile_for("lta", "united_states")
        vis = _evaluate_uk_questions(profile)
        assert vis["q_uk_sponsor_licence_confirmed"] is False
        assert vis["q_uk_points_threshold_confirmed"] is False

    def test_uk_questions_hidden_for_japan_destination(self):
        profile = _profile_for("lta", "japan")
        vis = _evaluate_uk_questions(profile)
        assert vis["q_uk_sponsor_licence_confirmed"] is False
        assert vis["q_uk_points_threshold_confirmed"] is False

    def test_uk_questions_hidden_for_eu_destination(self):
        profile = _profile_for("lta", "eu_eea")
        vis = _evaluate_uk_questions(profile)
        assert vis["q_uk_sponsor_licence_confirmed"] is False
        assert vis["q_uk_points_threshold_confirmed"] is False

    def test_uk_questions_hidden_for_short_term_contract(self):
        # q_destination_region itself is gated on LTA types, so without it answered,
        # the UK-gated questions also won't fire
        profile = _profile_for("short_term_project")
        vis = _evaluate_uk_questions(profile)
        assert vis["q_uk_sponsor_licence_confirmed"] is False
        assert vis["q_uk_points_threshold_confirmed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. wizard_draft_mapper — P5 field extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestP5MapperExtraction:

    def _draft(self, **assignment_kwargs):
        return {"assignment": assignment_kwargs}

    def test_sponsor_licence_true_extracted(self):
        profile = extract_profile_from_wizard_draft(
            self._draft(ukSponsorLicenceConfirmed=True)
        )
        assert profile.get("uk_sponsor_licence_confirmed") is True

    def test_sponsor_licence_false_extracted(self):
        profile = extract_profile_from_wizard_draft(
            self._draft(ukSponsorLicenceConfirmed=False)
        )
        assert profile.get("uk_sponsor_licence_confirmed") is False

    def test_sponsor_licence_string_true_coerced(self):
        profile = extract_profile_from_wizard_draft(
            self._draft(ukSponsorLicenceConfirmed="true")
        )
        assert profile.get("uk_sponsor_licence_confirmed") is True

    def test_sponsor_licence_absent_not_in_output(self):
        profile = extract_profile_from_wizard_draft(self._draft())
        assert "uk_sponsor_licence_confirmed" not in profile

    def test_points_threshold_true_extracted(self):
        profile = extract_profile_from_wizard_draft(
            self._draft(ukPointsThresholdConfirmed=True)
        )
        assert profile.get("uk_points_threshold_confirmed") is True

    def test_points_threshold_false_extracted(self):
        profile = extract_profile_from_wizard_draft(
            self._draft(ukPointsThresholdConfirmed=False)
        )
        assert profile.get("uk_points_threshold_confirmed") is False

    def test_points_threshold_absent_not_in_output(self):
        profile = extract_profile_from_wizard_draft(self._draft())
        assert "uk_points_threshold_confirmed" not in profile

    def test_empty_draft_is_safe(self):
        profile = extract_profile_from_wizard_draft({})
        assert "uk_sponsor_licence_confirmed" not in profile
        assert "uk_points_threshold_confirmed" not in profile


# ─────────────────────────────────────────────────────────────────────────────
# 8. End-to-end: wizard draft → profile → exception flags
# ─────────────────────────────────────────────────────────────────────────────

class TestP5EndToEnd:
    """
    Simulates the full pipeline: wizard draft JSON → extract_profile_from_wizard_draft
    → ImmigrationRegimeRouter → ExceptionRequestService.
    """

    def _run(self, draft: Dict[str, Any]) -> List[ExceptionFlag]:
        profile = extract_profile_from_wizard_draft(draft)
        profile.setdefault("destination_country", "United Kingdom")
        profile.setdefault("origin_country", "India")
        profile.setdefault("nationality", "Indian")
        profile.setdefault("contract_type", "lta")
        regime = router.detect_regime(
            nationality=profile.get("nationality"),
            destination_country=profile.get("destination_country"),
            origin_country=profile.get("origin_country"),
            contract_type=profile.get("contract_type"),
        )
        return svc.evaluate_case(profile=profile, regime=regime)

    def _marcus_draft(self, **overrides) -> Dict[str, Any]:
        """Base draft for Marcus — UK relocation, LTA."""
        base = {
            "relocationBasics": {
                "originCountry": "India",
                "destCountry": "United Kingdom",
                "employmentType": "full_time",
            },
            "assignment": {
                "contractType": "lta",
                "ukSponsorLicenceConfirmed": True,
                "ukPointsThresholdConfirmed": True,
            },
        }
        base["assignment"].update(overrides)
        return base

    def test_marcus_no_sponsor_licence_is_blocker(self):
        draft = self._marcus_draft(ukSponsorLicenceConfirmed=False)
        flags = self._run(draft)
        sev = _flag_severities(flags)
        assert "no_sponsoring_entity" in sev
        assert sev["no_sponsoring_entity"] == "blocker"

    def test_marcus_all_clear_no_flags(self):
        draft = self._marcus_draft(weeksToMoveDate=12, estimatedPackageCostBand="50k_100k")
        profile = extract_profile_from_wizard_draft(draft)
        profile["weeks_to_move_date"] = 12  # not in mapper but accepted by service
        profile.setdefault("destination_country", "United Kingdom")
        profile.setdefault("nationality", "Indian")
        profile.setdefault("contract_type", "lta")
        regime = router.detect_regime(
            nationality=profile.get("nationality"),
            destination_country=profile.get("destination_country"),
            contract_type=profile.get("contract_type"),
        )
        flags = svc.evaluate_case(profile=profile, regime=regime)
        types = _flag_types(flags)
        assert "no_sponsoring_entity" not in types
        assert "points_threshold_unconfirmed" not in types
        assert "timeline_breach" not in types

    def test_marcus_points_not_confirmed_is_warning(self):
        draft = self._marcus_draft(ukPointsThresholdConfirmed=False)
        flags = self._run(draft)
        sev = _flag_severities(flags)
        assert "points_threshold_unconfirmed" in sev
        assert sev["points_threshold_unconfirmed"] == "warning"

    def test_marcus_tight_timeline_blocker(self):
        draft = self._marcus_draft()
        profile = extract_profile_from_wizard_draft(draft)
        profile["destination_country"] = "United Kingdom"
        profile["nationality"] = "Indian"
        profile["contract_type"] = "lta"
        profile["weeks_to_move_date"] = 3   # < 8/2=4 → blocker
        regime = router.detect_regime(
            nationality="Indian",
            destination_country="United Kingdom",
            contract_type="lta",
        )
        flags = svc.evaluate_case(profile=profile, regime=regime)
        sev = _flag_severities(flags)
        assert "timeline_breach" in sev
        assert sev["timeline_breach"] == "blocker"

    def test_non_uk_draft_has_no_uk_flags(self):
        """A US-bound draft should not produce UK-specific exception types."""
        draft = {
            "relocationBasics": {
                "originCountry": "France",
                "destCountry": "United States",
            },
            "assignment": {
                "contractType": "lta",
                "usEntityConfirmed": True,
                "specializedKnowledgeDocumented": True,
                "employmentTenureMonths": "24",
            },
        }
        profile = extract_profile_from_wizard_draft(draft)
        profile["destination_country"] = "United States"
        profile["nationality"] = "French"
        profile["weeks_to_move_date"] = 30
        regime = router.detect_regime(
            nationality="French",
            destination_country="United States",
            contract_type="lta",
        )
        flags = svc.evaluate_case(profile=profile, regime=regime)
        types = _flag_types(flags)
        assert "points_threshold_unconfirmed" not in types
        # no_sponsoring_entity may appear for US (us_entity=True so it shouldn't)
        # but it should not come from UK checks

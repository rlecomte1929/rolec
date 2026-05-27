"""
test_p2_immigration_regimes.py — P2 sprint: Immigration regime detection and
exception flag evaluation tests.

Persona scenarios covered:
  Scenario 3 — Oliver (German, Germany → United States, LTA) → us_l1b
  Scenario 6 — Yuki (Japanese, Japan → Japan, domestic) / (Japanese, HQ → Japan) → japan_coe
  EU free movement — Camille (French, France → Netherlands) → eu_free_movement
  UK → uk_skilled_worker
  Catch-all → standard_work_permit
  Unknown (no destination) → unknown

ExceptionRequestService:
  L1B blockers: tenure_insufficient, no_sponsoring_entity, timeline_breach (premium only)
  L1B warnings: timeline_breach (standard processing), role_category_ambiguous
  Japan COE: timeline_breach, role_category_ambiguous (missing sub-category)
  Shared: cost_threshold
  No false positives: clean case returns empty list

wizard_draft_mapper.py:
  nationality from primaryApplicant, employeeProfile, relocationBasics
  nationality missing → not in output (no KeyError)

timeline_service regime injection:
  Oliver draft → regime milestones present in output
  EU draft → eu_registration milestone injected
  Domestic draft → no regime milestones injected
"""
from __future__ import annotations

import sys
import os
from datetime import date, timedelta
from typing import Any, Dict, List

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
# Pure-Python services only — no FastAPI / SQLAlchemy needed.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_regime import (
    ImmigrationRegimeRouter,
    ImmigrationRegimeResult,
)
from backend.app.services.exception_request_service import (
    ExceptionRequestService,
    ExceptionFlag,
)
from backend.app.services.wizard_draft_mapper import extract_profile_from_wizard_draft


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

router = ImmigrationRegimeRouter()
svc = ExceptionRequestService()


def _flag_types(flags: List[ExceptionFlag]) -> List[str]:
    return [f.exception_type for f in flags]


def _flag_severities(flags: List[ExceptionFlag]) -> Dict[str, str]:
    return {f.exception_type: f.severity for f in flags}


# ─────────────────────────────────────────────────────────────────────────────
# 1. ImmigrationRegimeRouter — regime detection
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeDetection:
    """Core routing logic — first-match priority."""

    # ── Scenario 3: Oliver (German → US, LTA) ────────────────────────────────

    def test_oliver_lta_detects_us_l1b(self):
        r = router.detect_regime(
            nationality="German",
            destination_country="United States",
            origin_country="Germany",
            contract_type="lta",
        )
        assert r.regime_id == "us_l1b"

    def test_oliver_usa_short_alias(self):
        r = router.detect_regime(
            nationality="German",
            destination_country="USA",
            contract_type="lta",
        )
        assert r.regime_id == "us_l1b"

    def test_oliver_l1b_is_critical_priority(self):
        r = router.detect_regime(destination_country="United States", contract_type="lta")
        assert r.priority == "critical"

    def test_oliver_l1b_requires_employer_petition(self):
        r = router.detect_regime(destination_country="United States", contract_type="lta")
        assert r.requires_employer_petition is True

    def test_oliver_l1b_task_codes_present(self):
        r = router.detect_regime(destination_country="United States", contract_type="lta")
        assert "l1b_support_letter" in r.task_codes
        assert "l1b_petition_preparation" in r.task_codes
        assert "l1b_petition_filing" in r.task_codes
        assert "l1b_visa_interview" in r.task_codes
        assert "l1b_port_of_entry" in r.task_codes
        assert "l1b_ssn_application" in r.task_codes

    def test_oliver_l1b_lead_time_is_20_weeks(self):
        r = router.detect_regime(destination_country="United States", contract_type="lta")
        assert r.typical_lead_time_weeks == 20

    def test_oliver_l1b_exception_triggers_correct(self):
        r = router.detect_regime(destination_country="United States", contract_type="lta")
        assert "tenure_insufficient" in r.exception_triggers
        assert "no_sponsoring_entity" in r.exception_triggers
        assert "timeline_breach" in r.exception_triggers

    def test_us_short_term_routes_to_standard_not_l1b(self):
        """Short-term project to US should NOT get L1B."""
        r = router.detect_regime(
            destination_country="United States",
            contract_type="short_term_project",
        )
        assert r.regime_id == "standard_work_permit"
        assert r.regime_id != "us_l1b"

    # ── Scenario 6: Yuki (Japanese HQ → Japan office) ────────────────────────

    def test_yuki_japan_detects_japan_coe(self):
        r = router.detect_regime(
            nationality="Japanese",
            destination_country="Japan",
            origin_country="France",  # HQ in Paris
            contract_type="lta",
        )
        assert r.regime_id == "japan_coe"

    def test_japan_coe_is_critical_priority(self):
        r = router.detect_regime(destination_country="Japan")
        assert r.priority == "critical"

    def test_japan_coe_requires_employer_petition(self):
        r = router.detect_regime(destination_country="Japan")
        assert r.requires_employer_petition is True

    def test_japan_coe_task_codes_present(self):
        r = router.detect_regime(destination_country="Japan")
        assert "japan_coe_preparation" in r.task_codes
        assert "japan_coe_visa_application" in r.task_codes
        assert "japan_residence_card" in r.task_codes
        assert "japan_municipal_registration" in r.task_codes

    def test_japan_coe_lead_time_is_16_weeks(self):
        r = router.detect_regime(destination_country="Japan")
        assert r.typical_lead_time_weeks == 16

    def test_japan_jp_alias(self):
        r = router.detect_regime(destination_country="jp")
        assert r.regime_id == "japan_coe"

    def test_domestic_japan_to_japan(self):
        """Same origin + dest = domestic, not japan_coe."""
        r = router.detect_regime(
            destination_country="Japan",
            origin_country="Japan",
        )
        assert r.regime_id == "domestic"

    # ── EU free movement ──────────────────────────────────────────────────────

    def test_eu_national_to_eu_dest_free_movement(self):
        """French national → Netherlands: no work permit."""
        r = router.detect_regime(
            nationality="France",
            destination_country="Netherlands",
            origin_country="France",
        )
        assert r.regime_id == "eu_free_movement"

    def test_eu_free_movement_lead_time_zero(self):
        r = router.detect_regime(nationality="Germany", destination_country="Spain")
        assert r.typical_lead_time_weeks == 0

    def test_eu_free_movement_task_codes(self):
        r = router.detect_regime(nationality="France", destination_country="Belgium")
        assert "eu_registration" in r.task_codes

    def test_non_eu_national_to_eu_dest_gets_standard(self):
        """US national → Germany: not free movement."""
        r = router.detect_regime(
            nationality="American",
            destination_country="Germany",
        )
        assert r.regime_id != "eu_free_movement"
        assert r.regime_id == "standard_work_permit"

    # ── UK ────────────────────────────────────────────────────────────────────

    def test_uk_destination_detects_skilled_worker(self):
        r = router.detect_regime(destination_country="United Kingdom", contract_type="lta")
        assert r.regime_id == "uk_skilled_worker"

    def test_uk_alias(self):
        r = router.detect_regime(destination_country="uk")
        assert r.regime_id == "uk_skilled_worker"

    # ── Catch-all / unknown ───────────────────────────────────────────────────

    def test_unknown_destination_returns_unknown(self):
        r = router.detect_regime()
        assert r.regime_id == "unknown"

    def test_unspecified_destination_returns_standard(self):
        r = router.detect_regime(destination_country="Brazil")
        assert r.regime_id == "standard_work_permit"

    def test_domestic_same_country(self):
        r = router.detect_regime(origin_country="France", destination_country="France")
        assert r.regime_id == "domestic"


# ─────────────────────────────────────────────────────────────────────────────
# 2. ExceptionRequestService — flag evaluation
# ─────────────────────────────────────────────────────────────────────────────

class TestL1BExceptionFlags:
    """L1B-specific exception checks."""

    def _l1b_regime(self) -> ImmigrationRegimeResult:
        return router.detect_regime(destination_country="United States", contract_type="lta")

    def test_clean_l1b_profile_no_flags(self):
        """A well-prepared L1B case should return no exception flags."""
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 18,
                "weeks_to_move_date": 28,
                "us_entity_confirmed": True,
                "specialized_knowledge_documented": True,
            },
            regime=regime,
        )
        assert flags == []

    def test_tenure_below_12_months_is_blocker(self):
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={"employment_tenure_months": 8, "us_entity_confirmed": True},
            regime=regime,
        )
        types = _flag_types(flags)
        severities = _flag_severities(flags)
        assert "tenure_insufficient" in types
        assert severities["tenure_insufficient"] == "blocker"

    def test_tenure_exactly_12_months_no_tenure_flag(self):
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 12,
                "us_entity_confirmed": True,
                "weeks_to_move_date": 28,
                "specialized_knowledge_documented": True,
            },
            regime=regime,
        )
        assert "tenure_insufficient" not in _flag_types(flags)

    def test_no_us_entity_confirmed_is_blocker(self):
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={"employment_tenure_months": 18, "us_entity_confirmed": False},
            regime=regime,
        )
        types = _flag_types(flags)
        severities = _flag_severities(flags)
        assert "no_sponsoring_entity" in types
        assert severities["no_sponsoring_entity"] == "blocker"

    def test_no_us_entity_name_and_unconfirmed_is_blocker(self):
        """us_entity_confirmed=None + us_entity_name=None → blocker."""
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={"employment_tenure_months": 18},
            regime=regime,
        )
        assert "no_sponsoring_entity" in _flag_types(flags)

    def test_timeline_below_premium_threshold_is_blocker(self):
        """< 10 weeks → absolute blocker, can't even do premium processing."""
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 18,
                "weeks_to_move_date": 6,
                "us_entity_confirmed": True,
            },
            regime=regime,
        )
        severities = _flag_severities(flags)
        assert "timeline_breach" in severities
        assert severities["timeline_breach"] == "blocker"

    def test_timeline_between_premium_and_standard_is_warning(self):
        """10–23 weeks → warning (premium processing needed, still possible)."""
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 18,
                "weeks_to_move_date": 15,
                "us_entity_confirmed": True,
                "specialized_knowledge_documented": True,
            },
            regime=regime,
        )
        severities = _flag_severities(flags)
        assert "timeline_breach" in severities
        assert severities["timeline_breach"] == "warning"

    def test_specialized_knowledge_false_is_warning(self):
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 18,
                "weeks_to_move_date": 28,
                "us_entity_confirmed": True,
                "specialized_knowledge_documented": False,
            },
            regime=regime,
        )
        types = _flag_types(flags)
        severities = _flag_severities(flags)
        assert "role_category_ambiguous" in types
        assert severities["role_category_ambiguous"] == "warning"

    def test_specialized_knowledge_none_no_flag(self):
        """Unknown (None) ≠ False — should not raise a flag."""
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 18,
                "weeks_to_move_date": 28,
                "us_entity_confirmed": True,
                # specialized_knowledge_documented not provided
            },
            regime=regime,
        )
        assert "role_category_ambiguous" not in _flag_types(flags)

    def test_l1b_flags_have_recommended_action(self):
        """Every flag on L1B must carry a recommended_action string."""
        regime = self._l1b_regime()
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 6,
                "weeks_to_move_date": 8,
                "us_entity_confirmed": False,
                "specialized_knowledge_documented": False,
            },
            regime=regime,
        )
        assert len(flags) >= 3
        for f in flags:
            assert f.recommended_action, f"Flag {f.exception_type} missing recommended_action"


class TestJapanCOEExceptionFlags:
    """Japan COE exception checks."""

    def _japan_regime(self) -> ImmigrationRegimeResult:
        return router.detect_regime(destination_country="Japan", contract_type="lta")

    def test_clean_japan_profile_no_flags(self):
        regime = self._japan_regime()
        flags = svc.evaluate_case(
            profile={
                "weeks_to_move_date": 20,
                "japan_visa_category": "eshs",
            },
            regime=regime,
        )
        assert flags == []

    def test_japan_timeline_too_short_is_blocker(self):
        """< 8 weeks (half of 16) → blocker."""
        regime = self._japan_regime()
        flags = svc.evaluate_case(
            profile={"weeks_to_move_date": 6, "japan_visa_category": "eshs"},
            regime=regime,
        )
        severities = _flag_severities(flags)
        assert "timeline_breach" in severities
        assert severities["timeline_breach"] == "blocker"

    def test_japan_timeline_marginal_is_warning(self):
        """8–15 weeks: possible but tight → warning."""
        regime = self._japan_regime()
        flags = svc.evaluate_case(
            profile={"weeks_to_move_date": 10, "japan_visa_category": "ict"},
            regime=regime,
        )
        severities = _flag_severities(flags)
        assert "timeline_breach" in severities
        assert severities["timeline_breach"] == "warning"

    def test_japan_missing_visa_category_is_warning(self):
        regime = self._japan_regime()
        flags = svc.evaluate_case(
            profile={"weeks_to_move_date": 20},  # no japan_visa_category
            regime=regime,
        )
        types = _flag_types(flags)
        assert "role_category_ambiguous" in types

    def test_japan_empty_visa_category_is_warning(self):
        regime = self._japan_regime()
        flags = svc.evaluate_case(
            profile={"weeks_to_move_date": 20, "japan_visa_category": ""},
            regime=regime,
        )
        assert "role_category_ambiguous" in _flag_types(flags)

    def test_japan_ict_category_no_role_flag(self):
        """ICT is a valid category — should not trigger role_category_ambiguous."""
        regime = self._japan_regime()
        flags = svc.evaluate_case(
            profile={"weeks_to_move_date": 20, "japan_visa_category": "ict"},
            regime=regime,
        )
        assert "role_category_ambiguous" not in _flag_types(flags)


class TestCostThresholdFlag:
    """Cost threshold flag applies to all regimes."""

    def test_cost_above_threshold_raises_warning(self):
        regime = router.detect_regime(destination_country="United States", contract_type="lta")
        flags = svc.evaluate_case(
            profile={
                "employment_tenure_months": 18,
                "us_entity_confirmed": True,
                "weeks_to_move_date": 30,
                "specialized_knowledge_documented": True,
                "estimated_package_cost_usd": 200_000,
            },
            regime=regime,
        )
        types = _flag_types(flags)
        assert "cost_threshold" in types

    def test_cost_at_threshold_no_flag(self):
        regime = router.detect_regime(destination_country="Japan")
        flags = svc.evaluate_case(
            profile={"estimated_package_cost_usd": 150_000, "weeks_to_move_date": 20},
            regime=regime,
        )
        assert "cost_threshold" not in _flag_types(flags)

    def test_cost_threshold_on_eu_regime(self):
        """Cost threshold should also fire for EU free-movement cases."""
        regime = router.detect_regime(nationality="France", destination_country="Germany")
        flags = svc.evaluate_case(
            profile={"estimated_package_cost_usd": 160_000},
            regime=regime,
        )
        assert "cost_threshold" in _flag_types(flags)

    def test_no_cost_provided_no_flag(self):
        regime = router.detect_regime(destination_country="Japan")
        flags = svc.evaluate_case(
            profile={"weeks_to_move_date": 20, "japan_visa_category": "eshs"},
            regime=regime,
        )
        assert "cost_threshold" not in _flag_types(flags)


class TestEURegimeNoExceptionFlags:
    """EU free movement has no L1B/Japan triggers — evaluate_case should be quiet."""

    def test_eu_free_movement_no_flags_by_default(self):
        regime = router.detect_regime(nationality="Germany", destination_country="France")
        flags = svc.evaluate_case(profile={}, regime=regime)
        assert flags == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. wizard_draft_mapper — nationality extraction (P2)
# ─────────────────────────────────────────────────────────────────────────────

class TestWizardDraftMapperNationality:

    def test_nationality_from_primary_applicant(self):
        draft = {"primaryApplicant": {"nationality": "German"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["nationality"] == "German"

    def test_nationality_from_employee_profile(self):
        draft = {"employeeProfile": {"nationality": "Japanese"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["nationality"] == "Japanese"

    def test_nationality_from_employee_profile_nationality_country(self):
        draft = {"employeeProfile": {"nationalityCountry": "French"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["nationality"] == "French"

    def test_nationality_from_relocation_basics(self):
        draft = {"relocationBasics": {"nationality": "Norwegian"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["nationality"] == "Norwegian"

    def test_nationality_primary_applicant_wins_over_employee_profile(self):
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "employeeProfile": {"nationality": "French"},
        }
        p = extract_profile_from_wizard_draft(draft)
        assert p["nationality"] == "German"

    def test_nationality_missing_not_in_output(self):
        draft = {"relocationBasics": {"originCountry": "Germany"}}
        p = extract_profile_from_wizard_draft(draft)
        assert "nationality" not in p

    def test_empty_draft_no_nationality(self):
        p = extract_profile_from_wizard_draft({})
        assert "nationality" not in p

    def test_nationality_combined_with_other_s3_s4_fields(self):
        """Full Oliver-style draft: nationality + contract_type + geography all extracted."""
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "relocationBasics": {
                "originCountry": "Germany",
                "destCountry": "United States",
            },
            "assignment": {"contractType": "lta"},
        }
        p = extract_profile_from_wizard_draft(draft)
        assert p["nationality"] == "German"
        assert p["origin_country"] == "Germany"
        assert p["destination_country"] == "United States"
        assert p["contract_type"] == "lta"


# ─────────────────────────────────────────────────────────────────────────────
# 4. compute_default_milestones — regime milestone injection
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeMilestoneInjection:
    """
    Functional tests: does the timeline service inject regime milestones
    correctly when given an Oliver-style (US L1B) or EU draft?
    """

    def _milestones(self, **kwargs):
        """Call compute_default_milestones with a fake case_id."""
        from backend.app.services.timeline_service import compute_default_milestones
        return compute_default_milestones(case_id="test-p2-case", **kwargs)

    def _types(self, milestones):
        return [m["milestone_type"] for m in milestones]

    def test_oliver_lta_us_injects_l1b_milestones(self):
        move_date = (date.today() + timedelta(weeks=30)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="United States",
            origin_country="Germany",
            nationality="German",
        )
        types = self._types(milestones)
        assert "task_l1b_support_letter" in types
        assert "task_l1b_petition_prep" in types
        assert "task_l1b_petition_filing" in types
        assert "task_l1b_visa_interview" in types
        assert "task_l1b_port_of_entry" in types

    def test_oliver_l1b_ssn_milestone_after_move_date(self):
        """SSN application target_date must be AFTER the move date."""
        move_date = (date.today() + timedelta(weeks=30)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="United States",
            nationality="German",
        )
        ssn = next((m for m in milestones if m["milestone_type"] == "task_l1b_ssn"), None)
        if ssn and ssn.get("target_date"):
            assert ssn["target_date"] > move_date, "SSN target_date should be after move date"

    def test_yuki_japan_injects_coe_milestones(self):
        move_date = (date.today() + timedelta(weeks=20)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="Japan",
            origin_country="France",
            nationality="Japanese",
        )
        types = self._types(milestones)
        assert "task_japan_coe_prep" in types
        assert "task_japan_coe_visa" in types
        assert "task_japan_residence_card" in types

    def test_eu_free_movement_injects_registration_milestone(self):
        move_date = (date.today() + timedelta(weeks=12)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="Netherlands",
            origin_country="France",
            nationality="France",   # country name, not the gentillic "French"
        )
        types = self._types(milestones)
        assert "task_eu_registration" in types

    def test_domestic_move_no_regime_milestones(self):
        move_date = (date.today() + timedelta(weeks=8)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="domestic",
            destination_country="France",
            origin_country="France",
        )
        types = self._types(milestones)
        # No L1B, COE, or EU registration tasks on a domestic move
        assert "task_l1b_support_letter" not in types
        assert "task_japan_coe_prep" not in types
        assert "task_eu_registration" not in types

    def test_regime_milestones_no_duplicates(self):
        move_date = (date.today() + timedelta(weeks=30)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="United States",
            nationality="German",
        )
        types = self._types(milestones)
        assert len(types) == len(set(types)), "Duplicate milestone_type detected"

    def test_no_target_move_date_still_returns_milestones(self):
        """Without a move_date, regime milestones are still injected (no target_date)."""
        milestones = self._milestones(
            contract_type="lta",
            destination_country="Japan",
            nationality="Japanese",
        )
        types = self._types(milestones)
        assert "task_japan_coe_prep" in types

    def test_backward_compat_no_nationality_no_crash(self):
        """Passing no nationality param returns milestones without crashing."""
        move_date = (date.today() + timedelta(weeks=12)).isoformat()
        milestones = self._milestones(target_move_date=move_date)
        assert isinstance(milestones, list)

    def test_regime_milestones_have_owner_field(self):
        move_date = (date.today() + timedelta(weeks=30)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="United States",
            nationality="German",
        )
        l1b_milestones = [m for m in milestones if m["milestone_type"].startswith("task_l1b")]
        assert len(l1b_milestones) > 0
        for m in l1b_milestones:
            assert "owner" in m, f"{m['milestone_type']} missing owner"

    def test_regime_milestones_have_criticality(self):
        move_date = (date.today() + timedelta(weeks=30)).isoformat()
        milestones = self._milestones(
            target_move_date=move_date,
            contract_type="lta",
            destination_country="Japan",
            nationality="Japanese",
        )
        japan_milestones = [m for m in milestones if "japan" in m["milestone_type"]]
        assert len(japan_milestones) > 0
        for m in japan_milestones:
            assert m.get("criticality") in ("critical", "normal"), (
                f"{m['milestone_type']} has unexpected criticality: {m.get('criticality')}"
            )

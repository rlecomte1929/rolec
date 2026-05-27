"""
test_p4_immigration_questions.py — P4: Immigration question bank and
wizard_draft_mapper extraction tests.

Covers:
  Question bank presence and structure:
    - All 6 P4 questions are registered in QUESTION_BANK
    - Each question has a non-empty whyThisMatters and a valid mapsTo path
    - q_destination_region: gated on LTA/permanent_transfer contract types
    - q_employment_tenure_months: gated on LTA/permanent_transfer
    - q_us_entity_confirmed: gated on q_destination_region == "united_states"
    - q_specialized_knowledge_documented: gated on q_destination_region == "united_states"
    - q_japan_visa_category: gated on q_destination_region == "japan"
    - q_estimated_package_cost: gated on LTA/permanent_transfer

  Orchestrator gating logic (dependsOn evaluation):
    - US questions not shown for Japan destination
    - Japan question not shown for US destination
    - P4 questions not shown for domestic_move
    - P4 questions not shown for short_term_project
    - All P4 questions shown for LTA + correct destination

  wizard_draft_mapper — P4 field extraction:
    - employment_tenure_months from string option values ("8" → 8)
    - us_entity_confirmed: True / False / None
    - specialized_knowledge_documented: True / False / None
    - japan_visa_category: "eshs" / "ict" extracted; "unknown" → absent
    - estimated_package_cost_usd: band → midpoint mapping
    - estimated_package_cost_usd: direct numeric fallback
    - Missing P4 fields → not in output (no KeyError)

  End-to-end: wizard draft → profile → exception flags
    - Oliver draft (tenure=8, us_entity=False, US) → tenure_insufficient blocker
    - Oliver draft (tenure=24, entity=True, sk=True, US) → no flags
    - Yuki draft (Japan, no category) → role_category_ambiguous
    - Cost band over_200k → cost_threshold warning
    - Domestic draft → no exception flags

  Orchestrator _evaluate_condition correctness for P4 operators:
    - "in" list match
    - exact string equality
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
from backend.app.services.wizard_draft_mapper import extract_profile_from_wizard_draft
from backend.app.services.immigration_regime import ImmigrationRegimeRouter
from backend.app.services.exception_request_service import ExceptionRequestService, ExceptionFlag

router = ImmigrationRegimeRouter()
svc = ExceptionRequestService()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _q(qid: str):
    q = get_question_by_id(qid)
    assert q is not None, f"Question {qid!r} not found in QUESTION_BANK"
    return q

def _flag_types(flags: List[ExceptionFlag]) -> List[str]:
    return [f.exception_type for f in flags]

def _evaluate_all_p4(profile: Dict[str, Any]) -> Dict[str, bool]:
    """
    Use the orchestrator's gating logic to check which P4 questions
    would be shown for a given in-flight profile dict.
    """
    from backend.agents.orchestrator import IntakeOrchestrator
    orch = IntakeOrchestrator()
    return {q.id: orch._check_dependencies(q, profile) for q in P4_QUESTIONS}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Question bank — presence and structure
# ─────────────────────────────────────────────────────────────────────────────

class TestP4QuestionPresence:

    def test_all_p4_questions_in_bank(self):
        bank_ids = {q.id for q in QUESTION_BANK}
        for q in P4_QUESTIONS:
            assert q.id in bank_ids, f"{q.id} missing from QUESTION_BANK"

    def test_p4_questions_have_why_this_matters(self):
        for q in P4_QUESTIONS:
            assert q.whyThisMatters.strip(), f"{q.id} has empty whyThisMatters"

    def test_p4_questions_have_maps_to(self):
        for q in P4_QUESTIONS:
            assert q.mapsTo.startswith("assignment."), (
                f"{q.id} mapsTo should be under assignment.*; got {q.mapsTo!r}"
            )

    def test_destination_region_has_correct_options(self):
        q = _q("q_destination_region")
        option_values = {o.value for o in q.options}
        assert "united_states" in option_values
        assert "japan" in option_values
        assert "eu_eea" in option_values
        assert "united_kingdom" in option_values

    def test_employment_tenure_has_options(self):
        q = _q("q_employment_tenure_months")
        assert q.options and len(q.options) >= 5
        values = {o.value for o in q.options}
        assert "12" in values, "12-month threshold option must be present"

    def test_japan_visa_category_has_eshs_and_ict(self):
        q = _q("q_japan_visa_category")
        values = {o.value for o in q.options}
        assert "eshs" in values
        assert "ict" in values
        assert "unknown" in values  # allows "I don't know" answer

    def test_cost_band_has_five_options(self):
        q = _q("q_estimated_package_cost")
        assert len(q.options) == 5
        values = {o.value for o in q.options}
        assert "150k_200k" in values
        assert "over_200k" in values

    def test_destination_region_gated_on_lta_types(self):
        q = _q("q_destination_region")
        assert q.dependsOn is not None
        cond = q.dependsOn.get("q_contract_type", {})
        assert "in" in cond
        assert "lta" in cond["in"]
        assert "permanent_transfer" in cond["in"]

    def test_us_entity_gated_on_destination_region(self):
        q = _q("q_us_entity_confirmed")
        assert q.dependsOn is not None
        assert "q_destination_region" in q.dependsOn
        assert q.dependsOn["q_destination_region"] == "united_states"

    def test_specialized_knowledge_gated_on_destination_region(self):
        q = _q("q_specialized_knowledge_documented")
        assert q.dependsOn is not None
        assert q.dependsOn.get("q_destination_region") == "united_states"

    def test_japan_visa_gated_on_destination_region(self):
        q = _q("q_japan_visa_category")
        assert q.dependsOn is not None
        assert q.dependsOn.get("q_destination_region") == "japan"

    def test_tenure_and_cost_gated_on_lta(self):
        for qid in ("q_employment_tenure_months", "q_estimated_package_cost"):
            q = _q(qid)
            assert q.dependsOn is not None
            cond = q.dependsOn.get("q_contract_type", {})
            assert "in" in cond and "lta" in cond["in"], (
                f"{qid} must be gated on lta contract type"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Orchestrator gating — which P4 questions are shown per profile
# ─────────────────────────────────────────────────────────────────────────────

class TestP4OrchestratorGating:

    def _profile_for(self, contract_type: str, destination_region: str = None) -> Dict[str, Any]:
        """Build a minimal in-flight orchestrator profile for gating evaluation."""
        # Orchestrator stores values at the mapsTo path of each answered question.
        profile: Dict[str, Any] = {"assignment": {"contractType": contract_type}}
        if destination_region:
            profile["assignment"]["destinationRegion"] = destination_region
        return profile

    def test_lta_us_shows_all_us_questions(self):
        profile = self._profile_for("lta", "united_states")
        shown = _evaluate_all_p4(profile)
        assert shown["q_destination_region"] is True
        assert shown["q_employment_tenure_months"] is True
        assert shown["q_us_entity_confirmed"] is True
        assert shown["q_specialized_knowledge_documented"] is True
        assert shown["q_estimated_package_cost"] is True
        # Japan question NOT shown for US destination
        assert shown["q_japan_visa_category"] is False

    def test_lta_japan_shows_japan_questions(self):
        profile = self._profile_for("lta", "japan")
        shown = _evaluate_all_p4(profile)
        assert shown["q_destination_region"] is True
        assert shown["q_employment_tenure_months"] is True
        assert shown["q_japan_visa_category"] is True
        assert shown["q_estimated_package_cost"] is True
        # US questions NOT shown for Japan destination
        assert shown["q_us_entity_confirmed"] is False
        assert shown["q_specialized_knowledge_documented"] is False

    def test_domestic_move_hides_all_p4_questions(self):
        profile = self._profile_for("domestic_move")
        shown = _evaluate_all_p4(profile)
        # None of the P4 questions should show for domestic
        for qid, is_shown in shown.items():
            assert is_shown is False, (
                f"{qid} should not show for domestic_move"
            )

    def test_short_term_project_hides_p4_questions(self):
        profile = self._profile_for("short_term_project")
        shown = _evaluate_all_p4(profile)
        for qid, is_shown in shown.items():
            assert is_shown is False, (
                f"{qid} should not show for short_term_project"
            )

    def test_permanent_transfer_eu_shows_no_us_or_japan(self):
        profile = self._profile_for("permanent_transfer", "eu_eea")
        shown = _evaluate_all_p4(profile)
        assert shown["q_destination_region"] is True
        assert shown["q_employment_tenure_months"] is True
        assert shown["q_estimated_package_cost"] is True
        assert shown["q_us_entity_confirmed"] is False
        assert shown["q_specialized_knowledge_documented"] is False
        assert shown["q_japan_visa_category"] is False

    def test_no_contract_type_answered_hides_all(self):
        """If q_contract_type not yet answered, no P4 question is shown."""
        profile: Dict[str, Any] = {}
        shown = _evaluate_all_p4(profile)
        for qid, is_shown in shown.items():
            assert is_shown is False, f"{qid} should not show before contract_type answered"


# ─────────────────────────────────────────────────────────────────────────────
# 3. wizard_draft_mapper — P4 field extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestWizardDraftMapperP4:

    def test_employment_tenure_string_coerced_to_int(self):
        draft = {"assignment": {"contractType": "lta", "employmentTenureMonths": "8"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["employment_tenure_months"] == 8
        assert isinstance(p["employment_tenure_months"], int)

    def test_employment_tenure_int_passthrough(self):
        draft = {"assignment": {"employmentTenureMonths": 24}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["employment_tenure_months"] == 24

    def test_employment_tenure_missing_not_in_output(self):
        draft = {"assignment": {"contractType": "lta"}}
        p = extract_profile_from_wizard_draft(draft)
        assert "employment_tenure_months" not in p

    def test_us_entity_confirmed_true(self):
        draft = {"assignment": {"usEntityConfirmed": True}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["us_entity_confirmed"] is True

    def test_us_entity_confirmed_false(self):
        draft = {"assignment": {"usEntityConfirmed": False}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["us_entity_confirmed"] is False

    def test_us_entity_confirmed_string_true(self):
        draft = {"assignment": {"usEntityConfirmed": "true"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["us_entity_confirmed"] is True

    def test_us_entity_missing_not_in_output(self):
        draft = {"assignment": {"contractType": "lta"}}
        p = extract_profile_from_wizard_draft(draft)
        assert "us_entity_confirmed" not in p

    def test_specialized_knowledge_false(self):
        draft = {"assignment": {"specializedKnowledgeDocumented": False}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["specialized_knowledge_documented"] is False

    def test_specialized_knowledge_true(self):
        draft = {"assignment": {"specializedKnowledgeDocumented": True}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["specialized_knowledge_documented"] is True

    def test_japan_visa_category_eshs(self):
        draft = {"assignment": {"japanVisaCategory": "eshs"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["japan_visa_category"] == "eshs"

    def test_japan_visa_category_ict(self):
        draft = {"assignment": {"japanVisaCategory": "ICT"}}  # test case-insensitive
        p = extract_profile_from_wizard_draft(draft)
        assert p["japan_visa_category"] == "ict"

    def test_japan_visa_category_unknown_absent(self):
        """'unknown' answer means ambiguous — should NOT be in output (triggers flag)."""
        draft = {"assignment": {"japanVisaCategory": "unknown"}}
        p = extract_profile_from_wizard_draft(draft)
        assert "japan_visa_category" not in p

    def test_japan_visa_category_empty_absent(self):
        draft = {"assignment": {"japanVisaCategory": ""}}
        p = extract_profile_from_wizard_draft(draft)
        assert "japan_visa_category" not in p

    def test_cost_band_under_50k_maps_to_midpoint(self):
        draft = {"assignment": {"estimatedPackageCostBand": "under_50k"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["estimated_package_cost_usd"] == 25_000.0

    def test_cost_band_50k_100k(self):
        draft = {"assignment": {"estimatedPackageCostBand": "50k_100k"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["estimated_package_cost_usd"] == 75_000.0

    def test_cost_band_100k_150k(self):
        draft = {"assignment": {"estimatedPackageCostBand": "100k_150k"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["estimated_package_cost_usd"] == 125_000.0

    def test_cost_band_150k_200k(self):
        draft = {"assignment": {"estimatedPackageCostBand": "150k_200k"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["estimated_package_cost_usd"] == 175_000.0

    def test_cost_band_over_200k(self):
        draft = {"assignment": {"estimatedPackageCostBand": "over_200k"}}
        p = extract_profile_from_wizard_draft(draft)
        assert p["estimated_package_cost_usd"] == 225_000.0

    def test_cost_band_missing_not_in_output(self):
        draft = {"assignment": {"contractType": "lta"}}
        p = extract_profile_from_wizard_draft(draft)
        assert "estimated_package_cost_usd" not in p

    def test_empty_draft_no_p4_fields(self):
        p = extract_profile_from_wizard_draft({})
        for field in (
            "employment_tenure_months", "us_entity_confirmed",
            "specialized_knowledge_documented", "japan_visa_category",
            "estimated_package_cost_usd",
        ):
            assert field not in p, f"{field} should not be in output for empty draft"


# ─────────────────────────────────────────────────────────────────────────────
# 4. End-to-end: wizard draft → profile → exception flags
# ─────────────────────────────────────────────────────────────────────────────

class TestP4EndToEnd:
    """
    Full pipeline: extract_profile_from_wizard_draft → ImmigrationRegimeRouter
    → ExceptionRequestService. Validates that real wizard answers produce the
    correct exception flags.
    """

    def _flags(self, draft: Dict[str, Any]) -> List[ExceptionFlag]:
        profile = extract_profile_from_wizard_draft(draft)
        regime = router.detect_regime(
            nationality=profile.get("nationality"),
            destination_country=profile.get("destination_country"),
            origin_country=profile.get("origin_country"),
            contract_type=profile.get("contract_type"),
        )
        return svc.evaluate_case(profile=profile, regime=regime)

    def test_oliver_short_tenure_produces_blocker(self):
        """Oliver: 8 months tenure → tenure_insufficient blocker."""
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "relocationBasics": {"originCountry": "Germany", "destCountry": "United States"},
            "assignment": {
                "contractType": "lta",
                "destinationRegion": "united_states",
                "employmentTenureMonths": "8",   # < 12 → blocker
                "usEntityConfirmed": True,
                "specializedKnowledgeDocumented": True,
                "estimatedPackageCostBand": "100k_150k",
            },
        }
        flags = self._flags(draft)
        types = _flag_types(flags)
        assert "tenure_insufficient" in types
        blockers = [f for f in flags if f.severity == "blocker"]
        assert any(f.exception_type == "tenure_insufficient" for f in blockers)

    def test_oliver_no_entity_produces_blocker(self):
        """Oliver: us_entity_confirmed=False → no_sponsoring_entity blocker."""
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "relocationBasics": {"originCountry": "Germany", "destCountry": "United States"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "usEntityConfirmed": False,   # → blocker
                "specializedKnowledgeDocumented": True,
            },
        }
        flags = self._flags(draft)
        assert "no_sponsoring_entity" in _flag_types(flags)

    def test_oliver_clean_draft_no_flags(self):
        """Well-prepared Oliver case → zero flags."""
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "relocationBasics": {"originCountry": "Germany", "destCountry": "United States"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "usEntityConfirmed": True,
                "specializedKnowledgeDocumented": True,
                "estimatedPackageCostBand": "100k_150k",
            },
        }
        flags = self._flags(draft)
        assert flags == []

    def test_yuki_no_visa_category_produces_flag(self):
        """Yuki: japan_visa_category missing → role_category_ambiguous warning."""
        draft = {
            "primaryApplicant": {"nationality": "Japanese"},
            "relocationBasics": {"originCountry": "France", "destCountry": "Japan"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "estimatedPackageCostBand": "100k_150k",
                # japanVisaCategory NOT set → flag fires
            },
        }
        flags = self._flags(draft)
        assert "role_category_ambiguous" in _flag_types(flags)

    def test_yuki_unknown_category_produces_flag(self):
        """'unknown' visa category → treated as absent → flag fires."""
        draft = {
            "primaryApplicant": {"nationality": "Japanese"},
            "relocationBasics": {"destCountry": "Japan"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "japanVisaCategory": "unknown",   # mapper omits → service flags it
            },
        }
        flags = self._flags(draft)
        assert "role_category_ambiguous" in _flag_types(flags)

    def test_yuki_eshs_category_no_role_flag(self):
        """Known ESHS category → no role_category_ambiguous."""
        draft = {
            "primaryApplicant": {"nationality": "Japanese"},
            "relocationBasics": {"destCountry": "Japan"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "japanVisaCategory": "eshs",
                "estimatedPackageCostBand": "50k_100k",
            },
        }
        flags = self._flags(draft)
        assert "role_category_ambiguous" not in _flag_types(flags)

    def test_over_200k_band_triggers_cost_threshold(self):
        """over_200k band → estimated_package_cost_usd=225k → cost_threshold warning."""
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "relocationBasics": {"originCountry": "Germany", "destCountry": "United States"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "usEntityConfirmed": True,
                "specializedKnowledgeDocumented": True,
                "estimatedPackageCostBand": "over_200k",   # → $225k → threshold exceeded
            },
        }
        flags = self._flags(draft)
        assert "cost_threshold" in _flag_types(flags)

    def test_under_150k_no_cost_threshold(self):
        """under_50k band → $25k → no cost_threshold."""
        draft = {
            "primaryApplicant": {"nationality": "German"},
            "relocationBasics": {"destCountry": "United States"},
            "assignment": {
                "contractType": "lta",
                "employmentTenureMonths": "24",
                "usEntityConfirmed": True,
                "specializedKnowledgeDocumented": True,
                "estimatedPackageCostBand": "under_50k",
            },
        }
        flags = self._flags(draft)
        assert "cost_threshold" not in _flag_types(flags)

    def test_domestic_draft_no_flags(self):
        """Domestic draft → no immigration regime → no exception flags."""
        draft = {
            "relocationBasics": {"originCountry": "France", "destCountry": "France"},
            "assignment": {"contractType": "domestic_move"},
        }
        flags = self._flags(draft)
        assert flags == []

    def test_eu_free_movement_draft_no_flags(self):
        """French national → Netherlands: free movement → no flags."""
        draft = {
            "primaryApplicant": {"nationality": "France"},
            "relocationBasics": {"originCountry": "France", "destCountry": "Netherlands"},
            "assignment": {"contractType": "lta"},
        }
        flags = self._flags(draft)
        assert flags == []

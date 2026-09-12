"""Dynamic service question schema for ReloPass.

Defines the canonical question bank with conditional logic, prefill sources,
and validation. Used by the question generation engine to produce
a dynamic questionnaire based on selected services and context.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QuestionOption(BaseModel):
    value: str
    label: str


class ServiceQuestionDef(BaseModel):
    """Single question definition in the schema."""
    question_key: str
    label: str
    type: Literal["text", "number", "select", "multiselect", "checkbox", "date", "range"] = "text"
    service_category: str  # housing, schools, movers, banks, insurances, electricity
    required: bool = False
    options: Optional[List[QuestionOption]] = None
    placeholder: Optional[str] = None
    default: Optional[Any] = None
    # Conditional: show only if answers/applies_if match
    applies_if: Optional[Dict[str, Any]] = None
    # Prefill: "case.destCity", "case.dependents[].age", "answers.budget_min"
    prefill_source: Optional[str] = None
    # Backend criteria key for recommendations
    criteria_key: Optional[str] = None


def _bank() -> List[ServiceQuestionDef]:
    """Canonical question bank. Only enabled services with backend support."""
    return [
        # Housing
        # Currency suffix is appended client-side from the user's chosen
        # display currency (set on the Select services page) so the wizard
        # stays consistent across the flow.
        ServiceQuestionDef(
            question_key="budget_min",
            label="Min monthly budget",
            type="number",
            service_category="housing",
            default=2000,
            criteria_key="budget_min",
        ),
        ServiceQuestionDef(
            question_key="budget_max",
            label="Max monthly budget",
            type="number",
            service_category="housing",
            default=5000,
            criteria_key="budget_max",
        ),
        ServiceQuestionDef(
            question_key="bedrooms",
            label="Number of bedrooms",
            type="number",
            service_category="housing",
            default=2,
            criteria_key="bedrooms",
        ),
        ServiceQuestionDef(
            question_key="sqm_min",
            label="Minimum sqm",
            type="number",
            service_category="housing",
            default=65,
            criteria_key="sqm_min",
        ),
        ServiceQuestionDef(
            question_key="commute_mins",
            label="Max commute to work (minutes)",
            type="number",
            service_category="housing",
            default=45,
            criteria_key="commute_mins",
        ),
        # Optional housing preferences — all default-off, so a case with no answers
        # still scores on sensible defaults. These populate the LivingAreasCriteria
        # fields (lifestyle_priorities / preferred_areas / avoid_areas / commute mode)
        # and the housing-agency sub-type preference.
        ServiceQuestionDef(
            question_key="commute_mode",
            label="Preferred way to commute",
            type="select",
            service_category="housing",
            required=False,
            options=[
                QuestionOption(value="transit", label="Public transit"),
                QuestionOption(value="walk", label="Walk"),
                QuestionOption(value="bike", label="Bike"),
                QuestionOption(value="car", label="Car"),
            ],
            criteria_key="commute_mode",
        ),
        ServiceQuestionDef(
            question_key="housing_lifestyle",
            label="What matters most in a neighbourhood?",
            type="multiselect",
            service_category="housing",
            required=False,
            options=[
                QuestionOption(value="safety", label="Safety"),
                QuestionOption(value="quiet", label="Quiet"),
                QuestionOption(value="green", label="Green space"),
                QuestionOption(value="nightlife", label="Nightlife"),
            ],
            criteria_key="housing_lifestyle",
        ),
        ServiceQuestionDef(
            question_key="housing_subtype",
            label="Type of housing to start with",
            type="select",
            service_category="housing",
            required=False,
            options=[
                QuestionOption(value="", label="No preference"),
                QuestionOption(value="temporary", label="Temporary (serviced apartments)"),
                QuestionOption(value="permanent", label="Permanent (rental agency)"),
            ],
            criteria_key="housing_subtype",
        ),
        ServiceQuestionDef(
            question_key="preferred_areas",
            label="Neighbourhoods you'd prefer (comma-separated, optional)",
            type="text",
            service_category="housing",
            required=False,
            placeholder="e.g. Frogner, Grünerløkka",
            criteria_key="preferred_areas",
        ),
        ServiceQuestionDef(
            question_key="avoid_areas",
            label="Neighbourhoods to avoid (comma-separated, optional)",
            type="text",
            service_category="housing",
            required=False,
            criteria_key="avoid_areas",
        ),
        # [Phase 0] Office address is no longer asked here — it duplicated the
        # intake wizard's office field. Recommendations now source the office
        # address from the case's assignmentContext.workLocation (single source),
        # geocoded server-side for real commute scoring.
        # Schools
        ServiceQuestionDef(
            question_key="child_ages",
            label="Children's ages (comma-separated, e.g. 5,8)",
            type="text",
            service_category="schools",
            default="8",
            prefill_source="case.dependents_ages",
            criteria_key="child_ages",
        ),
        ServiceQuestionDef(
            question_key="school_type",
            label="School type",
            type="select",
            service_category="schools",
            options=[
                QuestionOption(value="american", label="American"),
                QuestionOption(value="british", label="British"),
                QuestionOption(value="either", label="Either / No preference"),
                QuestionOption(value="french", label="French"),
                QuestionOption(value="german", label="German"),
                QuestionOption(value="international", label="International"),
                QuestionOption(value="private", label="Private"),
                QuestionOption(value="public", label="Public"),
            ],
            default="international",
            criteria_key="school_type",
        ),
        ServiceQuestionDef(
            question_key="curriculum",
            label="Curriculum preference",
            type="select",
            service_category="schools",
            options=[
                QuestionOption(value="either", label="Either"),
                QuestionOption(value="international", label="International (IB, etc.)"),
                QuestionOption(value="local", label="Local"),
            ],
            default="international",
            criteria_key="curriculum",
        ),
        ServiceQuestionDef(
            question_key="school_budget",
            label="School budget level",
            type="select",
            service_category="schools",
            options=[
                QuestionOption(value="high", label="High"),
                QuestionOption(value="low", label="Low"),
                QuestionOption(value="medium", label="Medium"),
            ],
            default="medium",
            criteria_key="budget_level",
        ),
        # Movers
        ServiceQuestionDef(
            question_key="origin_city",
            label="Origin city",
            type="text",
            service_category="movers",
            default="",
            prefill_source="case.originCity",
            criteria_key="origin_city",
        ),
        ServiceQuestionDef(
            question_key="move_type",
            label="Move type",
            type="select",
            service_category="movers",
            options=[
                QuestionOption(value="domestic", label="Domestic"),
                QuestionOption(value="international", label="International"),
            ],
            default="international",
            criteria_key="move_type",
        ),
        ServiceQuestionDef(
            question_key="acc_type",
            label="Current accommodation type",
            type="select",
            service_category="movers",
            options=[
                QuestionOption(value="apartment", label="Apartment"),
                QuestionOption(value="house", label="House"),
                QuestionOption(value="studio", label="Studio"),
            ],
            default="apartment",
            criteria_key="acc_type",
        ),
        ServiceQuestionDef(
            question_key="acc_bedrooms",
            label="Current bedrooms",
            type="number",
            service_category="movers",
            default=2,
            criteria_key="acc_bedrooms",
        ),
        ServiceQuestionDef(
            question_key="people",
            label="Number of people moving",
            type="number",
            service_category="movers",
            default=2,
            criteria_key="people",
        ),
        ServiceQuestionDef(
            question_key="packing",
            label="Packing service",
            type="select",
            service_category="movers",
            options=[
                QuestionOption(value="full", label="Full"),
                QuestionOption(value="partial", label="Partial"),
                QuestionOption(value="self", label="Self"),
            ],
            default="partial",
            criteria_key="packing_service",
        ),
        # Banks
        ServiceQuestionDef(
            question_key="bank_lang",
            label="Preferred languages",
            type="select",
            service_category="banks",
            options=[
                QuestionOption(value="ar", label="Arabic"),
                QuestionOption(value="zh", label="Chinese"),
                QuestionOption(value="nl", label="Dutch"),
                QuestionOption(value="en", label="English"),
                QuestionOption(value="fr", label="French"),
                QuestionOption(value="de", label="German"),
                QuestionOption(value="hi", label="Hindi"),
                QuestionOption(value="it", label="Italian"),
                QuestionOption(value="ja", label="Japanese"),
                QuestionOption(value="ko", label="Korean"),
                QuestionOption(value="pt", label="Portuguese"),
                QuestionOption(value="ru", label="Russian"),
                QuestionOption(value="es", label="Spanish"),
            ],
            default="en",
            criteria_key="preferred_languages",
        ),
        ServiceQuestionDef(
            question_key="bank_fees",
            label="Fee sensitivity",
            type="select",
            service_category="banks",
            options=[
                QuestionOption(value="high", label="Premium acceptable"),
                QuestionOption(value="low", label="Low fees important"),
                QuestionOption(value="medium", label="Balanced"),
            ],
            default="medium",
            criteria_key="fee_sensitivity",
        ),
        # [ANDREA-P1] Temporary accommodation (serviced / short-stay bridge before a lease)
        ServiceQuestionDef(
            question_key="temp_stay_weeks",
            label="How many weeks of temporary accommodation do you expect to need?",
            type="number",
            service_category="temp_accommodation",
            default=4,
            criteria_key="stay_weeks",
        ),
        ServiceQuestionDef(
            question_key="temp_budget_weekly",
            label="Weekly budget for temporary accommodation (destination currency)",
            type="number",
            service_category="temp_accommodation",
            criteria_key="budget_weekly",
        ),
        ServiceQuestionDef(
            question_key="temp_household_size",
            label="How many people will stay?",
            type="number",
            service_category="temp_accommodation",
            default=1,
            prefill_source="case.familySize",
            criteria_key="household_size",
        ),
        # [ANDREA-P1] Medical (GP registration on arrival)
        ServiceQuestionDef(
            question_key="medical_languages",
            label="Preferred languages at the practice",
            type="multiselect",
            service_category="medical",
            options=[
                QuestionOption(value="en", label="English"),
                QuestionOption(value="es", label="Spanish"),
                QuestionOption(value="fr", label="French"),
                QuestionOption(value="pt", label="Portuguese"),
            ],
            default=["en"],
            criteria_key="preferred_languages",
        ),
        # [ANDREA-P1] Language courses (accompanying partner / family)
        ServiceQuestionDef(
            question_key="language_level",
            label="Current level in the destination language",
            type="select",
            service_category="language",
            options=[
                QuestionOption(value="none", label="None"),
                QuestionOption(value="basic", label="Basic"),
                QuestionOption(value="intermediate", label="Intermediate"),
                QuestionOption(value="advanced", label="Advanced"),
            ],
            default="basic",
            criteria_key="language_level",
        ),
        # Insurances
        ServiceQuestionDef(
            question_key="ins_type",
            label="What type of insurance do you need?",
            type="select",
            service_category="insurances",
            options=[
                QuestionOption(value="health", label="Health"),
                QuestionOption(value="travel", label="Travel"),
                QuestionOption(value="housing", label="Housing / Home"),
                QuestionOption(value="car", label="Car"),
                QuestionOption(value="personal", label="Personal"),
                QuestionOption(value="family", label="Family"),
                QuestionOption(value="liability", label="Liability"),
            ],
            default="health",
            criteria_key="insurance_type",
        ),
        ServiceQuestionDef(
            question_key="ins_coverage",
            label="Additional coverage types (optional)",
            type="text",
            service_category="insurances",
            placeholder="e.g. health, travel",
            default="",
            criteria_key="coverage_types",
        ),
        ServiceQuestionDef(
            question_key="ins_family",
            label="Family coverage needed",
            type="checkbox",
            service_category="insurances",
            default=True,
            criteria_key="family_coverage",
        ),
        # Electricity
        ServiceQuestionDef(
            question_key="elec_green",
            label="Prefer green electricity",
            type="checkbox",
            service_category="electricity",
            default=True,
            criteria_key="green_preference",
        ),
        ServiceQuestionDef(
            question_key="elec_flex",
            label="Contract flexibility",
            type="select",
            service_category="electricity",
            options=[
                QuestionOption(value="high", label="High (short-term ok)"),
                QuestionOption(value="low", label="Low (long-term preferred)"),
                QuestionOption(value="medium", label="Medium"),
            ],
            default="medium",
            criteria_key="contract_flexibility",
        ),
        # Pets — replaces the standalone PetRelocationCard (species / count / needs).
        ServiceQuestionDef(
            question_key="pet_species",
            label="Species",
            type="select",
            service_category="pets",
            options=[
                QuestionOption(value="dog", label="Dog"),
                QuestionOption(value="cat", label="Cat"),
                QuestionOption(value="bird", label="Bird"),
                QuestionOption(value="other", label="Other"),
            ],
            default="dog",
            criteria_key="species",
        ),
        ServiceQuestionDef(
            question_key="pet_count",
            label="Number of pets",
            type="number",
            service_category="pets",
            default=1,
            criteria_key="count",
        ),
        ServiceQuestionDef(
            question_key="pet_specific_needs",
            label="Specific needs",
            type="text",
            service_category="pets",
            default="",
            placeholder="e.g. large breed, medical needs, quarantine questions",
            criteria_key="specific_needs",
        ),
        # Spouse / partner career — same option values as intake.
        ServiceQuestionDef(
            question_key="spouse_employment",
            label="Partner employment status",
            type="select",
            service_category="spouse",
            options=[
                QuestionOption(value="Working", label="Working"),
                QuestionOption(value="Not working", label="Not working"),
                QuestionOption(value="Student", label="Student"),
            ],
            default="Working",
            prefill_source="case.familyMembers.spouse.employment",
            criteria_key="employment",
        ),
        ServiceQuestionDef(
            question_key="spouse_language",
            label="Partner language level at destination",
            type="select",
            service_category="spouse",
            options=[
                QuestionOption(value="Fluent", label="Fluent"),
                QuestionOption(value="Conversational", label="Conversational"),
                QuestionOption(value="Beginner", label="Beginner"),
                QuestionOption(value="None", label="None"),
            ],
            default="Beginner",
            prefill_source="case.familyMembers.spouse.languageLevel",
            criteria_key="language_level",
        ),
        ServiceQuestionDef(
            question_key="spouse_wants_to_work",
            label="Partner wants to work or look for work at destination",
            type="checkbox",
            service_category="spouse",
            default=True,
            prefill_source="case.familyMembers.spouse.wantsToWork",
            criteria_key="wants_to_work",
        ),
    ]


SERVICE_QUESTION_BANK: List[ServiceQuestionDef] = _bank()


def get_questions_for_services(service_categories: List[str]) -> List[ServiceQuestionDef]:
    """Return questions filtered by selected service categories."""
    cats = set(c.strip().lower() for c in service_categories if c)
    return [q for q in SERVICE_QUESTION_BANK if q.service_category.lower() in cats]

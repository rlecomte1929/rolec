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
        ServiceQuestionDef(
            question_key="budget_min",
            label="Min monthly budget (SGD)",
            type="number",
            service_category="housing",
            default=2000,
            criteria_key="budget_min",
        ),
        ServiceQuestionDef(
            question_key="budget_max",
            label="Max monthly budget (SGD)",
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
        ServiceQuestionDef(
            question_key="office_address",
            label="Office/work address (optional)",
            type="text",
            service_category="housing",
            placeholder="e.g. Raffles Place MRT, Singapore",
            criteria_key="office_address",
        ),
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
    ]


SERVICE_QUESTION_BANK: List[ServiceQuestionDef] = _bank()


def get_questions_for_services(service_categories: List[str]) -> List[ServiceQuestionDef]:
    """Return questions filtered by selected service categories."""
    cats = set(c.strip().lower() for c in service_categories if c)
    return [q for q in SERVICE_QUESTION_BANK if q.service_category.lower() in cats]

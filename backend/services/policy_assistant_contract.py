"""
Bounded relocation policy Q&A assistant — backend contract only.

The assistant answers only from validated company policy data for the relevant case/company.
It does not provide general legal, tax, immigration, travel, or lifestyle advice.

See docs/policy/policy-assistant-contract.md for product rules and role scoping.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Intents (classification output from router / LLM guard)
# ---------------------------------------------------------------------------


class PolicyAssistantIntent(str, Enum):
    """Supported user question intents. Anything else routes to refusal or clarification."""

    POLICY_ENTITLEMENT_QUESTION = "policy_entitlement_question"
    """What am I entitled to under the policy for a specific benefit topic?"""

    POLICY_COMPARISON_QUESTION = "policy_comparison_question"
    """How does this policy compare (e.g. scenarios, limits) within allowed comparison surfaces."""

    POLICY_STATUS_QUESTION = "policy_status_question"
    """Is the policy published, under review, or visible to me?"""

    DRAFT_VS_PUBLISHED_QUESTION = "draft_vs_published_question"
    """HR-focused: differences or status between draft normalization and published version."""

    EMPLOYEE_VISIBILITY_QUESTION = "employee_visibility_question"
    """HR: what employees currently see (published vs draft) at a policy level."""

    OVERRIDE_EFFECT_QUESTION = "override_effect_question"
    """HR: effect of HR benefit rule overrides when derivable from loaded version data."""

    UNSUPPORTED_QUESTION = "unsupported_question"
    """Clearly out of scope (general chat, legal/tax/immigration/travel/lifestyle)."""

    AMBIGUOUS_QUESTION = "ambiguous_question"
    """Cannot map safely to policy data without disambiguation."""


# ---------------------------------------------------------------------------
# Canonical topics (subset aligned with ReloPass benefit taxonomy / LTA surface)
# ---------------------------------------------------------------------------


class PolicyAssistantCanonicalTopic(str, Enum):
    """Policy topics the assistant is allowed to discuss when grounded in company data."""

    TEMPORARY_HOUSING = "temporary_housing"
    HOME_SEARCH = "home_search"
    SHIPMENT = "shipment"
    SCHOOL_SEARCH = "school_search"
    SPOUSE_SUPPORT = "spouse_support"
    VISA_SUPPORT = "visa_support"
    WORK_PERMIT_SUPPORT = "work_permit_support"
    TAX_BRIEFING = "tax_briefing"
    TAX_RETURN_SUPPORT = "tax_return_support"
    HOME_LEAVE = "home_leave"
    RELOCATION_ALLOWANCE = "relocation_allowance"
    HOST_HOUSING = "host_housing"


POLICY_ASSISTANT_TOPIC_ORDER: Tuple[PolicyAssistantCanonicalTopic, ...] = (
    PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
    PolicyAssistantCanonicalTopic.HOME_SEARCH,
    PolicyAssistantCanonicalTopic.SHIPMENT,
    PolicyAssistantCanonicalTopic.SCHOOL_SEARCH,
    PolicyAssistantCanonicalTopic.SPOUSE_SUPPORT,
    PolicyAssistantCanonicalTopic.VISA_SUPPORT,
    PolicyAssistantCanonicalTopic.WORK_PERMIT_SUPPORT,
    PolicyAssistantCanonicalTopic.TAX_BRIEFING,
    PolicyAssistantCanonicalTopic.TAX_RETURN_SUPPORT,
    PolicyAssistantCanonicalTopic.HOME_LEAVE,
    PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE,
    PolicyAssistantCanonicalTopic.HOST_HOUSING,
)


# ---------------------------------------------------------------------------
# Answer typing
# ---------------------------------------------------------------------------


class PolicyAssistantAnswerType(str, Enum):
    """Shape of the grounded response."""

    ENTITLEMENT_SUMMARY = "entitlement_summary"
    COMPARISON_SUMMARY = "comparison_summary"
    STATUS_SUMMARY = "status_summary"
    DRAFT_PUBLISHED_SUMMARY = "draft_published_summary"
    CLARIFICATION_NEEDED = "clarification_needed"
    REFUSAL = "refusal"


class PolicyAssistantPolicyStatus(str, Enum):
    """Visibility / lifecycle of policy content used for the answer."""

    PUBLISHED = "published"
    DRAFT = "draft"
    DRAFT_AND_PUBLISHED = "draft_and_published"
    NO_POLICY_BOUND = "no_policy_bound"
    UNKNOWN = "unknown"


class PolicyAssistantRoleScope(str, Enum):
    """Which role context the answer was computed under (enforcement is server-side)."""

    EMPLOYEE = "employee"
    HR = "hr"


class PolicyAssistantComparisonReadiness(str, Enum):
    """Aligned with grouped policy comparison readiness strings where applicable."""

    COMPARISON_READY = "comparison_ready"
    INFORMATIONAL_ONLY = "informational_only"
    EXTERNAL_REFERENCE_PARTIAL = "external_reference_partial"
    REVIEW_REQUIRED = "review_required"
    DETERMINISTIC_NON_BUDGET = "deterministic_non_budget"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Refusal
# ---------------------------------------------------------------------------


class PolicyAssistantRefusalCode(str, Enum):
    OUT_OF_SCOPE_GENERAL = "out_of_scope_general"
    # Legacy umbrella; prefer granular legal / tax / immigration codes for new guardrails.
    OUT_OF_SCOPE_LEGAL_TAX_IMMIGRATION_TRAVEL = "out_of_scope_legal_tax_immigration_travel"

    OUT_OF_SCOPE_LEGAL_ADVICE = "out_of_scope_legal_advice"
    OUT_OF_SCOPE_TAX_BEYOND_POLICY = "out_of_scope_tax_beyond_policy"
    OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY = "out_of_scope_immigration_beyond_policy"
    OUT_OF_SCOPE_NEGOTIATION = "out_of_scope_negotiation"
    OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE = "out_of_scope_school_or_neighborhood_advice"
    OUT_OF_SCOPE_TRAVEL_OR_LIFESTYLE = "out_of_scope_travel_or_lifestyle"
    OUT_OF_SCOPE_UNRELATED_CHAT = "out_of_scope_unrelated_chat"

    NO_PUBLISHED_POLICY_EMPLOYEE = "no_published_policy_employee"
    NO_POLICY_CONTEXT = "no_policy_context"
    AMBIGUOUS_OR_UNGROUNDED = "ambiguous_or_ungrounded"
    ROLE_FORBIDDEN_DRAFT = "role_forbidden_draft"
    INSUFFICIENT_POLICY_DATA = "insufficient_policy_data"


class PolicyAssistantRefusal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refusal_code: PolicyAssistantRefusalCode = Field(
        ..., description="Machine-readable reason the assistant did not answer substantively."
    )
    refusal_text: str = Field(
        ...,
        max_length=4000,
        description="HR/employee-safe explanation; no hallucinated law or external facts.",
    )
    supported_examples: List[str] = Field(
        default_factory=list,
        description="Short example questions the user may ask instead (policy-grounded).",
    )


# ---------------------------------------------------------------------------
# Evidence & conditions (grounding hooks)
# ---------------------------------------------------------------------------


class PolicyAssistantEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(
        ...,
        description="e.g. benefit_rule, exclusion, policy_clause, normalization_draft_row, grouped_policy_item",
    )
    label: Optional[str] = Field(None, description="Human-readable label for UI.")
    reference: Optional[str] = Field(None, description="Internal id or stable key, not necessarily exposed to client.")
    excerpt: Optional[str] = Field(None, max_length=2000, description="Verbatim or near-verbatim policy text snippet.")
    source: Optional[str] = Field(None, description="e.g. published_matrix, draft_review, version_id")
    section_ref: Optional[str] = Field(None, description="Policy section reference when available (e.g. 3.2).")
    policy_source_type: Optional[str] = Field(
        None,
        description="Stable type: published_benefit_rule, draft_grouped_item, published_exclusion, etc.",
    )


class PolicyAssistantConditionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=2000, description="Applicability or condition in plain language.")
    kind: Optional[str] = Field(None, description="e.g. assignment_type, family_status, duration, approval")


class PolicyAssistantFollowUpOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: PolicyAssistantIntent = Field(..., description="Suggested intent if the user selects this follow-up.")
    label: str = Field(..., max_length=500, description="Short button or chip label.")
    query_hint: Optional[str] = Field(None, max_length=1000, description="Optional templated query for the client.")


# ---------------------------------------------------------------------------
# Main response
# ---------------------------------------------------------------------------


class PolicyAssistantAnswer(BaseModel):
    """
    Single turn response from the policy assistant API.

    Server must populate fields only from validated policy payloads (DB + normalization draft
    where role allows). ``answer_text`` must not invent limits, jurisdictions, or legal conclusions.
    """

    model_config = ConfigDict(extra="forbid")

    answer_type: PolicyAssistantAnswerType = Field(..., description="Structural kind of this message.")
    canonical_topic: Optional[PolicyAssistantCanonicalTopic] = Field(
        None,
        description="Primary benefit/topic when applicable; null for pure status/refusal turns.",
    )
    answer_text: str = Field(
        default="",
        max_length=8000,
        description="Grounded natural language answer; may be empty when refusal.refusal_text is the primary UX.",
    )
    policy_status: PolicyAssistantPolicyStatus = Field(
        ...,
        description="Whether the content reflects published policy, draft, both, or none.",
    )
    comparison_readiness: PolicyAssistantComparisonReadiness = Field(
        ...,
        description="Whether numeric comparison is meaningful for this topic, per policy readiness rules.",
    )
    evidence: List[PolicyAssistantEvidenceItem] = Field(
        default_factory=list,
        description="Pointers/snippets backing the answer (may be redacted per role).",
    )
    conditions: List[PolicyAssistantConditionItem] = Field(
        default_factory=list,
        description="Applicability conditions derived from policy rules.",
    )
    approval_required: bool = Field(
        False,
        description="True when policy text indicates approval / exception path for this entitlement.",
    )
    follow_up_options: List[PolicyAssistantFollowUpOption] = Field(
        default_factory=list,
        description="Bounded next questions within policy scope.",
    )
    refusal: Optional[PolicyAssistantRefusal] = Field(
        None,
        description="Populated when the assistant cannot or must not answer substantively.",
    )
    role_scope: PolicyAssistantRoleScope = Field(
        ...,
        description="Role under which this response was generated; client must not upgrade scope.",
    )
    detected_intent: Optional[PolicyAssistantIntent] = Field(
        None,
        description="Intent classifier output for this turn (optional telemetry / UI).",
    )


# ---------------------------------------------------------------------------
# Role scoping rules (documentation + helpers for implementers)
# ---------------------------------------------------------------------------

EMPLOYEE_POLICY_ASSISTANT_RULES: Dict[str, Any] = {
    "policy_sources_allowed": ["published_policy_version", "published_benefit_matrix"],
    "policy_sources_forbidden": ["normalization_draft", "unpublished_version", "hr_review_payload_draft_slices"],
    "scope": "case_specific_and_company_bound",
    "must_refuse": [
        "draft_vs_published_detail",
        "unpublished_limits",
        "other_employees_data",
        "general_law_tax_immigration_travel_lifestyle",
    ],
}

HR_POLICY_ASSISTANT_RULES: Dict[str, Any] = {
    "policy_sources_allowed": [
        "published_policy_version",
        "published_benefit_matrix",
        "working_version",
        "normalization_draft",
        "grouped_review",
        "template_first_import",
    ],
    "policy_sources_forbidden": ["other_companies", "raw_chat_without_grounding"],
    "scope": "company_and_version_bound",
    "must_refuse": [
        "general_law_tax_immigration_travel_lifestyle",
        "legal_advice",
        "ungrounded_speculation",
    ],
}


def refusal_for_out_of_scope_travel_legal() -> PolicyAssistantRefusal:
    """Factory for standard out-of-scope refusal (no heavy deps)."""
    return PolicyAssistantRefusal(
        refusal_code=PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_TAX_IMMIGRATION_TRAVEL,
        refusal_text=(
            "I can only answer questions about your company's relocation policy in ReloPass. "
            "I can't provide general legal, tax, immigration, travel, or lifestyle advice."
        ),
        supported_examples=[
            "What temporary housing support does my policy include?",
            "Is my relocation allowance published for my assignment?",
            "What does the policy say about home leave?",
        ],
    )


def employee_may_see_draft() -> bool:
    return False


def hr_may_see_draft() -> bool:
    return True

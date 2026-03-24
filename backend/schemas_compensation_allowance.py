"""
Pydantic models for Compensation & Allowance policy configuration (structured matrix).

Kept separate from schemas.py to avoid growing the monolith; import where needed.
Ingestion hook: map normalized document clauses / tables into PolicyConfigBenefitWrite, then call
the same validate_put_body + put_draft path the UI uses (avoid a second write schema).
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PolicyConfigCategory(str, Enum):
    pre_assignment_support = "pre_assignment_support"
    relocation_assistance = "relocation_assistance"
    compensation_allowances = "compensation_allowances"
    family_support_education = "family_support_education"
    leave_repatriation = "leave_repatriation"
    tax_payroll = "tax_payroll"


class PolicyConfigVersionStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    published = "published"
    archived = "archived"


class PolicyConfigValueType(str, Enum):
    currency = "currency"
    percentage = "percentage"
    text = "text"
    none = "none"


class PolicyConfigUnitFrequency(str, Enum):
    one_time = "one_time"
    monthly = "monthly"
    yearly = "yearly"
    per_trip = "per_trip"
    per_day = "per_day"
    per_dependent = "per_dependent"
    custom = "custom"


class PolicyConfigAssignmentType(str, Enum):
    short_term = "short_term"
    long_term = "long_term"
    permanent = "permanent"
    international = "international"


class PolicyConfigFamilyStatus(str, Enum):
    single = "single"
    spouse_partner = "spouse_partner"
    dependents = "dependents"


class PolicyConfigBenefitWrite(BaseModel):
    """Payload for creating/updating one benefit row (batch save)."""

    benefit_key: str = Field(..., min_length=1)
    benefit_label: str = Field(..., min_length=1)
    category: PolicyConfigCategory
    covered: bool = False
    value_type: PolicyConfigValueType = PolicyConfigValueType.none
    amount_value: Optional[float] = None
    currency_code: Optional[str] = None
    percentage_value: Optional[float] = None
    unit_frequency: PolicyConfigUnitFrequency = PolicyConfigUnitFrequency.one_time
    cap_rule_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    conditions_json: Dict[str, Any] = Field(default_factory=dict)
    assignment_types: List[PolicyConfigAssignmentType] = Field(default_factory=list)
    family_statuses: List[PolicyConfigFamilyStatus] = Field(default_factory=list)
    is_active: bool = True
    display_order: int = 0


class PolicyConfigBenefitRead(BaseModel):
    id: str
    policy_config_version_id: str
    benefit_key: str
    benefit_label: str
    category: str
    covered: bool
    value_type: str
    amount_value: Optional[float] = None
    currency_code: Optional[str] = None
    percentage_value: Optional[float] = None
    unit_frequency: str
    cap_rule_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    conditions_json: Dict[str, Any] = Field(default_factory=dict)
    assignment_types: List[str] = Field(default_factory=list)
    family_statuses: List[str] = Field(default_factory=list)
    targeting_signature: str = "global"
    is_active: bool = True
    display_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"extra": "ignore"}


class PolicyConfigVersionRead(BaseModel):
    id: str
    policy_config_id: str
    version_number: int
    status: str
    effective_date: date
    published_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"extra": "ignore"}


class PolicyConfigRead(BaseModel):
    id: str
    company_id: str
    name: str
    config_key: str
    description: Optional[str] = None
    is_active: bool = True
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"extra": "ignore"}


class PublishedPolicyConfigBundle(BaseModel):
    """Latest published matrix for a company (employee-safe read model)."""

    config: PolicyConfigRead
    version: PolicyConfigVersionRead
    benefits: List[PolicyConfigBenefitRead]

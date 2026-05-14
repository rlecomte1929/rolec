from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


class RelocationBasicsDTO(BaseModel):
    originCountry: Optional[str] = None
    originCity: Optional[str] = None
    destCountry: Optional[str] = None
    destCity: Optional[str] = None
    purpose: Optional[str] = None
    targetMoveDate: Optional[date] = None
    durationMonths: Optional[int] = None
    hasDependents: Optional[bool] = None


class EmployeeProfileDTO(BaseModel):
    fullName: Optional[str] = None
    nationality: Optional[str] = None
    passportCountry: Optional[str] = None
    passportExpiry: Optional[date] = None
    residenceCountry: Optional[str] = None
    email: Optional[str] = None
    ocr: Optional[Dict[str, Any]] = None


class FamilyMemberDTO(BaseModel):
    fullName: Optional[str] = None
    dateOfBirth: Optional[date] = None
    relationship: Optional[str] = None
    nationality: Optional[str] = None
    wantsToWork: Optional[bool] = None


class FamilyMembersDTO(BaseModel):
    maritalStatus: Optional[str] = None
    spouse: Optional[FamilyMemberDTO] = None
    children: Optional[List[FamilyMemberDTO]] = None


class AssignmentContextDTO(BaseModel):
    employerName: Optional[str] = None
    employerCountry: Optional[str] = None
    workLocation: Optional[str] = None
    contractStartDate: Optional[date] = None
    contractType: Optional[str] = None
    salaryBand: Optional[str] = None
    jobTitle: Optional[str] = None
    seniorityBand: Optional[str] = None


class CaseDraftDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    relocationBasics: Optional[RelocationBasicsDTO] = None
    employeeProfile: Optional[EmployeeProfileDTO] = None
    familyMembers: Optional[FamilyMembersDTO] = None
    assignmentContext: Optional[AssignmentContextDTO] = None


class CaseDTO(BaseModel):
    id: str
    status: str
    draft: CaseDraftDTO
    createdAt: datetime
    updatedAt: datetime
    originCountry: Optional[str] = None
    originCity: Optional[str] = None
    destCountry: Optional[str] = None
    destCity: Optional[str] = None
    purpose: Optional[str] = None
    targetMoveDate: Optional[date] = None
    flags: Dict[str, Any] = {}
    requirementsSnapshotId: Optional[str] = None


class SourceRecordDTO(BaseModel):
    id: str
    url: str
    title: str
    publisherDomain: str
    retrievedAt: datetime
    snippet: Optional[str] = None


class RequirementItemDTO(BaseModel):
    id: str
    pillar: str
    title: str
    description: str
    severity: str
    owner: str
    requiredFields: List[str]
    statusForCase: str
    citations: List[SourceRecordDTO]


class CountryProfileDTO(BaseModel):
    countryCode: str
    lastUpdatedAt: Optional[datetime] = None
    confidenceScore: Optional[float] = None
    sources: List[SourceRecordDTO] = []
    requirementGroups: List[Dict[str, Any]] = []


class CountryListItemDTO(BaseModel):
    countryCode: str
    lastUpdatedAt: Optional[datetime] = None
    requirementsCount: int
    confidenceScore: Optional[float] = None
    topDomains: List[str]


class CountryListDTO(BaseModel):
    countries: List[CountryListItemDTO]


class CaseRequirementsDTO(BaseModel):
    caseId: str
    destCountry: str
    purpose: str
    computedAt: datetime
    requirements: List[RequirementItemDTO]
    sources: List[SourceRecordDTO]


class AssignmentType(str, Enum):
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    PERMANENT = "permanent"
    COMMUTER = "commuter"
    EXTENDED_BUSINESS_TRIP = "extended_business_trip"
    INTERNATIONAL = "international"


class Phase(str, Enum):
    PRE_ASSIGNMENT = "pre_assignment"
    ON_ASSIGNMENT = "on_assignment"
    REPATRIATION = "repatriation"
    ONGOING = "ongoing"
    EXCEPTION = "exception"


class BenefitCategory(str, Enum):
    HOUSING = "housing"
    TEMPORARY_HOUSING = "temporary_housing"
    TRAVEL = "travel"
    SHIPMENT = "shipment"
    IMMIGRATION = "immigration"
    TAX = "tax"
    SCHOOLING = "schooling"
    ALLOWANCE = "allowance"
    MOBILITY_PREMIUM = "mobility_premium"
    SPOUSE_SUPPORT = "spouse_support"
    HOME_LEAVE = "home_leave"
    TRANSPORTATION = "transportation"
    MEALS = "meals"
    MISCELLANEOUS = "miscellaneous"


class ValueType(str, Enum):
    MONETARY = "monetary"
    PERCENTAGE = "percentage"
    BOOLEAN = "boolean"
    DURATION = "duration"
    QUANTITY = "quantity"
    TEXT = "text"


class Frequency(str, Enum):
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    PER_ASSIGNMENT = "per_assignment"
    PER_TRIP = "per_trip"
    PER_CHILD = "per_child"
    PER_FAMILY = "per_family"
    RECURRING = "recurring"


class ProviderEntity(str, Enum):
    COMPANY = "company"
    EMPLOYEE = "employee"
    VENDOR = "vendor"
    PAYROLL = "payroll"
    HR = "hr"
    MOBILITY_TEAM = "mobility_team"
    INSURER = "insurer"
    TAX_PROVIDER = "tax_provider"
    IMMIGRATION_PROVIDER = "immigration_provider"
    UNKNOWN = "unknown"


class PolicyFactEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_types: List[AssignmentType] = Field(default_factory=list)
    family_statuses: List[str] = Field(default_factory=list)
    min_duration_months: Optional[int] = None
    notes: Optional[str] = None


class PolicyDocumentCanonicalBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    source_policy_document_id: Optional[str] = None
    source_type: str = "local_file"
    source_uri: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    title: Optional[str] = None
    policy_scope: Optional[str] = None
    document_type: Optional[str] = None
    version_label: Optional[str] = None
    effective_date: Optional[date] = None
    default_currency: Optional[str] = None
    assignment_types: List[AssignmentType] = Field(default_factory=list)
    raw_text: Optional[str] = None
    normalized_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ingestion_status: str = "ingested"
    extraction_status: str = "pending"


class PolicyDocumentCanonicalCreate(PolicyDocumentCanonicalBase):
    pass


class PolicyDocumentCanonicalRead(PolicyDocumentCanonicalBase):
    id: str
    created_at: datetime
    updated_at: datetime


class PolicyDocumentChunkCanonicalBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    canonical_policy_document_id: str
    chunk_index: int
    section_path: Optional[str] = None
    structure_type: Optional[str] = None
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    text_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyDocumentChunkCanonicalCreate(PolicyDocumentChunkCanonicalBase):
    pass


class PolicyDocumentChunkCanonicalRead(PolicyDocumentChunkCanonicalBase):
    id: str
    created_at: datetime


class PolicyFactCanonicalBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    canonical_policy_document_id: str
    canonical_policy_document_chunk_id: str
    source_policy_document_id: Optional[str] = None
    phase: Optional[Phase] = None
    benefit_category: Optional[BenefitCategory] = None
    value_type: ValueType
    frequency: Optional[Frequency] = None
    provider_entity: Optional[ProviderEntity] = None
    title: Optional[str] = None
    description: Optional[str] = None
    eligibility: PolicyFactEligibility = Field(default_factory=PolicyFactEligibility)
    assignment_types: List[AssignmentType] = Field(default_factory=list)
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    percentage: Optional[float] = None
    quantity: Optional[float] = None
    duration_value: Optional[int] = None
    duration_unit: Optional[str] = None
    value_text: Optional[str] = None
    is_taxable: Optional[bool] = None
    reimbursement_required: Optional[bool] = None
    source_quote: Optional[str] = None
    confidence_score: Optional[float] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class PolicyFactLLMRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Optional[Phase] = None
    benefit_category: Optional[BenefitCategory] = None
    value_type: ValueType
    frequency: Optional[Frequency] = None
    provider_entity: Optional[ProviderEntity] = None
    title: Optional[str] = None
    description: Optional[str] = None
    eligibility: PolicyFactEligibility = Field(default_factory=PolicyFactEligibility)
    assignment_types: List[AssignmentType] = Field(default_factory=list)
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    percentage: Optional[float] = None
    quantity: Optional[float] = None
    duration_value: Optional[int] = None
    duration_unit: Optional[str] = None
    value_text: Optional[str] = None
    is_taxable: Optional[bool] = None
    reimbursement_required: Optional[bool] = None
    source_quote: Optional[str] = None
    confidence_score: Optional[float] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class PolicyFactCanonicalCreate(PolicyFactCanonicalBase):
    pass


class PolicyFactCanonicalRead(PolicyFactCanonicalBase):
    id: str
    created_at: datetime


class PolicyFactExtractionLLMInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    title: Optional[str] = None
    section_path: Optional[str] = None
    structure_type: Optional[str] = None
    page_number: Optional[int] = None
    text_content: str
    default_currency: Optional[str] = None
    assignment_types: List[AssignmentType] = Field(default_factory=list)


class PolicyFactExtractionLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: List[PolicyFactLLMRecord] = Field(default_factory=list)


class PolicyFactValidationErrorRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    company_id: str
    canonical_policy_document_id: str
    canonical_policy_document_chunk_id: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime


class CanonicalPolicyRenderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    canonical_policy_document_id: str
    title: str
    markdown: str


class CanonicalPolicyQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    canonical_policy_document_id: Optional[str] = None


class CanonicalPolicyQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    canonical_policy_document_id: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    retrieved_chunk_ids: List[str] = Field(default_factory=list)


class QueryAuditLogRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    company_id: str
    user_id: str
    user_role: str
    canonical_policy_document_id: str
    query_text: str
    redacted_query_text: str
    retrieved_chunk_ids: List[str] = Field(default_factory=list)
    answer_preview: Optional[str] = None
    created_at: datetime

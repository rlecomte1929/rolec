from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
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
    employment: Optional[str] = None
    languageLevel: Optional[str] = None


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
    # AIQ-1349: STA / LTA / PERMANENT — without this field the PATCH body's
    # assignmentType is silently dropped (CaseDraftDTO is extra="ignore"), so the
    # canonical-case bridge never sees it. Drives duration-aware policy + roadmap.
    assignmentType: Optional[str] = None
    expectedDurationMonths: Optional[int] = None
    # AIQ-1603: single-select preferred commute mode, validated against a fixed enum so an
    # invalid value is a 422 (not silent bad data). Bridged onto public.cases.commute_preference.
    commutePreference: Optional[str] = None

    @field_validator("commutePreference")
    @classmethod
    def _valid_commute(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"car", "public_transport", "bike", "walk", "no_preference"}
        if v not in allowed:
            raise ValueError(f"commutePreference must be one of {sorted(allowed)}")
        return v

    @field_validator("expectedDurationMonths")
    @classmethod
    def _positive_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("expectedDurationMonths must be a positive integer")
        return v


class CaseDraftDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    relocationBasics: Optional[RelocationBasicsDTO] = None
    employeeProfile: Optional[EmployeeProfileDTO] = None
    familyMembers: Optional[FamilyMembersDTO] = None
    assignmentContext: Optional[AssignmentContextDTO] = None
    # Employee wizard Step 2 — selected relocation services
    services: Optional[List[str]] = None


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
    #: Optional because only a `source_records` row actually records a retrieval time. A
    #: citation stored as a bare URL or an inline object was never retrieved by us, and this
    #: field drives the client's StalenessBadge — inventing a timestamp here would manufacture
    #: a freshness claim for a page nobody has checked. None renders no badge.
    retrievedAt: Optional[datetime] = None
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
    # AIQ-1349: provenance level for this requirement.
    verificationStatus: Optional[str] = None
    # True when the row carries an unresolved `needs_lawyer_review` flag and no counsel
    # attestation yet: it is SERVED, but the UI badges it "Legal review pending — not
    # independently legal-reviewed." Honest caveat, not a claim anyone reviewed it. Drops to
    # False/None once `attestation_status='attested'`. See services/lawyer_review_gate.py.
    legalReviewPending: Optional[bool] = None
    # A real obligation the person would not anticipate. Optional, not `bool = False`:
    # an engine-synthesised item has no such data, and null ("not modeled") must stay
    # distinguishable from false ("modeled, and it is obvious").
    nonObvious: Optional[bool] = None
    # Free-text deadline verbatim from the source ("within 8 days of arrival"). None
    # when the source states no deadline.
    timing: Optional[str] = None
    # Counsel attestation — ORTHOGONAL to verificationStatus, never a rung on the same
    # ladder. That one is our own provenance (representative -> corpus_grounded ->
    # verified); this is external legal sign-off. models.py says it plainly: "Sellable
    # means BOTH". Kept as separate fields so the UI cannot collapse them and let
    # "Expert-verified" read as counsel-assured, which is the one claim we cannot make.
    #
    # None means no counsel has looked at this. That is the honest default and the state
    # of every row in production today — it must render as ABSENCE, never as a downgrade
    # badge and never as reassurance.
    attestationStatus: Optional[str] = None   # None | requested | attested | stale
    attestedBy: Optional[str] = None          # the firm, e.g. "Wikborg Rein"
    attestedAt: Optional[datetime] = None
    # 'action' (the default — something is required of someone) or
    # 'nothing_to_do' (a STATED positive confirmation that nothing is required).
    # A correct answer of "none" must be stated, never implied by an empty list.
    outcomeType: str = "action"
    # Why nothing is required. Mandatory when outcomeType == 'nothing_to_do' —
    # a confirmation without a reason is indistinguishable from a bug.
    reason: Optional[str] = None


class CountryProfileDTO(BaseModel):
    countryCode: str
    lastUpdatedAt: Optional[datetime] = None
    confidenceScore: Optional[float] = None
    sources: List[SourceRecordDTO] = []
    requirementGroups: List[Dict[str, Any]] = []


class AdminCitationDTO(BaseModel):
    """One resolved citation, as the review surface needs it.

    Not `SourceRecordDTO`, for one reason: `url` here is Optional. `citations_json` holds
    `source_records` ids, and some of them dangle — FRANCE carries 14 non-URL string citations
    of which only 4 resolve. The employee reader is right to drop an unresolvable reference;
    the reviewer is the one person who has to SEE that a requirement's only citation points at
    nothing, because they are the one about to publish it. A dangling reference therefore
    arrives with its raw text as the title and no `url` to link to.

    No `retrievedAt`/`snippet`: the review surface links out and reads the page itself.
    """

    #: The `source_records` id, else the URL, else the raw text. Stable, and the client's key.
    id: str
    url: Optional[str] = None
    title: str
    publisherDomain: Optional[str] = None


class AdminRequirementReviewDTO(BaseModel):
    """One requirement as an ADMIN needs to see it before deciding to publish it.

    Deliberately not `RequirementItemDTO`: that one is the employee-facing shape and carries no
    review fields. An admin needs the sources, the provenance, the nationality scope and the
    review state — the things the decision actually turns on.
    """

    id: str
    purpose: str
    pillar: str
    title: str
    description: str
    severity: str
    owner: str
    # How well-sourced: representative | corpus_grounded | expert_verified. A badge.
    verificationStatus: Optional[str] = None
    # The human signature behind verificationStatus='expert_verified' (verified-write
    # guardrail): who signed it off and when. NULL until a human verifies.
    verifiedBy: Optional[str] = None
    verifiedAt: Optional[datetime] = None
    # Whether it is served: pending | approved | rejected. The gate.
    reviewStatus: str = "approved"
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[datetime] = None
    # None ⇒ applies to every nationality class. Shown explicitly because a NULL here is what
    # serves a third-country visa track to an EU free mover.
    appliesToNationalityClasses: Optional[List[str]] = None
    appliesToAssignmentTypes: Optional[List[str]] = None
    citations: List[AdminCitationDTO] = []
    lastVerifiedAt: Optional[datetime] = None
    # Counsel attestation — ORTHOGONAL to verificationStatus, never a rung on the same
    # ladder. That one is our own provenance (representative -> corpus_grounded ->
    # verified); this is external legal sign-off. models.py says it plainly: "Sellable
    # means BOTH". Kept as separate fields so the UI cannot collapse them and let
    # "Expert-verified" read as counsel-assured, which is the one claim we cannot make.
    #
    # None means no counsel has looked at this. That is the honest default and the state
    # of every row in production today — it must render as ABSENCE, never as a downgrade
    # badge and never as reassurance.
    attestationStatus: Optional[str] = None   # None | requested | attested | stale
    attestedBy: Optional[str] = None          # the firm, e.g. "Wikborg Rein"
    attestedAt: Optional[datetime] = None


class KnowledgeScorecardDTO(BaseModel):
    """Catalog sufficiency for one destination. Not a McKinsey index; bars live in the scorer."""

    approvedCount: int
    pendingCount: int
    rejectedCount: int = 0
    citationResolvedApproved: int
    citationResolvePct: float
    pillarsPresent: List[str] = []
    lastHumanReviewAt: Optional[datetime] = None
    catalogReady: bool
    notReadyReason: Optional[str] = None


class AdminRequirementListDTO(BaseModel):
    countryCode: str
    pendingCount: int = 0
    items: List[AdminRequirementReviewDTO] = []
    scorecard: Optional[KnowledgeScorecardDTO] = None


class AdminRequirementReviewRequest(BaseModel):
    status: str  # approved | rejected


class CountryListItemDTO(BaseModel):
    countryCode: str
    lastUpdatedAt: Optional[datetime] = None
    requirementsCount: int
    confidenceScore: Optional[float] = None
    topDomains: List[str]
    catalogReady: Optional[bool] = None
    notReadyReason: Optional[str] = None


class CountryListDTO(BaseModel):
    countries: List[CountryListItemDTO]


class CaseRequirementsDTO(BaseModel):
    caseId: str
    destCountry: str
    purpose: str
    computedAt: datetime
    requirements: List[RequirementItemDTO]
    sources: List[SourceRecordDTO]
    # AIQ-1349: non-liability disclaimer + provenance level for the guidance.
    disclaimer: str = ""
    verificationStatus: Optional[str] = None
    # AIQ-1349: requirement titles waived because this is a short-term (STA)
    # assignment — surfaced so the UI can explain the shorter list.
    staWaived: List[str] = []
    # Requirement titles waived because the employee's nationality exempts them
    # (an EU/EEA national needs none of the non-EEA visa track). Surfaced, not
    # silently dropped, so the shorter list is explainable.
    nationalityWaived: List[str] = []
    # OWN_NATIONAL | EU_EEA | THIRD_COUNTRY | None when nationality is unknown.
    nationalityClass: Optional[str] = None
    # AIQ-1473c: False when the destination doesn't resolve to a known catalog
    # key — the requirements list is then empty because we have no catalogue for
    # that country, NOT because nothing is required. Lets the UI say so instead
    # of rendering an empty list as "nothing required" (the AIQ-1349 silent-miss).
    covered: bool = True
    # Sufficiency of the destination catalog (approved + cited + multi-pillar).
    # Distinct from `covered` (unknown destination / empty approved set).
    catalogReady: Optional[bool] = None
    catalogNotReadyReason: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Document Data Sheet (Phase 1) — one composed, corridor-agnostic read-model of
# the case's data sheet: steps → fields → value + provenance. Deterministic; no
# LLM on the serve path. See docs/specs/agnostic-datasheet-and-form-fill.md.
# ─────────────────────────────────────────────────────────────────────────────

class DataSheetDeadlineDTO(BaseModel):
    date: Optional[str] = None
    isSuggested: bool = False
    isHard: bool = False


class DataSheetFieldDTO(BaseModel):
    # The template field id — the address the edit endpoint (PATCH .../fields/{fieldId}) keys on.
    fieldId: str
    # The governed fact this field references (fact_dictionary). None when the seed does not
    # yet know the field — the field still renders from its own attributes.
    factKey: Optional[str] = None
    label: str
    category: Optional[str] = None
    # Where the value came from, exactly one of:
    #   intake | passport_ocr | prior_form | needs_input | consult_professional | ai
    # `consult_professional` is the firewall: value is ALWAYS null and only `guidance` renders.
    source: str
    value: Optional[str] = None
    confidence: Optional[float] = None
    # Prompt for a `needs_input` field.
    hint: Optional[str] = None
    # Referral text for a `consult_professional` field (never a value).
    guidance: Optional[str] = None
    requiresOriginal: bool = False
    # HR-view only: what the employer must do for this field.
    employerActionNote: Optional[str] = None


class DataSheetSectionDTO(BaseModel):
    stepId: str
    title: Optional[str] = None
    authority: Optional[str] = None
    sourceUrl: Optional[str] = None
    processNote: Optional[str] = None
    channels: List[str] = []
    order: int
    # HR-view annotations (best-effort, from the corridor step-graph).
    responsibleParty: Optional[str] = None
    slaNote: Optional[str] = None
    deadline: Optional[DataSheetDeadlineDTO] = None
    fields: List[DataSheetFieldDTO] = []


class DataSheetBannerDTO(BaseModel):
    # 'moat-fact' (a non-obvious trap) or 'warning' (a hard deadline).
    type: str
    text: str


class DataSheetConsultDTO(BaseModel):
    topic: str
    reason: Optional[str] = None


class DataSheetDTO(BaseModel):
    caseRef: str
    employeeName: Optional[str] = None
    corridor: Optional[str] = None
    corridorLabel: Optional[str] = None
    movementBasis: Optional[str] = None
    generatedAt: datetime
    completionPct: int = 0
    needsInputCount: int = 0
    banners: List[DataSheetBannerDTO] = []
    sections: List[DataSheetSectionDTO] = []
    consultProfessional: List[DataSheetConsultDTO] = []
    # False when the case has no data-sheet form yet — the UI says "not available yet",
    # never renders an empty sheet as "nothing to do" (mirrors CaseRequirementsDTO.covered).
    covered: bool = True
    # True when the sheet is rendered from curated corridor-content rather than an authored,
    # fillable template — a read-only guidance preview (no per-field value can be captured yet).
    preview: bool = False


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


# ─────────────────────────────────────────────────────────────────────────────
# Counsel attestation (Phase 1). See routers/attestation.py.
#
# The public-facing DTOs below are a PII BOUNDARY, not merely a response shape. They are
# whitelists: a field reaches an external reviewer only by being named here. Do not add a
# passthrough dict, and do not widen one of these to `Dict[str, Any]`.
# ─────────────────────────────────────────────────────────────────────────────
class AttestationChecklistItemDTO(BaseModel):
    """One requirement as external counsel sees it. No case, employee or company fields."""

    id: str                                   # corridor_attestation_items.id
    title: str
    claim: Optional[str] = None
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    pillar: Optional[str] = None
    validity: Optional[str] = None            # requirement_items.timing
    confidence: Optional[str] = None          # requirement_items.verification_status
    decision: str = "pending"                 # pending | approved | amended | rejected
    reviewer_comment: Optional[str] = None
    proposed_amendment: Optional[str] = None


class AttestationPublicViewDTO(BaseModel):
    """The entire payload the tokenized reviewer receives."""

    corridor_label: str
    purpose: str
    scope: str
    status: str
    title: Optional[str] = None
    disclaimer_version: str
    disclaimer_text: str
    # Echoed so the client can send it back on sign; the server re-derives and compares.
    content_hash: str
    expires_at: Optional[datetime] = None
    items: List[AttestationChecklistItemDTO] = Field(default_factory=list)
    signed_at: Optional[datetime] = None


class AttestationDecisionIn(BaseModel):
    decision: str                             # approved | amended | rejected
    reviewer_comment: Optional[str] = None
    proposed_amendment: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def _known_decision(cls, v: str) -> str:
        allowed = {"approved", "amended", "rejected"}
        norm = (v or "").strip().lower()
        if norm not in allowed:
            raise ValueError(f"decision must be one of {sorted(allowed)}")
        return norm


class AttestationSignIn(BaseModel):
    signer_name: str = Field(min_length=1, max_length=200)
    signer_email: str = Field(min_length=3, max_length=320)
    signer_org: Optional[str] = Field(default=None, max_length=200)
    signer_credential: Optional[str] = Field(default=None, max_length=200)
    signature_method: str = "typed_name"
    # The hash the reviewer was shown. Compared against the stored snapshot hash; a
    # mismatch is a 409, because the checklist changed under them.
    content_hash: str = Field(min_length=64, max_length=64)
    # Must be explicitly true. A signature without recorded agreement to the disclaimer
    # is not evidence that the disclaimer was agreed to.
    agreed_to_disclaimer: bool


class AttestationSignatureDTO(BaseModel):
    id: str
    signer_name: str
    signer_org: Optional[str] = None
    signer_credential: Optional[str] = None
    signature_method: str
    signed_content_hash: str
    disclaimer_version: str
    signed_at: datetime
    supersedes_signature_id: Optional[str] = None


class AttestationCreateIn(BaseModel):
    country_code: str = Field(min_length=2, max_length=64)
    purpose: str = "employment"
    title: Optional[str] = None
    reviewer_org: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    reviewer_credential: Optional[str] = None
    # Explicit scope. Omitted ⇒ every approved item for the corridor except the pillars
    # that are operational rather than legal (see routers/attestation.py OPERATIONAL_PILLARS).
    requirement_item_ids: Optional[List[str]] = None
    ttl_days: Optional[int] = Field(default=None, ge=1, le=90)
    # How this attestation publishes. 'manual' (default) preserves the two-key rule:
    # signing writes a signature only, and an admin must call /promote. 'auto_on_sign'
    # is recorded now and honoured in ATT-2.4.
    #
    # Typed as a Literal so an out-of-vocabulary value is a 422 at the boundary. The
    # database CHECK (ck_cap_promotion_policy, migration 20261120000000) remains the
    # authority and the backstop — but reaching it is not an acceptable way to reject
    # a typo: the CheckViolation propagates out of the endpoint unhandled, which is a
    # 500 rather than a validation error, and psycopg2's DETAIL line renders the whole
    # failing row (content snapshot included) into the traceback. Measured on Postgres
    # 2026-08-22 before this annotation was added.
    promotion_policy: Literal["manual", "auto_on_sign"] = "manual"
    # Whether promoting this attestation may ALSO advance the item's review_status.
    # Setting it widens the snapshot to include `pending` items — an attestation that
    # can advance review_status is precisely the one that should be showing counsel the
    # not-yet-published rows. The advance itself is ATT-2.4; this flag only records the
    # intent and selects the candidates.
    advance_review_status: bool = False


class AttestationCaseCreateIn(BaseModel):
    """Create a CASE-scoped attestation — counsel signs off on one person's move.

    Deliberately a separate model from `AttestationCreateIn` rather than an optional
    `case_id` on it. The corridor path is keyed on (country_code, purpose); this one is
    keyed on a case and derives the corridor from what the case is actually served. Folding
    both into one model would make `country_code` conditionally-required and let a caller
    send a combination that means nothing.

    Carries NO case data beyond the id. Everything counsel sees is catalog content — see
    the whitelist in attestation_tokens.canonical_payload.
    """

    # Any of the three id forms a URL may carry (assignment id, case_id, canonical_case_id);
    # resolved through db.resolve_case_ids, which is the canonical boundary.
    case_id: str = Field(min_length=1, max_length=128)
    title: Optional[str] = None
    reviewer_org: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    reviewer_credential: Optional[str] = None
    ttl_days: Optional[int] = Field(default=None, ge=1, le=90)


class AttestationAdminDTO(BaseModel):
    """Admin-side view. Carries reviewer contact details, which the public view must not."""

    id: str
    country_code: str
    purpose: str
    scope: str
    title: Optional[str] = None
    status: str
    requested_by: str
    reviewer_org: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    reviewer_credential: Optional[str] = None
    content_snapshot_hash: str
    disclaimer_version: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    item_count: int = 0
    items: List[AttestationChecklistItemDTO] = Field(default_factory=list)
    signature: Optional[AttestationSignatureDTO] = None


class AttestationCreatedDTO(BaseModel):
    """Creation response — the ONLY time the raw token is ever returned."""

    request: AttestationAdminDTO
    review_token: str
    review_url: str
    token_expires_at: Optional[datetime] = None
    warning: str = (
        "This link is shown once and cannot be recovered. Only its SHA-256 hash is stored. "
        "Send it to the reviewer now; if it is lost, issue a new request."
    )


class AttestationPromoteResultDTO(BaseModel):
    request_id: str
    promoted_item_ids: List[str] = Field(default_factory=list)
    promoted_count: int = 0
    attested_by: Optional[str] = None
    skipped_not_approved: List[str] = Field(default_factory=list)

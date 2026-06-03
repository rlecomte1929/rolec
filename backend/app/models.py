import enum

from sqlalchemy import Column, String, DateTime, Text, Float, Date, Integer, Boolean, Numeric, ForeignKey
from sqlalchemy.sql import func
from .db import Base


class Case(Base):
    __tablename__ = "wizard_cases"

    id = Column(String, primary_key=True, index=True)
    draft_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    origin_country = Column(String, nullable=True)
    origin_city = Column(String, nullable=True)
    dest_country = Column(String, nullable=True)
    dest_city = Column(String, nullable=True)
    purpose = Column(String, nullable=True)
    target_move_date = Column(Date, nullable=True)
    flags_json = Column(Text, nullable=True)
    # Workflow status for wizard cases. Use canonical-style default to avoid
    # conflicting with assignment status enums elsewhere in the system.
    status = Column(String, nullable=False, default="created")
    requirements_snapshot_id = Column(String, nullable=True)


class CountryProfile(Base):
    __tablename__ = "country_profiles"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    last_updated_at = Column(DateTime, nullable=True)
    confidence_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)


class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    publisher_domain = Column(String, nullable=False)
    retrieved_at = Column(DateTime, nullable=False)
    snippet = Column(Text, nullable=True)
    content_hash = Column(String, nullable=False, unique=True)


class RequirementItem(Base):
    __tablename__ = "requirement_items"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    purpose = Column(String, nullable=False)
    pillar = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    required_fields_json = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=False)
    last_verified_at = Column(DateTime, nullable=False)


class ResearchSourceCandidate(Base):
    __tablename__ = "research_source_candidates"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    destination_country = Column(String, nullable=True)
    purpose = Column(String, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    publisher_domain = Column(String, nullable=False)
    retrieved_at = Column(DateTime, nullable=False)
    snippet = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")
    content_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class KnowledgeDocIngestJob(Base):
    __tablename__ = "knowledge_doc_ingest_jobs"

    id = Column(String, primary_key=True, index=True)
    candidate_id = Column(String, nullable=True)
    doc_id = Column(String, nullable=True)
    url = Column(String, nullable=False)
    destination_country = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class CaseRequirementsSnapshot(Base):
    __tablename__ = "case_requirements_snapshots"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, index=True)
    dest_country = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    snapshot_json = Column(Text, nullable=False)
    sources_json = Column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Supplier Registry (source of truth for recommendations + RFQ)
# ---------------------------------------------------------------------------

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    legal_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    languages_supported = Column(Text, nullable=True)  # JSON array as string
    verified = Column(Boolean, nullable=False, default=False)
    vendor_id = Column(String, nullable=True)  # FK to vendors.id for RFQ
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierServiceCapability(Base):
    __tablename__ = "supplier_service_capabilities"

    id = Column(String, primary_key=True, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    service_category = Column(String, nullable=False, index=True)
    coverage_scope_type = Column(String, nullable=False, default="country")
    country_code = Column(String, nullable=True, index=True)
    city_name = Column(String, nullable=True, index=True)
    specialization_tags = Column(Text, nullable=True)  # JSON array
    min_budget = Column(Numeric, nullable=True)
    max_budget = Column(Numeric, nullable=True)
    family_support = Column(Boolean, nullable=False, default=False)
    corporate_clients = Column(Boolean, nullable=False, default=False)
    remote_support = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierScoringMetadata(Base):
    __tablename__ = "supplier_scoring_metadata"

    supplier_id = Column(String, ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True)
    average_rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=False, default=0)
    response_sla_hours = Column(Integer, nullable=True)
    preferred_partner = Column(Boolean, nullable=False, default=False)
    premium_partner = Column(Boolean, nullable=False, default=False)
    last_verified_at = Column(DateTime, nullable=True)
    admin_score = Column(Float, nullable=True)  # 0-100 boost for ranking (admin-tunable)
    manual_priority = Column(Integer, nullable=True)  # relative priority (higher = rank higher)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AssignmentType(str, enum.Enum):
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    PERMANENT = "permanent"
    COMMUTER = "commuter"
    EXTENDED_BUSINESS_TRIP = "extended_business_trip"
    INTERNATIONAL = "international"


class Phase(str, enum.Enum):
    PRE_ASSIGNMENT = "pre_assignment"
    ON_ASSIGNMENT = "on_assignment"
    REPATRIATION = "repatriation"
    ONGOING = "ongoing"
    EXCEPTION = "exception"


class BenefitCategory(str, enum.Enum):
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


class ValueType(str, enum.Enum):
    MONETARY = "monetary"
    PERCENTAGE = "percentage"
    BOOLEAN = "boolean"
    DURATION = "duration"
    QUANTITY = "quantity"
    TEXT = "text"


class Frequency(str, enum.Enum):
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


class ProviderEntity(str, enum.Enum):
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


class PolicyDocumentCanonical(Base):
    __tablename__ = "canonical_policy_documents"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    source_policy_document_id = Column(String, nullable=True, index=True)
    source_type = Column(String, nullable=False, default="local_file")
    source_uri = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    title = Column(String, nullable=True)
    policy_scope = Column(String, nullable=True)
    document_type = Column(String, nullable=True)
    version_label = Column(String, nullable=True)
    effective_date = Column(Date, nullable=True)
    default_currency = Column(String, nullable=True)
    assignment_types_json = Column(Text, nullable=False, default="[]")
    raw_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    ingestion_status = Column(String, nullable=False, default="ingested")
    extraction_status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class PolicyDocumentChunkCanonical(Base):
    __tablename__ = "canonical_policy_document_chunks"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    canonical_policy_document_id = Column(
        String,
        ForeignKey("canonical_policy_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    section_path = Column(String, nullable=True)
    structure_type = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    text_content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PolicyFactCanonical(Base):
    __tablename__ = "canonical_policy_facts"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    canonical_policy_document_id = Column(
        String,
        ForeignKey("canonical_policy_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_policy_document_chunk_id = Column(
        String,
        ForeignKey("canonical_policy_document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_policy_document_id = Column(String, nullable=True, index=True)
    phase = Column(String, nullable=True, index=True)
    benefit_category = Column(String, nullable=True, index=True)
    value_type = Column(String, nullable=False, index=True)
    frequency = Column(String, nullable=True)
    provider_entity = Column(String, nullable=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    eligibility_json = Column(Text, nullable=False, default="{}")
    assignment_types_json = Column(Text, nullable=False, default="[]")
    amount = Column(Numeric, nullable=True)
    currency = Column(String, nullable=True)
    percentage = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    duration_value = Column(Integer, nullable=True)
    duration_unit = Column(String, nullable=True)
    value_text = Column(Text, nullable=True)
    is_taxable = Column(Boolean, nullable=True)
    reimbursement_required = Column(Boolean, nullable=True)
    source_quote = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    raw_payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PolicyFactCanonicalValidationError(Base):
    __tablename__ = "canonical_policy_fact_validation_errors"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    canonical_policy_document_id = Column(
        String,
        ForeignKey("canonical_policy_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_policy_document_chunk_id = Column(
        String,
        ForeignKey("canonical_policy_document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_payload_json = Column(Text, nullable=False, default="{}")
    errors_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ProspectCandidate(Base):
    """HR prospect pipeline staging row, enriched by the LLM agent.

    Lifecycle: pending_enrichment → enriched → approved | maybe | rejected.
    `raw_input_json` is what the admin provided (domain, name, notes);
    `enriched_json` is what the agent produced (company profile, signals,
    rationale). The top-level score / band / hook columns mirror the most
    useful fields of enriched_json for list-view filtering.
    """

    __tablename__ = "prospect_candidates"

    id = Column(String, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    company_domain = Column(String, nullable=True, index=True)
    company_linkedin_url = Column(String, nullable=True)
    raw_input_json = Column(Text, nullable=False, default="{}")
    enriched_json = Column(Text, nullable=False, default="{}")
    icp_score = Column(Integer, nullable=True, index=True)
    qualification_band = Column(String, nullable=True)
    suggested_contact_title = Column(String, nullable=True)
    suggested_hook = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending_enrichment", index=True)
    enrichment_error = Column(Text, nullable=True)
    web_search_used = Column(Boolean, nullable=False, default=False)
    batch_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    enriched_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, nullable=True)


class QueryAuditLog(Base):
    __tablename__ = "canonical_policy_query_audit_logs"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    user_role = Column(String, nullable=False, index=True)
    canonical_policy_document_id = Column(String, nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    redacted_query_text = Column(Text, nullable=False)
    retrieved_chunk_ids_json = Column(Text, nullable=False, default="[]")
    answer_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Specialist Review UI — P1-02a (AIQ-631)
# ---------------------------------------------------------------------------

class SpecialistReviewAction(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class SpecialistReviewEvent(Base):
    __tablename__ = "specialist_review_events"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, nullable=False, index=True)
    step_id = Column(String, nullable=False, index=True)
    reviewer_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    reason_code = Column(String, nullable=True)
    original_step_json = Column(Text, nullable=False, default="{}")
    edited_step_json = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, server_default=func.now(), nullable=False)


class RoadmapReviewStatus(Base):
    __tablename__ = "roadmap_review_status"

    case_id = Column(String, primary_key=True, index=True)
    released_to_user = Column(Boolean, nullable=False, default=False)
    regeneration_requested = Column(Boolean, nullable=False, default=False)
    reviewer_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class TranslationCache(Base):
    """Parker-I neural translation cache — dedup by sha256 of (text, src, tgt, domain).

    String id keeps the model portable to SQLite for tests (mirrors the rest of this
    module). The Postgres table + RLS live in the migration; this ORM mapping is what
    the service/repo and the test in-memory DB use.
    """
    __tablename__ = "translation_cache"

    id = Column(String, primary_key=True, index=True)
    source_hash = Column(String, nullable=False, unique=True, index=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_lang = Column(String, nullable=False)
    target_lang = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    provider = Column(String, nullable=False)
    model_version = Column(String, nullable=True)
    quality_score = Column(Numeric, nullable=True)
    cost_usd = Column(Numeric, nullable=True)
    translated_at = Column(DateTime, server_default=func.now(), nullable=False)

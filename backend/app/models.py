import enum

from sqlalchemy import Column, String, DateTime, Text, Float, Date, Integer, Boolean, Numeric, ForeignKey, JSON, UniqueConstraint, Uuid
from sqlalchemy.sql import func
from .db import Base

#: For columns that are genuinely `uuid` in Postgres.
#:
#: `Column(String)` against a real `uuid` column looks fine on SQLite and breaks on
#: Postgres. SQLAlchemy's insertmanyvalues path matches inserted rows back to their
#: parameter sets by primary key, and a Python `str` sent to a `uuid` column comes back
#: from the driver as a `UUID`, so the match fails:
#:
#:     InvalidRequestError: Can't match sentinel values in result set to parameter sets;
#:     key '3ccecc8d-…' was not found. There may be a mismatch between the datatype passed
#:     to the DBAPI driver vs. that which it returns in a result row.
#:
#: It only fires on a MULTI-row insert, so a single-row test passes and inserting two
#: children of one parent 500s — which is why the SQLite suite was green while the first
#: live Postgres call failed (see reference: mocked/SQLite tests miss PG constraints).
#:
#: `Uuid(as_uuid=False)` is the portable fix: native `uuid` on Postgres, CHAR on SQLite,
#: and plain `str` on the Python side so callers keep passing/comparing `str(uuid4())`.
#: Use this for any new column declared `uuid` in a migration.
_UUID = Uuid(as_uuid=False)


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


class CaseOutcome(Base):
    """AIQ-685 / P1-07b — anonymized flywheel outcome row (one per case).

    Mirrors supabase/migrations/20260620100000_case_outcomes.sql. PII-free by
    construction: the only link to the real case is ``case_ref_hash`` (SHA-256
    hex). The DB owns the CHECK constraints + PII-guard trigger + service-role
    RLS; this model intentionally declares columns only (no PG-specific regex
    CHECKs) so it stays portable for SQLite-backed unit tests.
    """

    __tablename__ = "case_outcomes"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    # SHA-256 hex of the real case id — one outcome row per case.
    case_ref_hash = Column(String, nullable=False, unique=True, index=True)
    pathway_type = Column(String, nullable=True)
    origin_country_code = Column(String, nullable=True)
    dest_country_code = Column(String, nullable=True)
    # APPROVED | REJECTED | WITHDRAWN | PENDING
    outcome = Column(String, nullable=False)
    processing_time_days_actual = Column(Integer, nullable=True)
    rejection_reason_code = Column(String, nullable=True)
    specialist_corrections_count = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime, nullable=True)
    decided_at = Column(DateTime, nullable=True)


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
    # Corridor-import idempotency (the 2026-08-15 FR→NO double-import incident): the
    # natural key the crud.create_requirement_item upsert matches on is enforced by the
    # DATABASE, not just by application code. Two racing imports both pre-select nothing
    # and would both insert; a writer that bypasses the funnel duplicates freely; and
    # once duplicates exist, .first() serves an arbitrary one of them. With this
    # constraint a duplicate import physically cannot insert a second row for the same
    # (country_code, purpose, title) — crud inserts with ON CONFLICT DO NOTHING pinned
    # to this key. Production Postgres gets the same index (after a dedupe) from
    # migration 20261118000000; SQLite test databases get it from this declaration.
    __table_args__ = (
        UniqueConstraint(
            "country_code",
            "purpose",
            "title",
            name="uq_requirement_items_country_purpose_title",
        ),
    )

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
    # AIQ-1349: optional JSON array of assignment types this requirement applies
    # to (e.g. ["LTA","PERMANENT"]). NULL ⇒ applies to all. Drives data-driven
    # STA/LTA requirement filtering without hardcoded title heuristics.
    applies_to_assignment_types_json = Column(Text, nullable=True)
    # Optional JSON array of nationality classes this requirement applies to
    # (["THIRD_COUNTRY"]). NULL ⇒ applies to all. Stops the non-EEA visa track
    # being served to an EU/EEA national. See services/nationality_class.py.
    applies_to_nationality_classes_json = Column(Text, nullable=True)
    # Optional JSON array of social-security regimes this requirement applies to
    # (["posted"]). NULL ⇒ applies to all. Fail-open, same contract as assignment type.
    applies_to_regimes_json = Column(Text, nullable=True)
    # AIQ-1349: provenance level (representative / corpus_grounded / expert_verified).
    # Describes how well-sourced the content is. It is a DISPLAY BADGE, not a gate — no read
    # path filters on it. Use review_status below to decide what is served.
    # Generator/verifier separation: 'expert_verified' is a human signature. Only
    # services/verification_guard.mark_expert_verified may write it (stamping verified_by +
    # verified_at below); crud.create_requirement_item — the funnel every automated producer
    # uses — refuses it outright and refuses to rewrite it once set.
    verification_status = Column(String, nullable=True)
    # The human behind verification_status='expert_verified'. Guard-owned: writable only via
    # verification_guard.mark_expert_verified; a generator payload carrying either column is
    # rejected. Mirrors reviewed_by/reviewed_at (publication) and attested_by/attested_at
    # (counsel) — three axes, each stamped with its own accountable actor.
    verified_by = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    # Admin publication gate: pending | approved | rejected. Only 'approved' is served, by
    # employees and by the public corridor endpoint alike. Set on insert, carried on update.
    review_status = Column(String, nullable=False, server_default="approved")
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    # A real obligation the person would not anticipate (emergency tax, skattekort,
    # police registration). A display/ranking hint — no read path gates on it.
    non_obvious = Column(Boolean, nullable=False, server_default="false", default=False)
    # Free-text deadline, verbatim from the source ("within 8 days of arrival"). Text and
    # not an interval on purpose: the rules are relative to events the engine doesn't model.
    timing = Column(Text, nullable=True)
    # Counsel-attestation axis, ORTHOGONAL to verification_status above. That one is the
    # founder/corpus ladder (representative → corpus_grounded → verified); this one is
    # external legal sign-off (NULL/none → requested → attested → stale). Sellable means
    # BOTH: verification_status='verified' AND attestation_status='attested'.
    #
    # Only the admin promote endpoint may ever write 'attested' — the tokenized public
    # reviewer path must never write to this table at all. That separation is the whole
    # point of the two-key design; see routers/attestation.py.
    attestation_status = Column(Text, nullable=True)
    attested_at = Column(DateTime(timezone=True), nullable=True)
    attested_by = Column(Text, nullable=True)
    latest_attestation_request_id = Column(_UUID, nullable=True)
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
    # Provenance (GAP 1): where this supplier record came from
    source = Column(String, nullable=False, default="admin_manual")
    source_url = Column(String, nullable=True)
    source_reference = Column(String, nullable=True)  # e.g. EuRA member ID, scrape batch
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
    # Platform vetting lifecycle (GAP 1)
    platform_vetting_status = Column(String, nullable=False, default="pending")
    vetted_by = Column(String, nullable=True)  # user id of the admin who decided
    vetted_at = Column(DateTime, nullable=True)
    vetting_notes = Column(Text, nullable=True)
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
    # Track B: link to the company this prospect was onboarded into (conversion path).
    onboarded_company_id = Column(String, nullable=True)
    onboarded_at = Column(DateTime, nullable=True)


class Lead(Base):
    """Person-level inbound lead (GTM-internal CRM). Fed by the public
    lead-capture endpoint (marketing-site demo forms) and manual entry.
    company_domain is an FK-by-value to prospect_candidates.company_domain
    so inbound leads can be matched against the outbound pipeline."""

    __tablename__ = "leads"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    company_domain = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False, default="marketing_site")
    status = Column(String, nullable=False, default="new", index=True)
    tags = Column(JSON, nullable=False, default=list)  # generic JSON (jsonb on PG, TEXT on SQLite)
    message = Column(Text, nullable=True)
    utm_source = Column(String, nullable=True)
    utm_campaign = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


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


class FeatureFlag(Base):
    """P2-01a — backend-native feature flag. String PK keeps the model portable
    to SQLite for tests (mirrors the rest of this module); the Postgres table +
    RLS live in the migration. Toggled DB-side, no redeploy required."""

    __tablename__ = "feature_flags"

    key = Column(String, primary_key=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class FeatureFlagAccount(Base):
    """P2-01a — per-account allowlist for a feature flag. A flag is active for an
    account only when the flag is enabled AND a row exists here ("selected test
    accounts initially")."""

    __tablename__ = "feature_flag_accounts"

    flag_key = Column(String, primary_key=True, index=True)
    account_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


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


# ─────────────────────────────────────────────────────────────────────────────
# Counsel attestation (Phase 1). Tables created by
# supabase/migrations/20261104000000_counsel_attestation_phase1.sql.
#
# `JSON` and not postgresql.JSONB deliberately: the columns ARE jsonb in Postgres,
# but the backend test fixture is SQLite and the generic type round-trips on both.
# ─────────────────────────────────────────────────────────────────────────────
class CorridorAttestationRequest(Base):
    """One corridor attestation ask — the envelope sent to external counsel."""

    __tablename__ = "corridor_attestation_requests"
    # implicit_returning=False: with a server_default on created_at, SQLAlchemy uses
    # RETURNING for a multi-row INSERT and then matches result rows back to parameter sets
    # by a "sentinel" — which fails on Postgres when the PK is a client-generated uuid
    # ("Can't match sentinel values in result set to parameter sets"). We generate every id
    # ourselves and never need a value echoed back at insert time, so turning RETURNING off
    # removes the whole mechanism. SQLite never hit this, which is why the suite was green.
    __table_args__ = {"implicit_returning": False}

    id = Column(_UUID, primary_key=True, index=True)
    country_code = Column(String, nullable=False, index=True)
    purpose = Column(String, nullable=False, server_default="employment")
    scope = Column(Text, nullable=False, server_default="legal")
    # Set when scope='case': the ONE case this attestation covers. NULL for corridor-scoped
    # requests, which is every row today. Deliberately has no ForeignKey — the canonical
    # case-id boundary is resolved in the application (db.resolve_case_ids) across three
    # case tables; see migration 20261121000000. `_UUID`, not String: the column is `uuid`
    # in Postgres, and wizard_cases.id is varchar, so the router validates the shape at the
    # boundary rather than letting a non-uuid id raise a DataError out of the endpoint.
    case_id = Column(_UUID, nullable=True, index=True)
    title = Column(Text, nullable=True)
    # draft | sent | in_review | changes_requested | signed | revoked | superseded
    status = Column(Text, nullable=False, server_default="draft")
    requested_by = Column(Text, nullable=False)
    reviewer_org = Column(Text, nullable=True)
    reviewer_name = Column(Text, nullable=True)
    reviewer_email = Column(Text, nullable=True)
    reviewer_credential = Column(Text, nullable=True)
    # SHA-256 of the raw token. The raw token is shown to the admin once and never stored,
    # so a dump of this table does not yield working reviewer links.
    link_token_hash = Column(Text, nullable=True, index=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    content_snapshot_hash = Column(Text, nullable=False)
    content_snapshot_json = Column(JSON, nullable=False)
    disclaimer_version = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # How this attestation reaches requirement_items, and whether promoting it may also
    # advance review_status. Both default to today's behaviour, so an omitted field is the
    # conservative choice rather than a surprise. The vocabulary of `promotion_policy` is
    # enforced by a CHECK constraint in the database (ck_cap_promotion_policy), NOT here —
    # see migration 20261120000000. `auto_on_sign` is honoured in ATT-2.4; as of ATT-2.2
    # these are recorded intent and nothing acts on them.
    promotion_policy = Column(Text, nullable=False, server_default="manual")
    advance_review_status = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CorridorAttestationItem(Base):
    """One requirement inside an envelope, carrying the reviewer's decision.

    The `*_snapshot` columns duplicate the catalog row on purpose: counsel signs what they
    were SHOWN, so the evidence has to survive the requirement_items row being edited later.
    """

    __tablename__ = "corridor_attestation_items"
    # implicit_returning=False: with a server_default on created_at, SQLAlchemy uses
    # RETURNING for a multi-row INSERT and then matches result rows back to parameter sets
    # by a "sentinel" — which fails on Postgres when the PK is a client-generated uuid
    # ("Can't match sentinel values in result set to parameter sets"). We generate every id
    # ourselves and never need a value echoed back at insert time, so turning RETURNING off
    # removes the whole mechanism. SQLite never hit this, which is why the suite was green.
    __table_args__ = {"implicit_returning": False}

    id = Column(_UUID, primary_key=True, index=True)
    request_id = Column(_UUID, ForeignKey("corridor_attestation_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    # String, not a uuid type — requirement_items.id is `character varying` in Postgres.
    # A uuid FK against it fails with 42804 (incompatible types); see the migration header.
    requirement_item_id = Column(String, ForeignKey("requirement_items.id"), nullable=False, index=True)
    item_title = Column(Text, nullable=False)
    claim_snapshot = Column(Text, nullable=True)
    source_url_snapshot = Column(Text, nullable=True)
    evidence_snapshot = Column(Text, nullable=True)
    # pending | approved | amended | rejected
    decision = Column(Text, nullable=False, server_default="pending")
    reviewer_comment = Column(Text, nullable=True)
    proposed_amendment = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CorridorAttestationSignature(Base):
    """Append-only proof of sign-off. INSERT ONLY.

    Never UPDATE or DELETE a row of this table. Revocation or re-issue is a NEW row
    pointing at the prior one through `supersedes_signature_id` — the chain is the audit
    trail, and a signature you can edit is not evidence of anything.
    """

    __tablename__ = "corridor_attestation_signatures"
    # implicit_returning=False: with a server_default on created_at, SQLAlchemy uses
    # RETURNING for a multi-row INSERT and then matches result rows back to parameter sets
    # by a "sentinel" — which fails on Postgres when the PK is a client-generated uuid
    # ("Can't match sentinel values in result set to parameter sets"). We generate every id
    # ourselves and never need a value echoed back at insert time, so turning RETURNING off
    # removes the whole mechanism. SQLite never hit this, which is why the suite was green.
    __table_args__ = {"implicit_returning": False}

    id = Column(_UUID, primary_key=True, index=True)
    request_id = Column(_UUID, ForeignKey("corridor_attestation_requests.id"), nullable=False, index=True)
    signer_name = Column(Text, nullable=False)
    signer_email = Column(Text, nullable=False)
    signer_org = Column(Text, nullable=True)
    signer_credential = Column(Text, nullable=True)
    # typed_name | uploaded_pdf | esign (future — eIDAS upgrade path, no rewrite needed)
    signature_method = Column(Text, nullable=False, server_default="typed_name")
    # Must equal the request's content_snapshot_hash at signing time, or the signature
    # attests to a checklist the reviewer never saw.
    signed_content_hash = Column(Text, nullable=False)
    signed_payload_json = Column(JSON, nullable=False)
    disclaimer_version = Column(Text, nullable=False)
    disclaimer_text = Column(Text, nullable=False)
    signed_ip = Column(Text, nullable=True)
    signed_user_agent = Column(Text, nullable=True)
    supersedes_signature_id = Column(_UUID, ForeignKey("corridor_attestation_signatures.id"), nullable=True)
    signed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

/**
 * relopass-api-contracts.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Canonical TypeScript contracts for the ReloPass platform redesign.
 * Source of truth for all API shapes, entity interfaces, and shared UI types.
 *
 * Design intent
 * ─────────────
 * Every relocation case is visible, compliant, and on-time.
 * The employee should feel zero friction — the system answers before they ask.
 * HR is the support function and facilitator, not the bottleneck.
 *
 * Usage
 * ─────
 * - Import entities in React components for prop typing
 * - Import API types in fetch helpers / React Query hooks
 * - Import enums everywhere — no magic strings
 *
 * Organisation
 * ────────────
 * 1.  Primitive enums
 * 2.  Core domain entities (maps 1:1 to Supabase tables)
 * 3.  Derived / view types (joins, aggregates)
 * 4.  API request shapes
 * 5.  API response envelopes
 * 6.  Route-specific payload types
 * 7.  AI panel types
 * 8.  UI / navigation types
 * 9.  Real-time / event types
 * 10. Error types
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─────────────────────────────────────────────────────────────────────────────
// 1. PRIMITIVE ENUMS
// ─────────────────────────────────────────────────────────────────────────────

/** Plan tier controls what features the company/user can access.
 *  - basic   : employee self-service (default for assignees)
 *  - hr      : HR operator (case management, vendor coordination)
 *  - admin   : org admin (policy management, billing, analytics)
 */
export type PlanTier = "basic" | "hr" | "admin";

/** Role stored in profiles.role — aligned with auth.my_role() RLS helper */
export type UserRole = "employee" | "hr" | "admin" | "vendor_contact";

/** Top-level lifecycle of a relocation case */
export type CaseStatus =
  | "draft"          // intake wizard in progress
  | "active"         // case open and progressing
  | "on_hold"        // paused by HR (pending info, policy exception, etc.)
  | "completed"      // case closed, audit trail frozen
  | "cancelled";     // case abandoned

/** Granular stage within the active lifecycle — drives roadmap progress */
export type CaseStage =
  | "intake"          // employee completing onboarding wizard
  | "compliance"      // immigration / compliance checks running
  | "housing"         // housing search in progress
  | "logistics"       // move co-ordination
  | "settling_in"     // on-ground orientation phase
  | "close_out";      // final steps and audit close

/** Individual roadmap step status */
export type StepStatus =
  | "pending"
  | "in_progress"
  | "awaiting_employee"
  | "awaiting_vendor"
  | "awaiting_hr"
  | "blocked"
  | "skipped"
  | "completed";

/** Document lifecycle */
export type DocStatus =
  | "required"         // known requirement, not yet submitted
  | "submitted"        // employee uploaded, not yet reviewed
  | "under_review"     // HR or vendor reviewing
  | "approved"         // accepted
  | "rejected"         // requires re-submission
  | "expired"          // e.g. visa/passport expiry
  | "waived";          // requirement formally waived

/** Smart form status */
export type FormStatus =
  | "not_started"
  | "in_progress"
  | "submitted"
  | "reviewed";

/** Policy exception approval state */
export type ExceptionStatus = "pending" | "approved" | "denied";

/** Benefit value type — governs how benefit_value is rendered */
export type BenefitValueType = "currency" | "days" | "boolean" | "text";

/** Thread context — where does this message thread live */
export type ThreadContext =
  | "case"          // discussion on a specific case
  | "requirement"   // about a document/requirement
  | "step"          // about a roadmap step
  | "vendor"        // vendor co-ordination thread
  | "support";      // HR support ticket

/** AI model identifiers (as used in AIPanelContext) */
export type AIModelId =
  | "claude-haiku-4-5-20251001"  // fast: used for suggestions, search answers
  | "claude-sonnet-4-6";          // deep: used for document analysis, drafts

/** Message sender role within a thread */
export type ThreadParticipantRole = "employee" | "hr" | "vendor" | "system";

/** Corridor string format: "{origin_iso2}-{dest_iso2}" e.g. "FR-DE" */
export type CorridorCode = string;

// ─────────────────────────────────────────────────────────────────────────────
// 2. CORE DOMAIN ENTITIES  (1:1 with Supabase tables)
// ─────────────────────────────────────────────────────────────────────────────

// ── 2.1 Multi-tenancy ────────────────────────────────────────────────────────

export interface Company {
  id: string;                        // uuid
  name: string;
  slug: string;                      // used in subdomain routing
  logo_url: string | null;
  plan_tier: PlanTier;
  settings: CompanySettings;
  created_at: string;                // ISO-8601
  updated_at: string;
}

export interface CompanySettings {
  default_currency: string;          // ISO-4217 e.g. "EUR"
  fiscal_year_start: number;         // 1–12 (month)
  ai_enabled: boolean;
  globe_canvas_enabled: boolean;
  theme_override: "light" | "dark" | null;  // null = user-controlled
}

export interface Profile {
  id: string;                        // uuid, matches auth.users.id
  company_id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: UserRole;
  plan_tier: PlanTier;
  locale: string;                    // BCP-47 e.g. "en-GB"
  phone: string | null;
  onboarding_complete: boolean;
  created_at: string;
  updated_at: string;
}

// ── 2.2 Reference data ───────────────────────────────────────────────────────

export interface Country {
  iso2: string;                      // 2-letter ISO e.g. "FR"
  iso3: string;                      // 3-letter ISO e.g. "FRA"
  name: string;
  flag_emoji: string;
  visa_complexity: 1 | 2 | 3 | 4 | 5;  // 1 = easy, 5 = hardest
  processing_weeks_min: number;
  processing_weeks_max: number;
  key_authorities: string[];         // ["Direction Générale des Étrangers en France"]
  popular_corridors: string[];       // ["FR-DE", "FR-GB", "FR-US"]
  created_at: string;
}

export interface DiscoverySource {
  id: string;
  name: string;                      // "LinkedIn", "Google", "Colleague referral"
  category: "social" | "search" | "referral" | "event" | "other";
}

export interface PolicyTier {
  id: string;                       // uuid
  company_id: string;
  name: string;                     // "Senior Executive", "Standard", "Entry Level"
  description: string | null;
  rank: number;                     // lower = more generous
  max_budget_eur: number | null;
  lump_sum_eur: number | null;
  temp_housing_days: number;
  created_at: string;
  updated_at: string;
}

// ── 2.3 Cases (core entity) ──────────────────────────────────────────────────

export interface RelocationCase {
  id: string;                        // uuid
  company_id: string;
  employee_id: string;               // profiles.id
  hr_owner_id: string | null;        // profiles.id of assigned HR
  policy_tier_id: string | null;
  origin_country_code: string;       // ISO-2
  dest_country_code: string;         // ISO-2
  corridor: CorridorCode;            // GENERATED ALWAYS AS STORED
  status: CaseStatus;
  stage: CaseStage;
  target_start_date: string | null;  // ISO date "YYYY-MM-DD"
  actual_start_date: string | null;
  target_close_date: string | null;
  actual_close_date: string | null;
  intake_data: IntakeData | null;    // wizard answers
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * IntakeData — structured output of the employee onboarding wizard.
 * Stored as JSONB in cases.intake_data.
 * All downstream forms, requirements, and AI suggestions are seeded from this.
 */
export interface IntakeData {
  // Step 1 — Family configuration
  family_config: {
    marital_status: "single" | "married" | "civil_partnership" | "other";
    partner_relocating: boolean;
    partner_employment_status: "employed" | "self_employed" | "unemployed" | "student" | null;
    children: ChildConfig[];
  };

  // Step 2 — Housing preferences
  housing_prefs: {
    preferred_type: "apartment" | "house" | "any";
    min_bedrooms: number;
    max_monthly_budget_eur: number | null;
    preferred_neighbourhoods: string[];  // free text tags
    pet_owner: boolean;
    accessibility_needs: boolean;
    accessibility_detail: string | null;
  };

  // Step 3 — Temporary housing
  temp_housing: {
    needed: boolean;
    duration_weeks: number | null;
    preferred_location: string | null;  // near office, near school, etc.
    serviced_apartment_ok: boolean;
  };

  // Step 4 — Immigration situation
  immigration: {
    current_visa_type: string | null;
    current_visa_expiry: string | null;  // ISO date
    has_work_permit_dest: boolean;
    needs_visa_dest: boolean | null;     // null = unknown, wizard prompts
    passport_nationalities: string[];    // ISO-2 list
    dual_citizen: boolean;
  };

  // Step 5 — Move logistics
  logistics: {
    volume_cbm_estimate: number | null;
    has_vehicle: boolean;
    vehicles_to_ship: number;
    special_items: ("piano" | "art" | "wine" | "pets" | "fragile")[];
    preferred_move_window: {
      earliest: string | null;  // ISO date
      latest: string | null;
    };
  };

  // Step 6 — Financial / tax
  financial: {
    needs_tax_advice: boolean;
    has_property_to_sell: boolean;
    has_rental_income: boolean;
    banking_needs_assistance: boolean;
    home_sale_assistance_needed: boolean;
  };

  // Step 7 — Schooling
  schooling: {
    children_school_age: boolean;
    school_type_preference: ("public" | "private" | "international" | "no_preference")[];
    language_of_instruction: string[];  // BCP-47
  };

  // Step 8 — Language & cultural
  language: {
    dest_language_proficiency: "none" | "basic" | "intermediate" | "fluent";
    wants_language_lessons: boolean;
    wants_cultural_training: boolean;
  };

  // Metadata
  wizard_version: string;             // semver of wizard schema
  completed_at: string | null;        // ISO datetime
}

export interface ChildConfig {
  age: number;
  school_needed: boolean;
  special_educational_needs: boolean;
}

export interface CaseDependent {
  id: string;
  case_id: string;
  full_name: string;
  relationship: "partner" | "child" | "parent" | "other";
  date_of_birth: string | null;
  passport_nationality: string | null;
  visa_required: boolean | null;
  notes: string | null;
  created_at: string;
}

// ── 2.4 Roadmap ──────────────────────────────────────────────────────────────

export interface RoadmapTrack {
  id: string;
  case_id: string;
  name: string;                       // "Immigration", "Housing", "Move Logistics"
  icon: string;                       // lucide-react icon name
  sort_order: number;
  is_mandatory: boolean;
  progress_pct: number;               // 0–100, computed by edge function
  created_at: string;
  updated_at: string;
}

export interface RoadmapStep {
  id: string;
  track_id: string;
  case_id: string;                    // denormalised for RLS
  title: string;
  description: string | null;
  status: StepStatus;
  owner: "employee" | "hr" | "vendor" | "system";
  vendor_id: string | null;
  due_date: string | null;
  // [AIQ-1258c/d] True when due_date is auto-estimated from the case move date
  // (move_date − track lead time) rather than a real deadline.
  due_date_is_suggested?: boolean;
  completed_at: string | null;
  sort_order: number;
  dependency_ids: string[];           // IDs of steps that must complete first
  ai_suggestion: string | null;       // last AI-generated guidance text
  created_at: string;
  updated_at: string;
  // [P3-04] Confidence display — optional source-provenance metadata. Absent
  // until the backend emits per-step confidence; UI renders nothing when unset.
  confidence_level?: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  source_url?: string | null;          // official source backing this step
  source_fetched_at?: string | null;   // ISO date the source was last verified
  source_excerpt?: string | null;      // one-sentence excerpt from the source
  estimated_effort?: string | null;    // [AIQ-869] short effort label, null when done
}

// ── 2.5 Requirements & Documents ─────────────────────────────────────────────

export interface Requirement {
  id: string;
  case_id: string;
  step_id: string | null;
  name: string;                       // "Work Permit Application Form"
  description: string | null;
  category: RequirementCategory;
  status: DocStatus;
  is_mandatory: boolean;
  template_url: string | null;        // link to blank template
  instructions: string | null;        // plain-language instructions for employee
  country_specific: boolean;
  corridor_specific: boolean;
  due_date: string | null;
  completed_at: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export type RequirementCategory =
  | "immigration"
  | "employment"
  | "housing"
  | "financial"
  | "tax"
  | "schooling"
  | "medical"
  | "vehicle"
  | "other";

export interface RequirementDep {
  id: string;
  requirement_id: string;
  depends_on_id: string;
}

export interface Document {
  id: string;
  case_id: string;
  requirement_id: string | null;
  step_id: string | null;
  uploader_id: string;               // profiles.id
  file_name: string;
  file_url: string;                  // Supabase Storage signed URL
  file_size_bytes: number;
  mime_type: string;
  status: DocStatus;
  ocr_data: OcrData | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  expires_at: string | null;         // for passports, visas, permits
  created_at: string;
  updated_at: string;
}

/**
 * OcrData — extracted by the OCR pipeline, feeds form auto-fill.
 * Design intent: "Ask Once, Use Everywhere" — the employee uploads a passport
 * once; every form that needs passport data pre-fills from this.
 */
export interface OcrData {
  doc_type: "passport" | "id_card" | "visa" | "permit" | "contract" | "lease" | "other";
  extracted_fields: Record<string, string>;  // field_key → raw extracted value
  confidence: Record<string, number>;        // field_key → 0.0–1.0
  processed_at: string;
  model_version: string;
}

// ── 2.6 Smart Forms ──────────────────────────────────────────────────────────

export interface Form {
  id: string;
  case_id: string;
  requirement_id: string | null;
  form_type: FormType;
  status: FormStatus;
  fields_data: Record<string, FormFieldValue>;  // field_key → value
  auto_filled_fields: string[];                 // keys auto-filled from OCR
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewer_id: string | null;
  created_at: string;
  updated_at: string;
}

export type FormType =
  | "personal_info"
  | "family_declaration"
  | "housing_request"
  | "tax_declaration_intent"
  | "school_application"
  | "bank_account_opening"
  | "vendor_briefing"
  | "custom";

export type FormFieldValue = string | number | boolean | string[] | null;

// ── 2.7 Policy ───────────────────────────────────────────────────────────────

export interface PolicyBenefit {
  id: string;
  policy_tier_id: string;
  name: string;                       // "Temporary Housing Allowance"
  description: string | null;
  value_type: BenefitValueType;
  benefit_value: string;              // stored as text, cast on read
  currency: string | null;
  category: string;                   // "housing", "transport", "school"
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PolicyException {
  id: string;
  case_id: string;
  policy_tier_id: string | null;
  requested_by: string;              // profiles.id
  approved_by: string | null;
  benefit_name: string;
  requested_value: string;
  approved_value: string | null;
  status: ExceptionStatus;
  justification: string;
  decision_notes: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

// ── 2.8 Vendors ──────────────────────────────────────────────────────────────

export type VendorServiceType =
  | "immigration_legal"
  | "moving"
  | "housing"
  | "tax"
  | "schooling"
  | "banking"
  | "language_training"
  | "cultural_training"
  | "medical"
  | "other";

export interface Vendor {
  id: string;
  name: string;
  service_type: VendorServiceType;
  website_url: string | null;
  logo_url: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  coverage_countries: string[];      // ISO-2 list, [] = global
  description: string | null;
  rating: number | null;             // 1.0–5.0
  is_global: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompanyVendor {
  id: string;
  company_id: string;
  vendor_id: string;
  is_preferred: boolean;
  internal_notes: string | null;
  contract_url: string | null;
  created_at: string;
}

// ── 2.9 Messaging ────────────────────────────────────────────────────────────

export interface Thread {
  id: string;
  company_id: string;
  case_id: string | null;
  context: ThreadContext;
  context_entity_id: string | null;  // step_id, requirement_id, etc.
  subject: string | null;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ThreadParticipant {
  id: string;
  thread_id: string;
  profile_id: string;
  role: ThreadParticipantRole;
  joined_at: string;
  last_read_at: string | null;
}

export interface Message {
  id: string;
  thread_id: string;
  sender_id: string;
  body: string;
  is_system_message: boolean;
  attachments?: MessageAttachment[];  // included when fetching thread detail
  created_at: string;
  updated_at: string;
}

export interface MessageAttachment {
  id: string;
  message_id: string;
  document_id: string | null;
  file_name: string;
  file_url: string;
  file_size_bytes: number;
  mime_type: string;
  created_at: string;
}

// ── 2.10 Discovery ───────────────────────────────────────────────────────────

export interface CaseDiscoveryRun {
  id: string;
  case_id: string;
  corridor: CorridorCode;
  triggered_by: string;             // profiles.id
  status: "pending" | "running" | "complete" | "failed";
  result: DiscoveryResult | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface DiscoveryResult {
  visa_options: VisaOption[];
  estimated_timeline_weeks: number;
  key_risks: string[];
  recommended_actions: string[];
  corridor_complexity_score: number;  // 1–10
  data_sources: string[];
  generated_at: string;
}

export interface VisaOption {
  name: string;
  category: string;
  eligibility_summary: string;
  processing_weeks_min: number;
  processing_weeks_max: number;
  requires_employer_sponsorship: boolean;
  key_conditions: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. DERIVED / VIEW TYPES  (joins, aggregates — used in list/detail responses)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * CaseSummaryRow — used in S2 Case Management table.
 * One row in the HR dashboard case list.
 * Design intent: HR should be able to scan the full state of all cases
 * at a glance without opening individual case pages.
 */
export interface CaseSummaryRow {
  id: string;
  employee_name: string;
  employee_avatar_url: string | null;
  hr_owner_name: string | null;
  origin_country: Pick<Country, "iso2" | "name" | "flag_emoji">;
  dest_country: Pick<Country, "iso2" | "name" | "flag_emoji">;
  corridor: CorridorCode;
  status: CaseStatus;
  stage: CaseStage;
  policy_tier_name: string | null;
  target_start_date: string | null;
  target_close_date: string | null;
  overall_progress_pct: number;       // 0–100
  blocked_steps_count: number;
  overdue_requirements_count: number;
  unread_messages_count: number;
  has_pending_exceptions: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * CaseDetail — full case for S3 Case Detail view.
 * Includes all related entities fetched in a single API call.
 */
export interface CaseDetail extends RelocationCase {
  employee: Profile;
  hr_owner: Profile | null;
  policy_tier: PolicyTier | null;
  policy_benefits: PolicyBenefit[];
  origin_country: Country;
  dest_country: Country;
  dependents: CaseDependent[];
  roadmap_tracks: (RoadmapTrack & { steps: RoadmapStep[] })[];
  requirements: Requirement[];
  documents: Document[];
  forms: Form[];
  active_vendors: (Vendor & { is_preferred: boolean })[];
  pending_exceptions: PolicyException[];
  thread_summary: ThreadSummary[];
}

export interface ThreadSummary {
  id: string;
  context: ThreadContext;
  subject: string | null;
  last_message_preview: string;
  last_message_at: string;
  unread_count: number;
  participant_count: number;
  is_resolved: boolean;
}

/**
 * EmployeeDashboardData — drives S5 (Employee My Move) and S6 (My Journey).
 * Design intent: employee sees their relocation as a guided journey,
 * not an administrative task list.
 */
export interface EmployeeDashboardData {
  case: Pick<RelocationCase, "id" | "status" | "stage" | "target_start_date" | "corridor">;
  overall_progress_pct: number;
  days_until_move: number | null;
  next_action: NextAction | null;
  active_tracks: TrackProgress[];
  overdue_items: OverdueItem[];
  recently_completed: RecentActivity[];
  ai_suggestion_of_day: string | null;
}

export interface NextAction {
  type: "step" | "requirement" | "form";
  entity_id: string;
  title: string;
  description: string;
  urgency: "low" | "medium" | "high" | "critical";
  due_date: string | null;
  deep_link: string;               // relative URL e.g. "/my-move/requirements/abc"
}

export interface TrackProgress {
  track_id: string;
  name: string;
  icon: string;
  progress_pct: number;
  next_step_title: string | null;
  has_blocked_items: boolean;
}

export interface OverdueItem {
  type: "step" | "requirement" | "form";
  entity_id: string;
  title: string;
  overdue_by_days: number;
  track_name: string;
}

export interface RecentActivity {
  type: "step_completed" | "document_approved" | "form_submitted" | "message_received";
  title: string;
  completed_at: string;
}

/**
 * VendorBriefRow — used in S8 Vendor Directory
 */
export interface VendorBriefRow extends Vendor {
  case_assignments: number;           // how many active cases use this vendor
  is_preferred_by_company: boolean;
  average_case_duration_days: number | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. API REQUEST SHAPES
// ─────────────────────────────────────────────────────────────────────────────

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface SignInRequest {
  email: string;
  password: string;
}

export interface SignUpRequest {
  email: string;
  password: string;
  full_name: string;
  company_slug?: string;             // join existing company
  invite_token?: string;
}

export interface ResetPasswordRequest {
  email: string;
}

// ── Case management ───────────────────────────────────────────────────────────

export interface CreateCaseRequest {
  employee_id: string;
  origin_country_code: string;
  dest_country_code: string;
  target_start_date?: string;
  policy_tier_id?: string;
  hr_owner_id?: string;
}

export interface UpdateCaseRequest {
  hr_owner_id?: string | null;
  policy_tier_id?: string | null;
  status?: CaseStatus;
  stage?: CaseStage;
  target_start_date?: string | null;
  target_close_date?: string | null;
  notes?: string | null;
}

export interface SubmitIntakeRequest {
  case_id: string;
  intake_data: IntakeData;
}

export interface ListCasesRequest {
  status?: CaseStatus | CaseStatus[];
  stage?: CaseStage | CaseStage[];
  hr_owner_id?: string;
  corridor?: CorridorCode;
  has_blocked?: boolean;
  search?: string;                   // employee name or case id prefix
  sort_by?: "created_at" | "updated_at" | "target_start_date" | "progress_pct";
  sort_dir?: "asc" | "desc";
  page?: number;
  per_page?: number;
}

// ── Roadmap ──────────────────────────────────────────────────────────────────

export interface UpdateStepRequest {
  status?: StepStatus;
  due_date?: string | null;
  vendor_id?: string | null;
  sort_order?: number;
}

export interface ReorderStepsRequest {
  track_id: string;
  ordered_step_ids: string[];
}

// ── Requirements & Documents ─────────────────────────────────────────────────

export interface CreateRequirementRequest {
  case_id: string;
  step_id?: string;
  name: string;
  category: RequirementCategory;
  description?: string;
  is_mandatory?: boolean;
  due_date?: string;
  instructions?: string;
}

export interface UpdateRequirementStatusRequest {
  requirement_id: string;
  status: DocStatus;
  rejection_reason?: string;
}

export interface UploadDocumentRequest {
  case_id: string;
  requirement_id?: string;
  step_id?: string;
  file: File;                        // browser File object
  run_ocr?: boolean;                 // default true
}

export interface ReviewDocumentRequest {
  document_id: string;
  action: "approve" | "reject";
  rejection_reason?: string;
}

// ── Forms ─────────────────────────────────────────────────────────────────────

export interface SaveFormDraftRequest {
  form_id: string;
  fields_data: Record<string, FormFieldValue>;
}

export interface SubmitFormRequest {
  form_id: string;
  fields_data: Record<string, FormFieldValue>;
}

// ── Policy ────────────────────────────────────────────────────────────────────

export interface RequestExceptionRequest {
  case_id: string;
  policy_tier_id?: string;
  benefit_name: string;
  requested_value: string;
  justification: string;
}

export interface DecideExceptionRequest {
  exception_id: string;
  action: "approve" | "deny";
  approved_value?: string;
  decision_notes?: string;
}

// ── Messaging ─────────────────────────────────────────────────────────────────

export interface CreateThreadRequest {
  case_id: string;
  context: ThreadContext;
  context_entity_id?: string;
  subject?: string;
  initial_message: string;
  participant_ids: string[];
}

export interface SendMessageRequest {
  thread_id: string;
  body: string;
  attachment_document_ids?: string[];
}

export interface MarkThreadReadRequest {
  thread_id: string;
}

// ── Vendors ───────────────────────────────────────────────────────────────────

export interface AssignVendorRequest {
  case_id: string;
  step_id: string;
  vendor_id: string;
  notes?: string;
}

export interface ListVendorsRequest {
  service_type?: VendorServiceType;
  corridor?: CorridorCode;
  preferred_only?: boolean;
  search?: string;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface AnalyticsPeriod {
  start: string;  // ISO date
  end: string;
}

export interface CaseAnalyticsRequest {
  period: AnalyticsPeriod;
  group_by?: "corridor" | "policy_tier" | "stage" | "hr_owner" | "month";
  filter_corridor?: CorridorCode;
  filter_policy_tier_id?: string;
}

// ── AI Panel ──────────────────────────────────────────────────────────────────

export interface AIPanelMessageRequest {
  case_id?: string;
  route: string;                     // current browser route e.g. "/cases/abc/roadmap"
  messages: AIPanelMessageInput[];
  model?: AIModelId;
  context_entities?: AIPanelContextEntity[];
}

export interface AIPanelMessageInput {
  role: "user" | "assistant";
  content: string;
}

export interface AIPanelContextEntity {
  type: "case" | "step" | "requirement" | "document" | "vendor";
  id: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. API RESPONSE ENVELOPES
// ─────────────────────────────────────────────────────────────────────────────

/** Standard success envelope for all non-paginated responses */
export interface ApiResponse<T> {
  data: T;
  meta?: ResponseMeta;
}

/** Standard success envelope for paginated list responses */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
  meta?: ResponseMeta;
}

export interface Pagination {
  page: number;
  per_page: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface ResponseMeta {
  request_id: string;
  duration_ms: number;
}

/** Standard error envelope */
export interface ApiError {
  error: {
    code: ApiErrorCode;
    message: string;                 // human-readable (UI-safe)
    detail?: string;                 // technical detail (dev mode only)
    field?: string;                  // for validation errors
  };
}

export type ApiErrorCode =
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "VALIDATION_ERROR"
  | "CONFLICT"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR"
  | "INTAKE_INCOMPLETE"             // action requires completed intake
  | "CASE_LOCKED"                   // case is completed/cancelled
  | "POLICY_VIOLATION"
  | "OCR_FAILED"
  | "AI_UNAVAILABLE";

// ─────────────────────────────────────────────────────────────────────────────
// 6. ROUTE-SPECIFIC PAYLOAD TYPES
// ─────────────────────────────────────────────────────────────────────────────

// ── GET /cases → list ─────────────────────────────────────────────────────────

export type ListCasesResponse = PaginatedResponse<CaseSummaryRow>;

// ── GET /cases/:id → detail ───────────────────────────────────────────────────

export type GetCaseResponse = ApiResponse<CaseDetail>;

// ── POST /cases → create ─────────────────────────────────────────────────────

export type CreateCaseResponse = ApiResponse<RelocationCase>;

// ── PATCH /cases/:id ─────────────────────────────────────────────────────────

export type UpdateCaseResponse = ApiResponse<RelocationCase>;

// ── POST /cases/:id/intake ───────────────────────────────────────────────────

export interface IntakeSubmitResponse {
  case: RelocationCase;
  generated_requirements: Requirement[];
  generated_roadmap_tracks: RoadmapTrack[];
  generated_forms: Form[];
}

// ── GET /cases/:id/roadmap ───────────────────────────────────────────────────

export interface RoadmapResponse {
  tracks: (RoadmapTrack & { steps: RoadmapStep[] })[];
  overall_progress_pct: number;
  blocked_count: number;
  overdue_count: number;
}

// ── GET /cases/:id/documents ─────────────────────────────────────────────────

export interface DocumentsResponse {
  documents: Document[];
  requirements: Requirement[];
  completion_pct: number;
  pending_review_count: number;
}

// ── POST /documents/:id/ocr ──────────────────────────────────────────────────

export interface OcrResultResponse {
  document_id: string;
  ocr_data: OcrData;
  forms_updated: string[];           // form_ids that were auto-filled
  fields_filled_count: number;
}

// ── GET /cases/:id/employee-dashboard ────────────────────────────────────────

export type EmployeeDashboardResponse = ApiResponse<EmployeeDashboardData>;

// ── GET /analytics/cases ─────────────────────────────────────────────────────

export interface CaseAnalyticsResponse {
  period: AnalyticsPeriod;
  summary: CaseAnalyticsSummary;
  by_group: CaseAnalyticsGroup[];
  timeline: CaseAnalyticsTimelinePoint[];
}

export interface CaseAnalyticsSummary {
  total_cases: number;
  active_cases: number;
  completed_cases: number;
  avg_duration_days: number;
  on_time_pct: number;
  compliance_completion_pct: number;
  top_corridors: { corridor: CorridorCode; count: number }[];
}

export interface CaseAnalyticsGroup {
  group_key: string;
  group_label: string;
  count: number;
  avg_duration_days: number;
  on_time_pct: number;
}

export interface CaseAnalyticsTimelinePoint {
  date: string;                      // ISO date (start of period)
  opened: number;
  completed: number;
  active: number;
}

// ── POST /ai/chat ────────────────────────────────────────────────────────────

export interface AIChatResponse {
  message_id: string;
  content: string;
  model: AIModelId;
  suggested_actions?: AISuggestedAction[];
  context_entities_used: string[];   // ids of entities the AI referenced
  tokens_used: number;
}

export interface AISuggestedAction {
  label: string;
  action_type: "navigate" | "update_step" | "create_thread" | "request_exception";
  action_payload: Record<string, unknown>;
}

// SSE stream chunk for streaming AI responses
export interface AIChatStreamChunk {
  type: "delta" | "done" | "error";
  delta?: string;
  final_message?: AIChatResponse;
  error?: string;
}

// ── GET /globe-data ──────────────────────────────────────────────────────────

export interface GlobeDataResponse {
  corridors: GlobeCorridorArc[];
  total_active_cases: number;
  active_countries: string[];        // ISO-2 list
}

export interface GlobeCorridorArc {
  corridor: CorridorCode;
  origin_iso2: string;
  dest_iso2: string;
  origin_lat: number;
  origin_lon: number;
  dest_lat: number;
  dest_lon: number;
  case_count: number;
  arc_color: "teal" | "blue" | "amber";  // maps to design token globe_canvas_colors
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. AI PANEL TYPES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * AIPanelContext — constructed by AIPanelContextBuilder on each route change.
 * The system prompt is derived from design-tokens.json route_ai_context strings,
 * augmented with live case data if a case is in scope.
 */
export interface AIPanelContext {
  route: string;
  route_label: string;               // human-readable route name
  system_prompt: string;             // built by context builder
  active_case_id: string | null;
  suggested_prompts: string[];       // pre-seeded questions for the current view
  capabilities: AIPanelCapability[];
}

export type AIPanelCapability =
  | "answer_questions"
  | "summarise_case"
  | "suggest_next_step"
  | "draft_message"
  | "explain_requirement"
  | "check_policy"
  | "generate_checklist"
  | "translate";

export interface AIPanelMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  is_streaming: boolean;
  suggested_actions?: AISuggestedAction[];
  error?: string;
}

export interface AIPanelState {
  is_open: boolean;
  is_loading: boolean;
  context: AIPanelContext | null;
  messages: AIPanelMessage[];
  session_id: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. UI / NAVIGATION TYPES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * NavItem — single item in the sidebar.
 * Source of truth is design-tokens.json > nav_items.
 * Visibility controlled by plan_tier and user_role.
 */
export interface NavItem {
  id: string;
  label: string;
  icon: string;                      // lucide-react icon name
  route: string;
  badge?: NavBadge;
  visible_to: PlanTier[];
  role_required?: UserRole[];
  is_external?: boolean;
  children?: NavItem[];
}

export interface NavBadge {
  type: "count" | "dot" | "status";
  value?: number;
  color?: "teal" | "amber" | "red" | "gray";
}

export interface NavSection {
  id: string;
  label: string | null;              // null = unlabelled section
  items: NavItem[];
  collapsible?: boolean;
}

/**
 * SidebarState — persisted in localStorage key "rp-sidebar"
 */
export interface SidebarState {
  is_collapsed: boolean;
  collapsed_sections: string[];      // section ids
}

/**
 * ThemePreference — persisted in localStorage key "rp-theme"
 */
export type ThemePreference = "light" | "dark" | "system";

/**
 * ToastMessage — used by the global toast system
 */
export interface ToastMessage {
  id: string;
  type: "success" | "error" | "warning" | "info";
  title: string;
  body?: string;
  duration_ms?: number;             // default 4000
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * MovableColumnsConfig — persisted in localStorage key "rp-columns-{table_id}"
 * Used by the MovableColumns system for table column reordering.
 */
export interface MovableColumnsConfig {
  table_id: string;
  columns: ColumnConfig[];
}

export interface ColumnConfig {
  key: string;
  label: string;
  width_px?: number;
  is_visible: boolean;
  sort_order: number;
  is_sortable?: boolean;
  is_filterable?: boolean;
}

/**
 * FilterState — URL-serialisable filter state for list views
 */
export interface FilterState {
  search: string;
  status: string[];
  stage: string[];
  corridor: string[];
  hr_owner_id: string[];
  policy_tier_id: string[];
  has_blocked: boolean | null;
  sort_by: string;
  sort_dir: "asc" | "desc";
}

/**
 * PillVariant — maps to design-token pill_variants
 */
export type PillVariant =
  | "success"
  | "warning"
  | "danger"
  | "accent"
  | "neutral"
  | "ghost";

/**
 * Breadcrumb — for TopBar breadcrumb trail
 */
export interface Breadcrumb {
  label: string;
  route?: string;                    // undefined = current (non-clickable)
}

// ─────────────────────────────────────────────────────────────────────────────
// 9. REAL-TIME / EVENT TYPES  (Supabase Realtime channel payloads)
// ─────────────────────────────────────────────────────────────────────────────

export type RealtimeEventType =
  | "case_status_changed"
  | "step_status_changed"
  | "document_uploaded"
  | "document_reviewed"
  | "message_sent"
  | "exception_decided"
  | "roadmap_progress_updated"
  | "vendor_assigned";

export interface RealtimeEvent<T = unknown> {
  type: RealtimeEventType;
  company_id: string;
  case_id: string | null;
  payload: T;
  triggered_by: string;             // profiles.id
  timestamp: string;
}

export interface CaseStatusChangedPayload {
  old_status: CaseStatus;
  new_status: CaseStatus;
  old_stage: CaseStage;
  new_stage: CaseStage;
}

export interface StepStatusChangedPayload {
  step_id: string;
  track_id: string;
  old_status: StepStatus;
  new_status: StepStatus;
  new_progress_pct: number;
}

export interface DocumentReviewedPayload {
  document_id: string;
  requirement_id: string | null;
  action: "approved" | "rejected";
  rejection_reason: string | null;
}

export interface MessageSentPayload {
  thread_id: string;
  message_id: string;
  sender_name: string;
  preview: string;
  thread_context: ThreadContext;
}

// ─────────────────────────────────────────────────────────────────────────────
// 10. ERROR TYPES
// ─────────────────────────────────────────────────────────────────────────────

export class ReloPassApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    message: string,
    public readonly status: number,
    public readonly field?: string
  ) {
    super(message);
    this.name = "ReloPassApiError";
  }
}

export class IntakeIncompleteError extends ReloPassApiError {
  constructor(public readonly case_id: string) {
    super(
      "INTAKE_INCOMPLETE",
      "Complete the intake wizard before accessing this feature.",
      422
    );
  }
}

export class PolicyViolationError extends ReloPassApiError {
  constructor(
    message: string,
    public readonly benefit_name: string,
    public readonly requested_value: string,
    public readonly allowed_value: string
  ) {
    super("POLICY_VIOLATION", message, 422);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 11. UTILITY / HELPER TYPES
// ─────────────────────────────────────────────────────────────────────────────

/** Makes selected keys of T optional */
export type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

/** Makes selected keys of T required */
export type RequiredBy<T, K extends keyof T> = T & Required<Pick<T, K>>;

/** Deep readonly */
export type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};

/** Supabase row type helpers */
export type InsertRow<T> = Omit<T, "id" | "created_at" | "updated_at">;
export type UpdateRow<T> = Partial<Omit<T, "id" | "created_at" | "updated_at" | "company_id">>;

// ─────────────────────────────────────────────────────────────────────────────
// 12. STATUS → DISPLAY MAPS  (co-located so components stay thin)
// ─────────────────────────────────────────────────────────────────────────────

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  draft: "Draft",
  active: "Active",
  on_hold: "On Hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const CASE_STATUS_PILL: Record<CaseStatus, PillVariant> = {
  draft: "neutral",
  active: "accent",
  on_hold: "warning",
  completed: "success",
  cancelled: "ghost",
};

export const CASE_STAGE_LABELS: Record<CaseStage, string> = {
  intake: "Intake",
  compliance: "Compliance",
  housing: "Housing Search",
  logistics: "Move Logistics",
  settling_in: "Settling In",
  close_out: "Close Out",
};

export const STEP_STATUS_LABELS: Record<StepStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  awaiting_employee: "Awaiting Employee",
  awaiting_vendor: "Awaiting Vendor",
  awaiting_hr: "Awaiting HR",
  blocked: "Blocked",
  skipped: "Skipped",
  completed: "Completed",
};

export const STEP_STATUS_PILL: Record<StepStatus, PillVariant> = {
  pending: "neutral",
  in_progress: "accent",
  awaiting_employee: "warning",
  awaiting_vendor: "warning",
  awaiting_hr: "warning",
  blocked: "danger",
  skipped: "ghost",
  completed: "success",
};

export const DOC_STATUS_LABELS: Record<DocStatus, string> = {
  required: "Required",
  submitted: "Submitted",
  under_review: "Under Review",
  approved: "Approved",
  rejected: "Rejected",
  expired: "Expired",
  waived: "Waived",
};

export const DOC_STATUS_PILL: Record<DocStatus, PillVariant> = {
  required: "neutral",
  submitted: "accent",
  under_review: "warning",
  approved: "success",
  rejected: "danger",
  expired: "danger",
  waived: "ghost",
};

export const VENDOR_SERVICE_LABELS: Record<VendorServiceType, string> = {
  immigration_legal: "Immigration Legal",
  moving: "Moving",
  housing: "Housing",
  tax: "Tax Advisory",
  schooling: "Schooling",
  banking: "Banking",
  language_training: "Language Training",
  cultural_training: "Cultural Training",
  medical: "Medical",
  other: "Other",
};

export const REQUIREMENT_CATEGORY_LABELS: Record<RequirementCategory, string> = {
  immigration: "Immigration",
  employment: "Employment",
  housing: "Housing",
  financial: "Financial",
  tax: "Tax",
  schooling: "Schooling",
  medical: "Medical",
  vehicle: "Vehicle",
  other: "Other",
};

// ─────────────────────────────────────────────────────────────────────────────
// 13. ROUTE CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * ROUTES — single source of truth for all app routes.
 * Use these in Link/navigate calls, never raw strings.
 */
export const ROUTES = {
  // Public
  SIGN_IN: "/sign-in",
  SIGN_UP: "/sign-up",
  RESET_PASSWORD: "/reset-password",

  // HR / Admin
  DASHBOARD: "/dashboard",
  CASES: "/cases",
  CASE_DETAIL: (id: string) => `/cases/${id}`,
  CASE_ROADMAP: (id: string) => `/cases/${id}/roadmap`,
  CASE_DOCUMENTS: (id: string) => `/cases/${id}/documents`,
  CASE_FORMS: (id: string) => `/cases/${id}/forms`,
  CASE_POLICY: (id: string) => `/cases/${id}/policy`,
  CASE_MESSAGES: (id: string) => `/cases/${id}/messages`,
  CASE_INTAKE: (id: string) => `/cases/${id}/intake`,
  VENDORS: "/vendors",
  VENDOR_DETAIL: (id: string) => `/vendors/${id}`,
  ANALYTICS: "/analytics",
  POLICY_SETTINGS: "/settings/policy",
  TEAM_SETTINGS: "/settings/team",
  ORG_SETTINGS: "/settings/organisation",

  // Employee
  MY_MOVE: "/my-move",
  MY_JOURNEY: "/my-move/journey",
  MY_DOCUMENTS: "/my-move/documents",
  MY_FORMS: "/my-move/forms",
  MY_MESSAGES: "/my-move/messages",

  // Shared
  PROFILE: "/profile",
  NOTIFICATIONS: "/notifications",
  HELP: "/help",
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// End of relopass-api-contracts.ts
// ─────────────────────────────────────────────────────────────────────────────

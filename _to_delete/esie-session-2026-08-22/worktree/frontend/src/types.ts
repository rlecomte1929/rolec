// TypeScript types matching backend schemas

export interface Question {
  id: string;
  title: string;
  whyThisMatters: string;
  type: string;
  options?: QuestionOption[];
  required: boolean;
  mapsTo: string;
  dependsOn?: unknown;
  validation?: unknown;
  allowUnknown: boolean;
}

export interface QuestionOption {
  value: string;
  label: string;
  icon?: string;
}

export interface NextQuestionResponse {
  question: Question | null;
  isComplete: boolean;
  progress: {
    answeredCount: number;
    totalQuestions: number;
    percentComplete: number;
  };
}

export interface LoginRequest {
  identifier: string;
  password: string;
}

/** Populated after EMPLOYEE register/login when pending cases were linked */
export interface PostSignupReconciliation {
  linkedContactIds: string[];
  attachedAssignmentIds: string[];
  skippedContactsLinkedToOtherUser?: number;
  skippedAssignmentsLinkedToOtherUser?: number;
  skippedRevokedInvites?: number;
  skippedAlreadyLinkedSameUser?: number;
  headline?: string | null;
  message?: string | null;
}

export interface LoginResponse {
  token: string;
  user: User;
  reconciliation?: PostSignupReconciliation | null;
}

export interface RegisterRequest {
  username?: string;
  email?: string;
  password: string;
  role: UserRole;
  name?: string;
  company_name?: string;
  /** HR signup only — headcount band, persisted to companies.size_band (AIQ-829). */
  company_size?: string;
}

export type UserRole = 'HR' | 'EMPLOYEE' | 'ADMIN';

export interface Company {
  id?: string;
  name: string;
  legal_name?: string | null;
  website?: string | null;
  country?: string | null;
  hq_city?: string | null;
  industry?: string | null;
  logo_url?: string | null;
  brand_color?: string | null;
  size_band?: string | null;
  address?: string | null;
  phone?: string | null;
  hr_contact?: string | null;
  default_destination_country?: string | null;
  support_email?: string | null;
  default_working_location?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CompanyProfilePayload {
  name: string;
  country?: string;
  size_band?: string;
  address?: string;
  phone?: string;
  hr_contact?: string;
  legal_name?: string;
  website?: string;
  hq_city?: string;
  industry?: string;
  default_destination_country?: string;
  support_email?: string;
  default_working_location?: string;
}

/** AIQ-1223c — deterministic HR-onboarding inference response. */
export interface InferredOnboardingConfig {
  company_id: string | null;
  signals: {
    size_band: string | null;
    size_bucket: 'small' | 'medium' | 'large' | 'unknown';
    default_destination_country: string | null;
    default_working_location: string | null;
    published_tier_count: number;
    has_published_policy: boolean;
    case_count: number;
    has_active_program: boolean;
  };
  proposed_config: {
    policy_tiers: string[];
    tier_source: 'published' | 'size_band_guess';
    default_destination_country: string | null;
    default_working_location: string | null;
    dashboard_density: 'compact' | 'standard' | 'active_program';
    bulk_assign_enabled: boolean;
    show_volume_nudges: boolean;
  };
  confidence: 'low' | 'medium' | 'high';
}

export interface DossierQuestion {
  id: string;
  question_text: string;
  answer_type: 'text' | 'boolean' | 'select' | 'date' | 'multiselect';
  options?: string[] | null;
  is_mandatory: boolean;
  domain: string;
  question_key?: string | null;
  source: 'library' | 'case';
}

export interface DossierQuestionsResponse {
  destination_country?: string | null;
  questions: DossierQuestion[];
  answers: Record<string, unknown>;
  mandatory_unanswered_count: number;
  is_step5_complete: boolean;
  sources_used: Array<{ title?: string; url: string; snippet?: string }>;
}

// A single citation backing a dossier suggestion. The RAG path (P3-02) returns
// corpus chunks as `{ chunk_id, url }` (url may be absent when the chunk has no
// source_url); the legacy web-search path returned `{ title, url, snippet }`.
// `url` is therefore optional and `chunk_id` carries the corpus attribution.
export interface DossierSource {
  chunk_id?: string;
  title?: string;
  url?: string;
  snippet?: string;
}

export interface DossierSuggestion {
  question_text: string;
  answer_type: 'text' | 'boolean' | 'select' | 'date' | 'multiselect';
  sources: DossierSource[];
}

export interface DossierSearchSuggestionsResponse {
  destination_country?: string | null;
  sources: DossierSource[];
  suggestions: DossierSuggestion[];
  // [OBS-01] true when the suggestion LLM call failed (provider/transport outage),
  // distinct from a genuinely empty result for an uncovered corridor.
  degraded?: boolean;
}

export interface User {
  id: string;
  username?: string;
  email?: string;
  role: UserRole;
  // AIQ-1361/1363 multi-role: all roles the user holds + the active/primary role.
  // Optional so legacy callers/tests are unaffected.
  roles?: string[];
  primary_role?: string | null;
  name?: string;
  company?: string;
  // AIQ-1701: has this user already dismissed their role's first-login welcome page?
  // Server-owned (profiles.welcome_seen_at) and mirrored into localStorage at login,
  // which keeps the welcome redirect check synchronous. Optional so legacy
  // callers/tests are unaffected.
  welcome_seen?: boolean | null;
}

export interface AnswerRequest {
  questionId: string;
  answer: unknown;
  isUnknown?: boolean;
}

export interface Child {
  firstName?: string;
  dateOfBirth?: string;
  currentGrade?: string;
  languageNeeds?: string;
}

export interface Spouse {
  fullName?: string;
  nationality?: string;
  wantsToWork: boolean;
  occupation?: string;
  educationLevel?: string;
}

export interface Passport {
  number?: string;
  expiryDate?: string;
  issuingCountry?: string;
}

export interface Employer {
  name: string;
  roleTitle?: string;
  jobLevel?: string;
  contractType?: string;
  salaryBand?: string;
}

export interface Assignment {
  startDate?: string;
  expectedDurationMonths?: number;
  relocationPackage?: boolean;
  relocationPackageNotes?: string;
}

export interface PrimaryApplicant {
  fullName?: string;
  nationality?: string;
  dateOfBirth?: string;
  photoUrl?: string;
  passport: Passport;
  employer: Employer;
  assignment: Assignment;
}

export interface HousingPreferences {
  desiredMoveInDate?: string;
  temporaryStayWeeks?: number;
  budgetMonthlySGD?: string;
  bedroomsMin: number;
  preferredAreas: string[];
  mustHave: string[];
}

export interface SchoolingPreferences {
  schoolingStartDate?: string;
  curriculumPreference?: string;
  budgetAnnualSGD?: string;
  priorities: string[];
}

export interface MoversPreferences {
  inventoryRough?: string;
  specialItems: string[];
  storageNeeded?: boolean;
  insuranceNeeded?: boolean;
}

export interface MovePlan {
  origin: string;
  destination: string;
  targetArrivalDate?: string;
  shippingDatePreference?: string;
  housing: HousingPreferences;
  schooling: SchoolingPreferences;
  movers: MoversPreferences;
}

export interface ComplianceDocs {
  hasPassportScans?: boolean;
  hasMarriageCertificate?: boolean;
  hasBirthCertificates?: boolean;
  hasEmploymentLetter?: boolean;
  hasBankStatements?: boolean;
  notes?: string;
}

export type PolicyExceptionStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export interface PolicyException {
  id: string;
  assignment_id: string;
  category: string;
  status: PolicyExceptionStatus;
  reason?: string;
  requested_amount?: number;
  requested_by: string;
  created_at: string;
  updated_at: string;
}

export interface PolicyCap {
  amount: number;
  currency: string;
  durationMonths?: number;
}

export interface PolicyConfig {
  policyVersion: string;
  effectiveDate: string;
  jurisdictionNotes: string;
  caps: Record<string, PolicyCap>;
  approvalRules: Record<string, string>;
  exceptionWorkflow: {
    states: string[];
    requiredFields: string[];
  };
  requiredEvidence: Record<string, string[]>;
  leadTimeRules: { minDays: number };
  riskThresholds: { low: number; moderate: number };
  documentRequirements: Record<string, string[]>;
}

export type PolicySpendStatus = 'ON_TRACK' | 'NEAR_LIMIT' | 'OVER_LIMIT';

export interface PolicySpendItem {
  title: string;
  used: number;
  cap: number;
  remaining: number;
  currency: string;
  status: PolicySpendStatus;
}

export interface PolicyResponse {
  policy: PolicyConfig;
  spend: Record<string, PolicySpendItem>;
  exceptions: PolicyException[];
  gating: {
    requiresAcknowledgement: boolean;
    requiresHRApproval: boolean;
  };
}

export type ComplianceStatus = 'PASS' | 'WARN' | 'FAIL';
export type ComplianceSeverity = 'LOW' | 'MED' | 'HIGH' | 'CRITICAL';
export type ComplianceConfidence = 'LOW' | 'MED' | 'HIGH';
export type ComplianceOwner = 'HR' | 'Employee' | 'Partner';

export interface ComplianceCheckItem {
  checkId: string;
  title: string;
  pillar: string;
  status: ComplianceStatus;
  severity: ComplianceSeverity;
  confidence: ComplianceConfidence;
  owner: ComplianceOwner;
  whyItMatters: string;
  evidenceNeeded: string[];
  fixActions: string[];
  blocking: boolean;
}

export interface ComplianceSummary {
  riskScore: number;
  label: 'Low' | 'Moderate' | 'High';
  criticalCount: number;
  lastVerified: string;
}

export interface ComplianceMeta {
  visaPath: string;
  destination: string;
  stage: string;
}

export interface ComplianceConflict {
  id: string;
  title: string;
  details: Record<string, string>;
}

export interface ComplianceCaseReport {
  summary: ComplianceSummary;
  meta: ComplianceMeta;
  checks: ComplianceCheckItem[];
  consistencyConflicts: ComplianceConflict[];
  recentChecks: ComplianceCheckItem[];
}

export interface RelocationBasicsDTO {
  originCountry?: string;
  originCity?: string;
  destCountry?: string;
  destCity?: string;
  purpose?: string;
  targetMoveDate?: string;
  durationMonths?: number;
  hasDependents?: boolean;
}

export interface EmployeeProfileDTO {
  fullName?: string;
  nationality?: string;
  passportCountry?: string;
  passportExpiry?: string;
  residenceCountry?: string;
  email?: string;
  ocr?: Record<string, unknown>;
}

export interface FamilyMemberDTO {
  fullName?: string;
  dateOfBirth?: string;
  relationship?: string;
  nationality?: string;
  wantsToWork?: boolean;
}

export interface FamilyMembersDTO {
  maritalStatus?: string;
  spouse?: FamilyMemberDTO;
  children?: FamilyMemberDTO[];
}

export interface AssignmentContextDTO {
  employerName?: string;
  employerCountry?: string;
  workLocation?: string;
  contractStartDate?: string;
  contractType?: string;
  salaryBand?: string;
  jobTitle?: string;
  seniorityBand?: string;
  /** AIQ-1349: STA / LTA / PERMANENT — drives duration-aware policy + roadmap. */
  assignmentType?: string;
  /** AIQ-1349: expected assignment length in months. */
  expectedDurationMonths?: number;
  /** AIQ-1603: single-select commute preference (car/public_transport/bike/walk/no_preference). */
  commutePreference?: string;
}

export interface CaseDraftDTO {
  relocationBasics: RelocationBasicsDTO;
  employeeProfile: EmployeeProfileDTO;
  familyMembers: FamilyMembersDTO;
  assignmentContext: AssignmentContextDTO;
  /** Employee wizard Step 2 — selected relocation services (e.g. ['housing', 'immigration']). */
  services?: string[];
}

export interface CaseDTO {
  id: string;
  status: string;
  draft: CaseDraftDTO;
  createdAt: string;
  updatedAt: string;
  originCountry?: string;
  originCity?: string;
  destCountry?: string;
  destCity?: string;
  purpose?: string;
  targetMoveDate?: string;
  flags?: Record<string, unknown>;
  requirementsSnapshotId?: string;
}

export interface SourceRecordDTO {
  id: string;
  url: string;
  title: string;
  publisherDomain: string;
  /**
   * Absent for a citation the backend holds as a bare URL or an inline object — only a
   * `source_records` row records a retrieval time. Drives StalenessBadge, which renders
   * nothing without it rather than claiming a freshness we cannot evidence.
   */
  retrievedAt?: string | null;
  snippet?: string;
}

export interface RequirementItemDTO {
  id: string;
  pillar: string;
  title: string;
  description: string;
  severity: string;
  owner: string;
  requiredFields: string[];
  /** CONFIRMED is the status of a `nothing_to_do` item — a positive answer, not a pending task. */
  statusForCase: 'PROVIDED' | 'MISSING' | 'NEEDS_REVIEW' | 'CONFIRMED';
  citations: SourceRecordDTO[];
  /** AIQ-1349: provenance level. */
  // `verified` is what production actually stores (10 approved rows); `expert_verified` is
  // what the backend constants and every doc comment say. Both are accepted until the two
  // are normalised — see the PROVENANCE map in RequirementList.tsx.
  verificationStatus?: 'representative' | 'corpus_grounded' | 'expert_verified' | 'verified' | null;
  // Counsel attestation. A SEPARATE axis from verificationStatus, not a further rung on it:
  // ours is provenance, this is external legal sign-off. null = no counsel has looked.
  attestationStatus?: 'requested' | 'attested' | 'stale' | null;
  attestedBy?: string | null;
  attestedAt?: string | null;
  /**
   * 'action' (something is required of someone) or 'nothing_to_do' (a STATED
   * confirmation that nothing is required — e.g. "No visa or residence permit
   * required"). A correct answer of "none" must be said out loud, never implied
   * by an empty list, because an empty pillar reads as a broken screen.
   */
  outcomeType?: 'action' | 'nothing_to_do';
  /** Why nothing is required. The only human-readable payload of a nothing_to_do item. */
  reason?: string | null;
  /**
   * A real obligation the person would not anticipate (the skattekort needed before
   * first pay, police registration). Optional rather than `boolean`: an item the rules
   * engine synthesised has no catalog row behind it, and null ("not modeled") is a
   * different claim from false ("modeled, and it is obvious").
   */
  nonObvious?: boolean | null;
  /** Free-text deadline verbatim from the source ("within 3 months of arrival"). */
  timing?: string | null;
}

export interface CountryProfileDTO {
  countryCode: string;
  lastUpdatedAt?: string;
  confidenceScore?: number;
  sources: SourceRecordDTO[];
  requirementGroups: { pillar: string; items: RequirementItemDTO[] }[];
}

export interface CountryListDTO {
  countries: {
    countryCode: string;
    lastUpdatedAt?: string;
    requirementsCount: number;
    confidenceScore?: number;
    topDomains: string[];
  }[];
}

export interface CaseRequirementsDTO {
  caseId: string;
  destCountry: string;
  purpose: string;
  computedAt: string;
  requirements: RequirementItemDTO[];
  sources: SourceRecordDTO[];
  staWaived?: string[];
  /**
   * Requirement titles waived because the employee's nationality exempts them
   * (an EU/EEA national needs none of the non-EEA visa track).
   *
   * NOT symmetric — read `nationalityClass` before rendering it. For a
   * THIRD_COUNTRY national this array holds the *EU* items, so showing it
   * verbatim would say "Justificatif de domicile doesn't apply to you", which is
   * confusing and false. Their list didn't shrink; those items were never theirs.
   */
  nationalityWaived?: string[];
  nationalityClass?: 'OWN_NATIONAL' | 'EU_EEA' | 'THIRD_COUNTRY' | null;
  // AIQ-1473c/d: false when the destination isn't in our requirements catalogue —
  // the empty list then means "no catalogue yet", not "nothing required".
  // Undefined from older backends → treat as covered (no notice).
  covered?: boolean;
}

export interface RelocationCaseListItem {
  id: string;
  status?: string | null;
  stage?: string | null;
  home_country?: string | null;
  host_country?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  employee_id?: string | null;
  hr_user_id?: string | null;
  company_id?: string | null;
}

export interface RelocationCase {
  id: string;
  status?: string | null;
  stage?: string | null;
  home_country?: string | null;
  host_country?: string | null;
  profile: Record<string, unknown>;
  missing_fields: string[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RelocationRun {
  id: string;
  created_at: string;
  run_type: string;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  error?: string | null;
  model_provider?: string | null;
  model_name?: string | null;
}

export type NextActionPriority = 'high' | 'medium' | 'low';

export interface NextAction {
  key: string;
  label: string;
  priority: NextActionPriority;
}

export interface CaseClassification {
  case_type: 'employee_sponsored' | 'remote_worker' | 'student' | 'self_employed' | 'unknown';
  risk_flags: string[];
  blockers: string[];
  next_actions: NextAction[];
}

export interface RelocationProfile {
  userId?: string;
  familySize: number;
  maritalStatus?: string;
  dependents: Child[];
  spouse: Spouse;
  primaryApplicant: PrimaryApplicant;
  movePlan: MovePlan;
  complianceDocs: ComplianceDocs;
}

export interface ImmigrationReadiness {
  score: number;
  status: 'GREEN' | 'AMBER' | 'RED';
  reasons: string[];
  missingDocs: string[];
}

export interface HousingRecommendation {
  id: string;
  name: string;
  area: string;
  bedrooms: number;
  furnished: boolean;
  nearMRT: boolean;
  estMonthlySGDMin: number;
  estMonthlySGDMax: number;
  familyFriendlyScore: number;
  notes: string;
  rationale: string;
  nextAction: string;
}

export interface SchoolRecommendation {
  id: string;
  name: string;
  area: string;
  curriculumTags: string[];
  ageRange: string;
  estAnnualSGDMin: number;
  estAnnualSGDMax: number;
  languageSupport: string[];
  notes: string;
  rationale: string;
  nextAction: string;
}

export interface MoverRecommendation {
  id: string;
  name: string;
  serviceTags: string[];
  notes: string;
  rfqTemplate: string;
  rationale: string;
  nextAction: string;
}

export interface TimelineTask {
  title: string;
  status: string;
  dueDate?: string;
}

export interface TimelinePhase {
  phase: string;
  tasks: TimelineTask[];
}

export interface DashboardResponse {
  profileCompleteness: number;
  immigrationReadiness: ImmigrationReadiness;
  nextActions: string[];
  timeline: TimelinePhase[];
  recommendations: {
    housing?: HousingRecommendation[];
    schools?: SchoolRecommendation[];
    movers?: MoverRecommendation[];
  };
  overallStatus: 'On track' | 'At risk';
}

// Canonical assignment statuses (aligned with Postgres constraint and backend).
export type AssignmentStatus =
  | 'created'
  | 'assigned'
  | 'awaiting_intake'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'closed';

export interface AssignmentSummary {
  id: string;
  caseId: string;
  employeeIdentifier: string;
  status: AssignmentStatus;
  submittedAt?: string;
  complianceStatus?: string | null;
  employeeFirstName?: string | null;
  employeeLastName?: string | null;
  /** Relocation case metadata (host_country, home_country) for list display */
  case?: { host_country?: string; home_country?: string; id?: string; status?: string } | null;
  /** Earliest open milestone due date (from HR assignments list API). */
  nextDeadline?: string | null;
}

export interface AssignmentsListResponse {
  assignments: AssignmentSummary[];
  total: number;
}

export interface IntakeChecklistItemDTO {
  key: string;
  label: string;
  satisfied: boolean;
  category: string;
  /** case_milestone.milestone_type: scroll target in relocation plan */
  linked_tracker_task_type?: string | null;
}

export interface ReadinessBlockingItemDTO {
  source: string;
  title: string;
  detail?: string | null;
  human_review_required?: boolean;
  provenance_note?: string | null;
  linked_tracker_task_type?: string | null;
}

export interface ReadinessNextActionDTO {
  title: string;
  category: string;
  linked_tracker_task_type?: string | null;
}

export interface CaseReadinessUiDTO {
  overall_status: string;
  overall_label: string;
  completion_basis: string;
  intake_satisfied: number;
  intake_total: number;
  checklist_satisfied?: number | null;
  checklist_total?: number | null;
  checklist_applicable?: boolean;
  checklist_pending?: number | null;
  blocking_items: ReadinessBlockingItemDTO[];
  next_actions: ReadinessNextActionDTO[];
  trust_banner?: string | null;
  next_deadline_display?: string | null;
}

export interface AssignmentDetail {
  id: string;
  caseId: string;
  employeeIdentifier: string;
  status: AssignmentStatus;
  submittedAt?: string;
  hrNotes?: string | null;
  profile?: RelocationProfile | null;
  completeness?: number | null;
  complianceReport?: ComplianceReport | null;
  employeeFirstName?: string | null;
  employeeLastName?: string | null;
  /** profiles.email for linked employee_user_id (same GET as assignment detail) */
  employeeEmail?: string | null;
  /** [AIQ-1648] The HR account that owns the case (case_assignments.hr_user_id → users.email) */
  hrOwnerEmail?: string | null;
  /** profiles.full_name when intake name not yet on RelocationProfile */
  linkedEmployeeFullName?: string | null;
  /** relocation_cases / draft relocationBasics: fallback when movePlan empty */
  caseOriginHint?: string | null;
  caseDestinationHint?: string | null;
  /** [AIQ-1336] City-level corridor so the case detail shows "Paris, France" not "France" */
  caseOriginCity?: string | null;
  caseDestinationCity?: string | null;
  /** Explicit intake + document checkpoints (merged readiness block) */
  intakeChecklist?: IntakeChecklistItemDTO[];
  readinessSnapshot?: Record<string, unknown> | null;
  caseReadinessUi?: CaseReadinessUiDTO | null;
}

export interface ComplianceActionItem {
  title: string;
  output_category?: string;
  human_review_required?: boolean;
}

export interface ComplianceReport {
  overallStatus: 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW';
  checks: ComplianceCheck[];
  actions: (string | ComplianceActionItem)[];
  /** Legal safety banner from API */
  disclaimer_legal?: string;
  verdict_explanation?: string;
  outcome_verdict?: string;
  meta?: Record<string, unknown>;
  explanation?: {
    steps: Array<{
      step: number;
      title: string;
      detail: unknown;
    }>;
  };
}

export interface ComplianceCheck {
  id: string;
  name: string;
  status: 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW';
  severity: 'low' | 'medium' | 'high';
  rationale: string;
  affectedFields: string[];
  /** internal_operational_rule | … */
  output_category?: string;
  check_type?: string;
  reference_strength?: string;
  human_review_required?: boolean;
  primary_reference?: Record<string, unknown>;
  rationale_legal_safety?: string;
}

export interface AssignCaseResponse {
  assignmentId: string;
  inviteToken?: string | null;
  /** AIQ-1572: whether an invite email was queued. False for is_test (test-drive)
   *  assignments, which no longer email. Optional + defaulted true at the call site so
   *  an older payload keeps today's copy. */
  inviteEmailSent?: boolean;
}

export interface EmployeeAssignmentResponse {
  assignment: {
    id: string;
    case_id: string;
    employee_identifier: string;
    status: AssignmentStatus;
  } | null;
}

export interface EmployeeJourneyResponse {
  question: Question | null;
  isComplete: boolean;
  progress: {
    answeredCount: number;
    totalQuestions: number;
    percentComplete: number;
  };
  completeness: number;
  missingItems: string[];
  assignmentStatus?: AssignmentStatus;
  hrNotes?: string | null;
  profile?: RelocationProfile | null;
}

// ---------------------------------------------------------------------------
// Admin console types
// ---------------------------------------------------------------------------
export interface AdminContextResponse {
  isAdmin: boolean;
  impersonation?: {
    target_user_id: string;
    mode: 'hr' | 'employee';
  } | null;
}

export type CompanyPlanTier = 'low' | 'medium' | 'premium';
export type CompanyStatus = 'active' | 'inactive' | 'archived';

export interface AdminCompany {
  id: string;
  name: string;
  country?: string;
  size_band?: string;
  address?: string;
  phone?: string;
  hr_contact?: string;
  support_email?: string | null;
  created_at: string;
  updated_at?: string;
  status?: CompanyStatus | string;
  plan_tier?: CompanyPlanTier | string;
  hr_seat_limit?: number | null;
  employee_seat_limit?: number | null;
  missing_from_companies_table?: number;
  /** Company id exists in hr_users/relocation_cases but not in companies table (detail endpoint) */
  missing_from_registry?: boolean;
  /** From admin companies list: number of people linked with role HR */
  hr_users_count?: number;
  /** From admin companies list: number of people linked as employees */
  employee_count?: number;
  /** From admin companies list: number of assignments/cases linked to company */
  assignments_count?: number;
  /** Primary HR contact name, or first HR user, or null */
  primary_contact_name?: string | null;
}

export interface AdminProfile {
  id: string;
  role: string;
  email?: string;
  full_name?: string;
  company_id?: string;
  created_at: string;
  /** Resolved company name (from admin people API) */
  company_name?: string;
  /** active | inactive */
  status?: string;
  /** full_name || email || id */
  name?: string;
}

export interface AdminEmployee {
  id: string;
  company_id: string;
  profile_id: string;
  band?: string;
  assignment_type?: string;
  relocation_case_id?: string;
  status?: string;
  created_at: string;
  /** Resolved from profile (company detail endpoint) */
  name?: string;
  email?: string;
}

/** HR company-scoped employee (with profile display fields) */
export interface HrCompanyEmployee {
  id: string;
  company_id: string;
  profile_id: string;
  band?: string;
  assignment_type?: string;
  relocation_case_id?: string;
  status?: string;
  created_at: string;
  full_name?: string;
  email?: string;
  role?: string;
}

export interface AdminHrUser {
  id: string;
  company_id: string;
  profile_id: string;
  permissions_json?: string;
  created_at: string;
  /** Resolved from profile (company detail endpoint) */
  name?: string;
  email?: string;
  status?: string;
}

export interface AdminRelocationCase {
  id: string;
  company_id?: string;
  employee_id?: string;
  status?: string;
  stage?: string;
  host_country?: string;
  home_country?: string;
  created_at?: string;
  updated_at?: string;
}

/** Assignment row for admin company detail (with employee_name, destination) */
export interface AdminCompanyDetailAssignment {
  id: string;
  employee_name?: string;
  destination?: string;
  status?: string;
}

/** Policy row for admin company detail */
export interface AdminCompanyDetailPolicy {
  policy_id: string;
  title?: string;
  latest_version?: number;
  status?: string;
  published: boolean;
}

export interface AdminCompanyDetailCounts {
  hr_users_count: number;
  employees_count: number;
  assignments_count: number;
  policies_count: number;
}

export interface AdminCompanyDetailOrphanDiagnostics {
  assignments_case_missing_company_id?: number;
  hr_users_missing_profile?: number;
  employees_missing_profile?: number;
}

export interface AdminAssignment {
  id: string;
  case_id?: string;
  canonical_case_id?: string;
  hr_user_id?: string;
  employee_user_id?: string;
  employee_identifier?: string;
  status?: string;
  employee_first_name?: string;
  employee_last_name?: string;
  expected_start_date?: string;
  submitted_at?: string;
  created_at?: string;
  updated_at?: string;
  case_company_id?: string;
  host_country?: string;
  home_country?: string;
  case_status?: string;
  stage?: string;
  company_name?: string;
  employee_full_name?: string;
  hr_full_name?: string;
  employee_email?: string;
  hr_email?: string;
  employee_company_id?: string;
  hr_company_id?: string;
  company_id?: string;
  employee_profile_company_id?: string;
  hr_profile_company_id?: string;
  assignment_type?: string;
  move_date?: string;
  family_status?: string;
  destination_from_profile?: string;
  policy_resolved?: boolean;
  company_has_policy?: boolean;
  /** Normalized from backend list */
  assignment_id?: string;
  destination_country?: string;
  /** True when assignment has no employee_user_id and no employee_identifier */
  orphan_employee?: boolean;
}

export interface AdminPolicyCompany {
  company_id: string;
  company_name?: string;
  policy_id?: string;
  policy_title?: string;
  extraction_status?: string;
  policy_updated_at?: string;
  doc_count?: number;
  version_count?: number;
  latest_version_status?: string;
  latest_version_number?: number;
  latest_version_updated_at?: string;
  resolved_count?: number;
  policy_status: 'no_policy' | 'draft' | 'review_required' | 'reviewed' | 'published';
}

/** Single policy row in admin company-scoped policy list */
export interface AdminPolicySummary {
  policy_id: string;
  title?: string;
  extraction_status?: string;
  version_count: number;
  published_version_id?: string | null;
  published_at?: string | null;
  latest_version_status?: string | null;
  latest_version_number?: number | null;
  /** 'default_platform_template' | 'company_uploaded' */
  template_source?: string;
  template_name?: string | null;
  is_default_template?: boolean;
}

/** Response from GET /api/admin/policies?company_id= */
export interface AdminPoliciesByCompany {
  company_id: string;
  company_name?: string;
  source_document_count: number;
  /** Most recently uploaded policy document filename (same ordering as admin list). */
  latest_source_document_title?: string | null;
  policies: AdminPolicySummary[];
}

/** Default platform policy template (admin) */
export interface AdminPolicyTemplate {
  id: string;
  template_name: string;
  version: string;
  status: string;
  is_default_template?: boolean;
  snapshot_json?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

/** Response from GET /api/admin/policies/templates */
export interface AdminPolicyTemplatesResponse {
  templates: AdminPolicyTemplate[];
}

/** Policy version from admin versions list */
export interface AdminPolicyVersion {
  id: string;
  policy_id: string;
  version_number: number;
  status: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

/** Response from GET /api/admin/policies/{id} (detail with versions) */
export interface AdminPolicyDetail extends Record<string, unknown> {
  id: string;
  company_id: string;
  company_name?: string;
  title?: string;
  extraction_status?: string;
  source_document_count: number;
  versions: AdminPolicyVersion[];
  published_version?: AdminPolicyVersion | null;
  published_version_id?: string | null;
  published_at?: string | null;
}

export interface AdminAssignmentDetail extends AdminAssignment {
  employee_profile?: Record<string, unknown>;
  case_services?: Array<{ service_key: string; category: string; selected?: number }>;
  resolved_policy?: Record<string, unknown>;
  company_policies?: Array<{ id: string; title: string; extraction_status?: string }>;
  company_has_published_policy?: boolean;
  hr_profile_id?: string;
  emp_profile_id?: string;
  employee_email?: string;
  hr_email?: string;
  employee_profile_company_id?: string;
  hr_profile_company_id?: string;
  company_id?: string;
  // Resolved relocation-case primary key (rc.id) from the case_assignments →
  // relocation_cases join; case_status is inherited from AdminAssignment.
  case_pk?: string | null;
}

export interface AdminSupportCase {
  id: string;
  company_id: string;
  created_by_profile_id: string;
  employee_id?: string;
  hr_profile_id?: string;
  category: string;
  severity: string;
  status: string;
  summary?: string;
  last_error_code?: string;
  last_error_context_json?: string;
  created_at: string;
  updated_at: string;
  /** Ticket priority: low | medium | high | urgent */
  priority?: string;
  /** Profile ID of assigned admin/HR */
  assignee_id?: string | null;
}

export interface AdminSupportNote {
  id: string;
  support_case_id: string;
  author_user_id: string;
  note: string;
  created_at: string;
}

// --- Public Resources (safe, published content only) ---

export interface ResourceContext {
  caseId: string;
  countryCode: string;
  countryName?: string | null;
  cityName?: string | null;
  familyType: 'single' | 'couple' | 'family';
  hasChildren: boolean;
  childAges: number[];
  spouseWorking?: boolean | null;
  relocationType?: 'short_term' | 'long_term' | 'permanent' | null;
  preferredLanguage?: string | null;
  recommendedTags: string[];
}

export interface PublicResource {
  id: string;
  countryCode: string;
  countryName?: string | null;
  cityName?: string | null;
  categoryId?: string | null;
  title: string;
  summary: string;
  contentJson?: unknown;
  body?: string | null;
  resourceType?: string;
  audienceType?: string;
  minChildAge?: number | null;
  maxChildAge?: number | null;
  budgetTier?: string | null;
  languageCode?: string | null;
  isFamilyFriendly: boolean;
  isFeatured: boolean;
  address?: string | null;
  district?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  priceRangeText?: string | null;
  externalUrl?: string | null;
  bookingUrl?: string | null;
  contactInfo?: unknown;
  openingHours?: unknown;
  trustTier?: string | null;
  /** NAV-002: content-currency signal — when the resource was last updated. */
  updated_at?: string | null;
  tags?: ResourceTag[];
}

export interface PublicEvent {
  id: string;
  countryCode: string;
  countryName?: string | null;
  cityName?: string | null;
  title: string;
  description?: string | null;
  eventType: string;
  venueName?: string | null;
  address?: string | null;
  startDatetime: string;
  endDatetime?: string | null;
  priceText?: string | null;
  currency?: string | null;
  isFree: boolean;
  isFamilyFriendly: boolean;
  minAge?: number | null;
  maxAge?: number | null;
  languageCode?: string | null;
  externalUrl?: string | null;
  bookingUrl?: string | null;
  trustTier?: string | null;
}

export interface ResourceCategory {
  id: string;
  key: string;
  label: string;
  description?: string | null;
  iconName?: string | null;
  sortOrder?: number;
}

export interface ResourceTag {
  id: string;
  key: string;
  label: string;
  tagGroup?: string | null;
}

export interface RecommendationGroup {
  recommendedForYou: PublicResource[];
  firstSteps: PublicResource[];
  familyEssentials: PublicResource[];
  thisWeekend: PublicEvent[];
}

/**
 * AIQ-1581: LLM-generated "things to do" suggestion for a destination city.
 * Non-personal, generated on the fly — not persisted, not a live web search.
 */
export interface CityActivity {
  title: string;
  description: string;
  category?: string;
}

export interface CityActivitiesResponse {
  city: string;
  country: string;
  activities: CityActivity[];
}

export interface ResourcesPagePayload {
  context: ResourceContext;
  categories: ResourceCategory[];
  resources: PublicResource[];
  events: PublicEvent[];
  recommended: RecommendationGroup;
  hints: { priorities: string[]; recommendations: string[] };
  filtersApplied: Record<string, unknown>;
}

/** Policy-service comparison: employee request vs resolved policy */
export type PolicyStatus =
  | 'included'
  | 'capped'
  | 'approval_required'
  | 'excluded'
  | 'partial'
  | 'out_of_scope';

export interface PolicyServiceComparisonItem {
  service_category: string;
  benefit_key: string;
  label: string;
  requested_value_json: Record<string, unknown>;
  policy_status: PolicyStatus;
  explanation: string;
  variance_json: Record<string, unknown>;
  approval_required: boolean;
  evidence_required_json: string[];
  policy_min_value?: number | null;
  policy_standard_value?: number | null;
  policy_max_value?: number | null;
  currency?: string;
}

/** Row from effective-entitlement engine (GET policy-service-comparison). */
export interface EffectiveServiceComparisonRow {
  service_key: string;
  coverage_status: string;
  comparison_status: string;
  policy_limit_snapshot: Record<string, unknown>;
  selected_value_snapshot: Record<string, unknown>;
  delta: number | null;
  explanation: string;
  approval_required: boolean;
}

export interface PolicyServiceComparisonResponse {
  comparisons: PolicyServiceComparisonItem[];
  resolved_policy: { id: string; policy_version_id: string; resolved_at: string } | null;
  assignment_id: string;
  case_id?: string;
  message?: string;
  comparison_available?: boolean;
  comparison_readiness?: {
    comparison_ready: boolean;
    comparison_blockers: string[];
    partial_numeric_coverage?: boolean;
  };
  diagnostics?: { benefits_count: number; services_count: number; answers_keys: string[] };
  /** Canonical per-selected-service comparison; present for employee calls even when legacy comparisons are gated. */
  effective_service_comparison?: EffectiveServiceComparisonRow[];
}

// ── P3/B6: Exception flags ───────────────────────────────────────────────────

/**
 * A single immigration/policy exception flag detected by ExceptionRequestService.
 * Mirrors the exception_requests DB row returned by GET /api/cases/{id}/exceptions.
 */
export interface ExceptionFlag {
  id: string;
  case_id: string;
  assignment_id?: string | null;
  exception_type: string;
  reason: string;
  severity: 'blocker' | 'warning';
  status: 'pending' | 'approved' | 'denied' | 'escalated' | 'withdrawn';
  recommended_action?: string | null;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_notes?: string | null;
  created_at: string;
  updated_at: string;
}

/** Response shape from GET /api/cases/{case_id}/exceptions */
export interface CaseExceptionsResponse {
  case_id: string;
  blockers: ExceptionFlag[];
  warnings: ExceptionFlag[];
  total: number;
}


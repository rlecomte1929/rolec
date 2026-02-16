// TypeScript types matching backend schemas

export interface Question {
  id: string;
  title: string;
  whyThisMatters: string;
  type: string;
  options?: QuestionOption[];
  required: boolean;
  mapsTo: string;
  dependsOn?: any;
  validation?: any;
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

export interface LoginResponse {
  token: string;
  user: User;
}

export interface RegisterRequest {
  username?: string;
  email?: string;
  password: string;
  role: UserRole;
  name?: string;
}

export type UserRole = 'HR' | 'EMPLOYEE' | 'ADMIN';

export interface User {
  id: string;
  username?: string;
  email?: string;
  role: UserRole;
  name?: string;
  company?: string;
}

export interface AnswerRequest {
  questionId: string;
  answer: any;
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
  ocr?: Record<string, any>;
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
}

export interface CaseDraftDTO {
  relocationBasics: RelocationBasicsDTO;
  employeeProfile: EmployeeProfileDTO;
  familyMembers: FamilyMembersDTO;
  assignmentContext: AssignmentContextDTO;
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
  flags?: Record<string, any>;
  requirementsSnapshotId?: string;
}

export interface SourceRecordDTO {
  id: string;
  url: string;
  title: string;
  publisherDomain: string;
  retrievedAt: string;
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
  statusForCase: 'PROVIDED' | 'MISSING' | 'NEEDS_REVIEW';
  citations: SourceRecordDTO[];
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

export type AssignmentStatus =
  | 'IN_PROGRESS'
  | 'DRAFT'
  | 'EMPLOYEE_SUBMITTED'
  | 'HR_REVIEW'
  | 'HR_APPROVED'
  | 'CHANGES_REQUESTED';

export interface AssignmentSummary {
  id: string;
  caseId: string;
  employeeIdentifier: string;
  status: AssignmentStatus;
  submittedAt?: string;
  complianceStatus?: string | null;
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
}

export interface ComplianceReport {
  overallStatus: 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW';
  checks: ComplianceCheck[];
  actions: string[];
}

export interface ComplianceCheck {
  id: string;
  name: string;
  status: 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW';
  severity: 'low' | 'medium' | 'high';
  rationale: string;
  affectedFields: string[];
}

export interface AssignCaseResponse {
  assignmentId: string;
  inviteToken?: string | null;
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


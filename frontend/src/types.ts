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
  email: string;
  provider?: string;
}

export interface LoginResponse {
  token: string;
  userId: string;
  email: string;
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

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date
from enum import Enum


class MaritalStatus(str, Enum):
    MARRIED = "married"
    SINGLE = "single"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class ContractType(str, Enum):
    PERMANENT = "permanent"
    ASSIGNMENT = "assignment"
    CONTRACT = "contract"


class CurriculumType(str, Enum):
    IB = "IB"
    UK = "UK"
    US = "US"
    LOCAL = "Local"
    NO_PREFERENCE = "No preference"


class InventorySize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class ReadinessStatus(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class OverallStatus(str, Enum):
    ON_TRACK = "On track"
    AT_RISK = "At risk"


class UserRole(str, Enum):
    HR = "HR"
    EMPLOYEE = "EMPLOYEE"


# Child model
class Child(BaseModel):
    firstName: Optional[str] = None
    dateOfBirth: Optional[date] = None
    currentGrade: Optional[str] = None
    languageNeeds: Optional[str] = None


# Spouse model
class Spouse(BaseModel):
    fullName: Optional[str] = None
    nationality: Optional[str] = None
    wantsToWork: bool = True
    occupation: Optional[str] = None
    educationLevel: Optional[str] = None


# Passport model
class Passport(BaseModel):
    number: Optional[str] = None
    expiryDate: Optional[date] = None
    issuingCountry: Optional[str] = None


# Employer model
class Employer(BaseModel):
    name: str = "Norwegian Investment"
    roleTitle: Optional[str] = None
    jobLevel: Optional[str] = None
    contractType: Optional[ContractType] = None
    salaryBand: Optional[str] = None


# Assignment model
class Assignment(BaseModel):
    startDate: Optional[date] = None
    expectedDurationMonths: Optional[int] = None
    relocationPackage: Optional[bool] = None
    relocationPackageNotes: Optional[str] = None


# Primary applicant model
class PrimaryApplicant(BaseModel):
    fullName: Optional[str] = None
    nationality: Optional[str] = None
    dateOfBirth: Optional[date] = None
    photoUrl: Optional[str] = None
    passport: Passport = Field(default_factory=Passport)
    employer: Employer = Field(default_factory=Employer)
    assignment: Assignment = Field(default_factory=Assignment)


# Housing preferences
class HousingPreferences(BaseModel):
    desiredMoveInDate: Optional[date] = None
    temporaryStayWeeks: Optional[int] = None
    budgetMonthlySGD: Optional[str] = None
    bedroomsMin: int = 3
    preferredAreas: List[str] = Field(default_factory=list)
    mustHave: List[str] = Field(default_factory=list)


# Schooling preferences
class SchoolingPreferences(BaseModel):
    schoolingStartDate: Optional[date] = None
    curriculumPreference: Optional[CurriculumType] = None
    budgetAnnualSGD: Optional[str] = None
    priorities: List[str] = Field(default_factory=list)


# Movers preferences
class MoversPreferences(BaseModel):
    inventoryRough: Optional[InventorySize] = None
    specialItems: List[str] = Field(default_factory=list)
    storageNeeded: Optional[bool] = None
    insuranceNeeded: Optional[bool] = None


# Move plan model
class MovePlan(BaseModel):
    origin: str = "Oslo, Norway"
    destination: str = "Singapore"
    targetArrivalDate: Optional[date] = None
    shippingDatePreference: Optional[date] = None
    housing: HousingPreferences = Field(default_factory=HousingPreferences)
    schooling: SchoolingPreferences = Field(default_factory=SchoolingPreferences)
    movers: MoversPreferences = Field(default_factory=MoversPreferences)


# Compliance & docs
class ComplianceDocs(BaseModel):
    hasPassportScans: Optional[bool] = None
    hasMarriageCertificate: Optional[bool] = None
    hasBirthCertificates: Optional[bool] = None
    hasEmploymentLetter: Optional[bool] = None
    hasBankStatements: Optional[bool] = None
    notes: Optional[str] = None


# Main RelocationProfile
class RelocationProfile(BaseModel):
    userId: Optional[str] = None
    familySize: int = 4
    maritalStatus: Optional[MaritalStatus] = None
    dependents: List[Child] = Field(default_factory=lambda: [Child(), Child()])
    spouse: Spouse = Field(default_factory=Spouse)
    primaryApplicant: PrimaryApplicant = Field(default_factory=PrimaryApplicant)
    movePlan: MovePlan = Field(default_factory=MovePlan)
    complianceDocs: ComplianceDocs = Field(default_factory=ComplianceDocs)


# Question models
class QuestionOption(BaseModel):
    value: str
    label: str
    icon: Optional[str] = None


class Question(BaseModel):
    id: str
    title: str
    whyThisMatters: str
    type: str  # single_select, multi_select, text, date, number, range, boolean, address
    options: Optional[List[QuestionOption]] = None
    required: bool = True
    mapsTo: str  # JSON pointer in profile
    dependsOn: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    allowUnknown: bool = False


# API request/response models
class RegisterRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    role: UserRole
    name: Optional[str] = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: Optional[str] = None
    email: Optional[str] = None
    role: UserRole
    name: Optional[str] = None
    company: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserResponse




class AnswerRequest(BaseModel):
    questionId: str
    answer: Any
    isUnknown: bool = False


class NextQuestionResponse(BaseModel):
    question: Optional[Question] = None
    isComplete: bool = False
    progress: Dict[str, Any] = Field(default_factory=dict)


class ValidationError(BaseModel):
    field: str
    message: str


class ImmigrationReadiness(BaseModel):
    score: int
    status: ReadinessStatus
    reasons: List[str]
    missingDocs: List[str]


class HousingRecommendation(BaseModel):
    id: str
    name: str
    area: str
    bedrooms: int
    furnished: bool
    nearMRT: bool
    estMonthlySGDMin: int
    estMonthlySGDMax: int
    familyFriendlyScore: int
    notes: str
    rationale: str
    nextAction: str = "View details"


class SchoolRecommendation(BaseModel):
    id: str
    name: str
    area: str
    curriculumTags: List[str]
    ageRange: str
    estAnnualSGDMin: int
    estAnnualSGDMax: int
    languageSupport: List[str]
    notes: str
    rationale: str
    nextAction: str = "Request application info"


class MoverRecommendation(BaseModel):
    id: str
    name: str
    serviceTags: List[str]
    notes: str
    rfqTemplate: str
    rationale: str
    nextAction: str = "Request quote"


class TimelineTask(BaseModel):
    title: str
    status: str  # todo, in_progress, done
    dueDate: Optional[str] = None


class TimelinePhase(BaseModel):
    phase: str
    tasks: List[TimelineTask]


class DashboardResponse(BaseModel):
    profileCompleteness: int
    immigrationReadiness: ImmigrationReadiness
    nextActions: List[str]
    timeline: List[TimelinePhase]
    recommendations: Dict[str, List[Any]]
    overallStatus: OverallStatus


class AssignmentStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    EMPLOYEE_SUBMITTED = "EMPLOYEE_SUBMITTED"
    HR_REVIEW = "HR_REVIEW"
    HR_APPROVED = "HR_APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class AssignmentSummary(BaseModel):
    id: str
    caseId: str
    employeeIdentifier: str
    status: AssignmentStatus
    submittedAt: Optional[str] = None
    complianceStatus: Optional[str] = None


class AssignmentDetail(BaseModel):
    id: str
    caseId: str
    employeeIdentifier: str
    status: AssignmentStatus
    submittedAt: Optional[str] = None
    hrNotes: Optional[str] = None
    profile: Optional[RelocationProfile] = None
    completeness: Optional[int] = None
    complianceReport: Optional[Dict[str, Any]] = None


class HRAssignmentDecision(BaseModel):
    decision: AssignmentStatus
    notes: Optional[str] = None
    requestedSections: Optional[List[str]] = None


class CreateCaseResponse(BaseModel):
    caseId: str


class AssignCaseRequest(BaseModel):
    employeeIdentifier: str


class AssignCaseResponse(BaseModel):
    assignmentId: str
    inviteToken: Optional[str] = None


class UpdateAssignmentIdentifierRequest(BaseModel):
    employeeIdentifier: str


class ClaimAssignmentRequest(BaseModel):
    email: str


class EmployeeJourneyRequest(BaseModel):
    assignmentId: str
    questionId: str
    answer: Any


class EmployeeJourneyNextQuestion(BaseModel):
    question: Optional[Question] = None
    isComplete: bool = False
    progress: Dict[str, Any] = Field(default_factory=dict)
    completeness: int = 0
    missingItems: List[str] = Field(default_factory=list)
    assignmentStatus: Optional[AssignmentStatus] = None
    hrNotes: Optional[str] = None
    profile: Optional[RelocationProfile] = None


class UpdateProfilePhotoRequest(BaseModel):
    assignmentId: str
    photoUrl: str


class PolicyExceptionRequest(BaseModel):
    category: str
    reason: Optional[str] = None
    amount: Optional[float] = None
class ComplianceActionRequest(BaseModel):
    actionType: str
    checkId: str
    notes: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

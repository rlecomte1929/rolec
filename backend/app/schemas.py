from pydantic import BaseModel
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
    relocationBasics: RelocationBasicsDTO
    employeeProfile: EmployeeProfileDTO
    familyMembers: FamilyMembersDTO
    assignmentContext: AssignmentContextDTO


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

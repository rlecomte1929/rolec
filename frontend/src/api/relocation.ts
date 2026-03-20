import { apiGet, apiPost } from './client';
import type {
  RelocationCase,
  RelocationCaseListItem,
  RelocationRun,
  RequirementItemDTO,
  CaseRequirementsDTO,
  CaseClassification,
  NextAction,
} from '../types';

const missingFieldLabels: Record<string, string> = {
  origin_country: 'Origin country',
  destination_country: 'Destination country',
  employment_type: 'Employment type',
  move_date: 'Move date',
  employer_country: 'Employer country',
};

const toTitleCase = (value: string) =>
  value
    .replace(/_/g, ' ')
    .split(' ')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

/**
 * ReloPass wizard + requirements use the main API with the ReloPass session token.
 * (Supabase JWT-only relocation routes do not see HR-created cases in Postgres.)
 */
export const listRelocationCases = async (): Promise<RelocationCaseListItem[]> => {
  return apiGet<RelocationCaseListItem[]>('/api/relocation/cases');
};

export const getRelocationCase = async (caseId: string): Promise<RelocationCase> => {
  return apiGet<RelocationCase>(`/api/relocation/case/${encodeURIComponent(caseId)}`);
};

export const getRelocationRuns = async (caseId: string): Promise<RelocationRun[]> => {
  return apiGet<RelocationRun[]>(`/api/relocation/case/${encodeURIComponent(caseId)}/runs`);
};

export const classifyRelocationCase = async (
  caseId: string
): Promise<{ case_id: string; classification: CaseClassification }> => {
  return apiPost<{ case_id: string; classification: CaseClassification }>(
    `/api/relocation/case/${encodeURIComponent(caseId)}/classify`
  );
};

export const getRelocationCaseClassification = async (
  caseId: string
): Promise<{ case_id: string; classification: CaseClassification; version: number; created_at: string }> => {
  return apiGet<{
    case_id: string;
    classification: CaseClassification;
    version: number;
    created_at: string;
  }>(`/api/relocation/case/${encodeURIComponent(caseId)}/classification`);
};

export const buildNextActionsFromMissingFields = (missingFields: string[]): NextAction[] => {
  return missingFields.map((field) => ({
    key: `collect_${field}`,
    label: `Add your ${(missingFieldLabels[field] || toTitleCase(field)).toLowerCase()}`,
    priority: 'high',
  }));
};

export const buildRequirementsFromMissingFields = (caseId: string, missingFields: string[]): CaseRequirementsDTO => {
  const requirements: RequirementItemDTO[] = missingFields.map((field) => ({
    id: `missing:${field}`,
    pillar: 'Intake',
    title: missingFieldLabels[field] || toTitleCase(field),
    description: 'This detail is required to complete your intake.',
    severity: 'BLOCKER',
    owner: 'Employee',
    requiredFields: [field],
    statusForCase: 'MISSING',
    citations: [],
  }));

  return {
    caseId,
    destCountry: '',
    purpose: '',
    computedAt: new Date().toISOString(),
    requirements,
    sources: [],
  };
};

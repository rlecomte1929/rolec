import { API_BASE_URL } from './client';
import { supabase } from './supabase';
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

const getSessionToken = async () => {
  const { data } = await supabase.auth.getSession();
  const token = data?.session?.access_token;
  if (!token) {
    throw new Error('Not authenticated');
  }
  return token;
};

const apiFetch = async <T>(path: string): Promise<T> => {
  const token = await getSessionToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Not authenticated');
    }
    if (res.status === 404) {
      throw new Error('Not found');
    }
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  return res.json() as Promise<T>;
};

const apiPost = async <T>(path: string): Promise<T> => {
  const token = await getSessionToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Not authenticated');
    }
    if (res.status === 404) {
      throw new Error('Not found');
    }
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  return res.json() as Promise<T>;
};

export const listRelocationCases = async (): Promise<RelocationCaseListItem[]> => {
  return apiFetch<RelocationCaseListItem[]>('/api/relocation/cases');
};

export const getRelocationCase = async (caseId: string): Promise<RelocationCase> => {
  return apiFetch<RelocationCase>(`/api/relocation/case/${caseId}`);
};

export const getRelocationRuns = async (caseId: string): Promise<RelocationRun[]> => {
  return apiFetch<RelocationRun[]>(`/api/relocation/case/${caseId}/runs`);
};

export const classifyRelocationCase = async (
  caseId: string
): Promise<{ case_id: string; classification: CaseClassification }> => {
  return apiPost<{ case_id: string; classification: CaseClassification }>(
    `/api/relocation/case/${caseId}/classify`
  );
};

export const getRelocationCaseClassification = async (
  caseId: string
): Promise<{ case_id: string; classification: CaseClassification; version: number; created_at: string }> => {
  return apiFetch<{ case_id: string; classification: CaseClassification; version: number; created_at: string }>(
    `/api/relocation/case/${caseId}/classification`
  );
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

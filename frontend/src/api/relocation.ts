import type {
  RelocationCase,
  RelocationCaseListItem,
  RelocationRun,
  CaseClassification,
  NextAction,
} from '../types';
import { apiGet, apiPost } from './client';

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

// buildRequirementsFromMissingFields was removed here.
//
// It synthesised a fake CaseRequirementsDTO client-side out of `missing_fields`,
// forcing every item to pillar 'Intake', severity BLOCKER, status MISSING — and
// Step 5 rendered it as though it were the destination requirements dossier. So the
// screen showed "your intake form is incomplete" while implying "here is what the
// law requires of you". Two different claims.
//
// Step 5 now calls the real endpoint (api/cases.getRequirements), and
// `missing_fields` keeps its actual job: intake completeness, which still gates the
// dossier-suggestion button and the submit flow.

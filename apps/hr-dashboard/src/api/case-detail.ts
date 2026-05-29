import { api } from '../lib/api';
import type {
  CaseDocument,
  CaseOverview,
  CaseStep,
  ContradictionsSummary,
} from '../features/case-detail/types';

/**
 * Case Detail API client.
 *
 * Backend routes (TBD per the C1-11c brief — backend-side work tracked
 * under the C1-11c epic; these contracts are stable so the frontend can
 * ship against them without ripple):
 *
 *   GET /api/hr/cases/{case_id}/overview
 *   GET /api/hr/cases/{case_id}/documents
 *   GET /api/hr/cases/{case_id}/steps
 *   GET /api/hr/cases/{case_id}/contradictions/summary
 *
 * RLS: every route already filters by JWT.company_id server-side (same
 * pattern as listCases in api/cases.ts). The frontend does NOT send a
 * tenant query — the JWT does the work.
 */

interface OverviewResponse {
  overview: CaseOverview;
}

interface DocumentsResponse {
  documents: CaseDocument[];
}

interface StepsResponse {
  steps: CaseStep[];
}

interface ContradictionsSummaryResponse {
  summary: ContradictionsSummary;
}

export async function fetchCaseOverview(caseId: string): Promise<CaseOverview> {
  const { data } = await api.get<OverviewResponse>(`/api/hr/cases/${caseId}/overview`);
  return data.overview;
}

export async function fetchCaseDocuments(caseId: string): Promise<CaseDocument[]> {
  const { data } = await api.get<DocumentsResponse>(`/api/hr/cases/${caseId}/documents`);
  return data?.documents ?? [];
}

export async function fetchCaseSteps(caseId: string): Promise<CaseStep[]> {
  const { data } = await api.get<StepsResponse>(`/api/hr/cases/${caseId}/steps`);
  return data?.steps ?? [];
}

export async function fetchContradictionsSummary(caseId: string): Promise<ContradictionsSummary> {
  const { data } = await api.get<ContradictionsSummaryResponse>(
    `/api/hr/cases/${caseId}/contradictions/summary`,
  );
  return data.summary;
}

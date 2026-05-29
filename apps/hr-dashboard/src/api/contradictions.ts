import { api } from '../lib/api';
import type {
  Contradiction,
  PriorCorrection,
  ResolvePayload,
  ResolveResponse,
} from '../features/resolution/types';

/**
 * Contradiction API client.
 *
 * Backend routes (TBD per C1-16 audit endpoint task):
 *   GET  /api/hr/cases/{case_id}/contradictions
 *   GET  /api/hr/cases/{case_id}/contradictions/{cid}/history
 *   POST /api/hr/cases/{case_id}/contradictions/{cid}/resolve
 *
 * Until those land, this module is the single touch point that future
 * backend changes can adjust without rippling through the UI.
 */

interface CaseContradictionsResponse {
  contradictions: Contradiction[];
}

interface CorrectionHistoryResponse {
  corrections: PriorCorrection[];
}

export async function listCaseContradictions(caseId: string): Promise<Contradiction[]> {
  const { data } = await api.get<CaseContradictionsResponse>(
    `/api/hr/cases/${caseId}/contradictions`,
  );
  return data?.contradictions ?? [];
}

export async function listCorrectionHistory(
  caseId: string,
  contradictionId: string,
): Promise<PriorCorrection[]> {
  const { data } = await api.get<CorrectionHistoryResponse>(
    `/api/hr/cases/${caseId}/contradictions/${contradictionId}/history`,
  );
  return data?.corrections ?? [];
}

export async function resolveContradiction(
  caseId: string,
  contradictionId: string,
  payload: ResolvePayload,
): Promise<ResolveResponse> {
  const { data } = await api.post<ResolveResponse>(
    `/api/hr/cases/${caseId}/contradictions/${contradictionId}/resolve`,
    payload,
  );
  return data;
}

import { apiGet, apiPatch, apiPost } from './client';
import type { CaseDTO, CaseDraftDTO, CaseRequirementsDTO, CaseExceptionsResponse, ExceptionFlag } from '../types';

export async function getCase(caseId: string): Promise<CaseDTO> {
  return apiGet(`/api/cases/${caseId}`);
}

export async function patchCase(caseId: string, patch: Partial<CaseDraftDTO>): Promise<CaseDTO> {
  return apiPatch(`/api/cases/${caseId}`, patch);
}

export async function startResearch(caseId: string): Promise<{ jobId: string }> {
  return apiPost(`/api/cases/${caseId}/research/start`);
}

export async function getRequirements(caseId: string): Promise<CaseRequirementsDTO> {
  return apiGet(`/api/cases/${caseId}/requirements`);
}

export async function createCase(caseId: string): Promise<{ createdCaseId: string; requirementsSnapshotId: string }> {
  return apiPost(`/api/cases/${caseId}/create`);
}

/**
 * Fetch exception flags for a case from the ExceptionRequestService.
 * Returns blockers and warnings detected during timeline generation.
 * Returns null on network/auth error so callers can fail silently.
 */
export async function fetchCaseExceptions(caseId: string): Promise<CaseExceptionsResponse | null> {
  if (!caseId) return null;
  try {
    return await apiGet<CaseExceptionsResponse>(`/api/cases/${caseId}/exceptions`);
  } catch {
    return null;
  }
}

export type ExceptionResolutionStatus = 'approved' | 'denied' | 'escalated' | 'withdrawn';

export interface UpdateExceptionPayload {
  status: ExceptionResolutionStatus;
  resolution_notes?: string;
}

/**
 * Approve, deny, escalate, or withdraw an exception flag.
 * HR-only — throws on auth failure or if the flag is not found.
 */
export async function updateCaseException(
  caseId: string,
  exceptionId: string,
  payload: UpdateExceptionPayload,
): Promise<ExceptionFlag> {
  return apiPatch<ExceptionFlag>(
    `/api/cases/${caseId}/exceptions/${exceptionId}`,
    payload,
  );
}

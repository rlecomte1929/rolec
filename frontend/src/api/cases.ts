import { apiGet, apiPatch, apiPost } from './client';
import type { CaseDTO, CaseDraftDTO, CaseRequirementsDTO } from '../types';

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

import { apiGet, apiPost } from './client';

/**
 * Outcome-sharing consent (P1-07c / AIQ-686). The employee opts in (per case) to
 * letting ReloPass use their *anonymized* relocation outcome to improve the AI.
 * Optional + withdrawable; gates the AIQ-685 outcome_extractor server-side.
 * Endpoint: /api/employee/cases/{case_id}/outcome-consent.
 */
export interface OutcomeConsentState {
  case_id: string;
  purpose: string;
  consented: boolean | null;
  consent_version: string;
}

export async function getOutcomeConsent(caseId: string): Promise<OutcomeConsentState> {
  return apiGet(`/api/employee/cases/${encodeURIComponent(caseId)}/outcome-consent`);
}

export async function setOutcomeConsent(
  caseId: string,
  consented: boolean,
): Promise<{ consented: boolean; consent_version: string }> {
  return apiPost(`/api/employee/cases/${encodeURIComponent(caseId)}/outcome-consent`, { consented });
}

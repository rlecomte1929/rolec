import { apiGet } from './client';

/**
 * HR AI case summary (AIQ-1697).
 * GET /api/hr/cases/{assignmentId}/ai-summary — the backend proxies to the
 * `case-summary` Edge Function (AIQ-1693/1698) with the caller's company_id. The
 * browser never calls the function directly. Four grounded, PII-safe sections.
 */
export interface CaseSummary {
  status: string;
  blockers: string[];
  next_actions: string[];
  cost_variance: string;
}

export interface CaseAiSummaryResponse {
  assignment_id: string;
  company_id: string;
  summary: CaseSummary;
  generated_at: string;
}

export async function getCaseAiSummary(assignmentId: string): Promise<CaseAiSummaryResponse> {
  return apiGet<CaseAiSummaryResponse>(
    `/api/hr/cases/${encodeURIComponent(assignmentId)}/ai-summary`,
  );
}

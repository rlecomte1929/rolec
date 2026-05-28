/**
 * Exception requests API client (T1.3).
 *
 * Thin wrapper around the apiGet/apiPost/apiPatch helpers in client.ts so
 * that the new surface is reviewable in isolation and easy to mock in tests.
 */

import { apiGet, apiPatch, apiPost } from './client';

export type ExceptionStatus = 'pending' | 'approved' | 'rejected';

/**
 * Structured precedent insight (AI-005). Computed by the backend from
 * historical decisions on similar exceptions, deterministic per call.
 * Used as the `aiOutput` payload for the AIRecommendationCard in the
 * exceptions inbox so the human's accept/override/reject can be replayed
 * against the same insight version.
 */
export interface PrecedentInsight {
  rationale: string;
  confidence: number;
  historical_approval_rate: number;
  sample_size: number;
  similar_case_ids: string[];
  generated_at: string;
  source_version: string;
  recommendation_id: string;
}

export interface ExceptionRequest {
  id: string;
  case_id: string;
  organization_id: string;
  category: string;
  requested_amount: number;
  cap_amount: number;
  currency: string;
  reason: string;
  status: ExceptionStatus;
  hr_note: string | null;
  benefit_key?: string | null;
  ai_insight?: string | null;
  precedent_insight?: PrecedentInsight | null;
  requested_by_user_id: string;
  resolved_by_user_id: string | null;
  created_at: string;
  resolved_at: string | null;
  updated_at: string;
}

export interface CreateExceptionRequestBody {
  category: string;
  requested_amount: number;
  cap_amount: number;
  currency: string;
  reason: string;
}

export interface ResolveExceptionRequestBody {
  status: 'approved' | 'rejected';
  hr_note?: string;
}

/** Employee or HR opens a new exception request for a case. */
export const createExceptionRequest = (
  caseId: string,
  body: CreateExceptionRequestBody,
): Promise<ExceptionRequest> =>
  apiPost<ExceptionRequest>(`/api/cases/${encodeURIComponent(caseId)}/exception-requests`, body);

/** List all exception requests on a case (tenant-scoped server-side). */
export const listExceptionRequestsForCase = (caseId: string): Promise<ExceptionRequest[]> =>
  apiGet<ExceptionRequest[]>(`/api/cases/${encodeURIComponent(caseId)}/exception-requests`);

/** HR / Admin: list every exception request across the caller's company. */
export const listExceptionRequestsForCompany = (
  status?: ExceptionStatus,
): Promise<ExceptionRequest[]> => {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiGet<ExceptionRequest[]>(`/api/exception-requests${qs}`);
};

/** HR approves or rejects a pending exception request. */
export const resolveExceptionRequest = (
  requestId: string,
  body: ResolveExceptionRequestBody,
): Promise<ExceptionRequest> =>
  apiPatch<ExceptionRequest>(`/api/exception-requests/${encodeURIComponent(requestId)}`, body);

/**
 * Exception requests API client (T1.3).
 *
 * Thin wrapper around the apiGet/apiPost/apiPatch helpers in client.ts so
 * that the new surface is reviewable in isolation and easy to mock in tests.
 */

import { apiGet, apiPatch, apiPost } from './client';

export type ExceptionStatus = 'pending' | 'approved' | 'rejected';

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

/** HR approves or rejects a pending exception request. */
export const resolveExceptionRequest = (
  requestId: string,
  body: ResolveExceptionRequestBody,
): Promise<ExceptionRequest> =>
  apiPatch<ExceptionRequest>(`/api/exception-requests/${encodeURIComponent(requestId)}`, body);

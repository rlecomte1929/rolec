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

/** UI-known category enum used by the HR exceptions inbox to map a server-side
 * free-form `category` string to one of four display tiles. The backend itself
 * keeps the column permissive (existing flows use it for service categories
 * like 'housing'); the inbox does the mapping client-side. See PR #157 body
 * for the data-model question still open. */
export type ExceptionCategory =
  | 'new_category'
  | 'cap_override'
  | 'timeline_extension'
  | 'additional_coverage';

export interface ExceptionRequest {
  id: string;
  case_id: string;
  organization_id: string;
  category: string; // service-category axis (housing, schools, ...)
  /** Q3-A: HR-inbox exception-type axis. NULL on legacy rows (the inbox
   * client-side mapping handles the fallback in that case). */
  exception_type: ExceptionCategory | null;
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
  // Joined fields (AI-005 follow-up). All optional — empty when the join
  // returns NULL (legacy rows or missing profile / mobility_cases record).
  requested_by_name?: string | null;
  requested_by_role?: string | null;
  resolved_by_name?: string | null;
  origin_country?: string | null;
  destination_country?: string | null;
}

/** One row from public.audit_logs surfaced through the audit-trail endpoint. */
export interface ExceptionAuditEvent {
  id: string;
  entity_type: string;
  entity_id: string;
  action_type: string;
  actor_type?: string | null;
  actor_id?: string | null;
  actor_name?: string | null;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface CreateExceptionRequestBody {
  /** Service-category axis (housing, schools, movers, ...). Free-form on the
   * backend; existing flows write this from RequestExceptionModal. */
  category: string;
  /** Q3-A: HR-inbox exception-type axis. Optional during the transition
   * window; surfaces that know it (the HR inbox) should set it so the
   * column is populated for new rows. */
  exception_type?: ExceptionCategory;
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

/** Fetch the audit trail (joined audit_logs) for a single exception request.
 * HR / admin only; tenant-scoped server-side. Returns rows oldest-first. */
export const getExceptionAuditTrail = (
  requestId: string,
): Promise<ExceptionAuditEvent[]> =>
  apiGet<ExceptionAuditEvent[]>(
    `/api/exception-requests/${encodeURIComponent(requestId)}/audit-trail`,
  );

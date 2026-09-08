/**
 * GAP 7: Assignment-scoped exception requests
 *   GET    /api/assignments/{id}/exceptions
 *   POST   /api/assignments/{id}/exceptions
 *   PATCH  /api/assignments/{id}/exceptions/{exceptionId}
 *
 * Used by the employee benefit card ("Request exception") and the
 * HR review queue (S5b — Exceptions & Approvals screen).
 *
 * Separate from the legacy case-scoped exceptions at /api/cases/{id}/exception-requests.
 */
import { apiGet, apiPatch } from './client';

/** Q3-A: HR-inbox exception-type axis. Same 4-value set used by the
 * case-scoped /api/cases/:case_id/exception-requests endpoint. */
export type AssignmentExceptionType =
  | 'new_category'
  | 'cap_override'
  | 'timeline_extension'
  | 'additional_coverage';

export interface AssignmentExceptionRead {
  id: string;
  assignment_id: string;
  benefit_key: string;
  type_label: string | null;
  /** Q3-A: distinct from `benefit_key`. One of the 4 HR-inbox axis values. */
  exception_type: AssignmentExceptionType | null;
  current_value: Record<string, unknown> | null;
  requested_value: Record<string, unknown> | null;
  reason: string;
  /** pending | approved | rejected */
  status: 'pending' | 'approved' | 'rejected';
  hr_note: string | null;
  ai_insight: string | null;
  audit_events: Array<{ ts: string; actor: string; action: string; note: string }> | null;
  requested_by_user_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ExceptionPatch {
  status: 'approved' | 'rejected';
  hr_note?: string;
  /** Optional AI-generated insight for the HR reviewer */
  ai_insight?: string;
}

/**
 * GAP 7: List exception requests for an assignment.
 */
export async function listAssignmentExceptions(
  assignmentId: string,
  status?: 'pending' | 'approved' | 'rejected',
): Promise<AssignmentExceptionRead[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiGet<AssignmentExceptionRead[]>(
    `/api/assignments/${assignmentId}/exceptions${qs}`,
  );
}

/**
 * GAP 7: HR approves or rejects an exception request.
 */
export async function resolveAssignmentException(
  assignmentId: string,
  exceptionId: string,
  body: ExceptionPatch,
): Promise<AssignmentExceptionRead> {
  return apiPatch<AssignmentExceptionRead>(
    `/api/assignments/${assignmentId}/exceptions/${exceptionId}`,
    body,
  );
}

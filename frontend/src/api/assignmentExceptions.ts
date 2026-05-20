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
import { apiGet, apiPost, apiPatch } from './client';

export interface AssignmentExceptionCreate {
  /** Benefit key from BENEFIT_COLUMNS, e.g. "temporary_housing", "schooling" */
  benefit_key: string;
  /** Human-readable label, e.g. "Temporary housing cap override" */
  type_label: string;
  /** Current policy value, e.g. { amount: 1500, currency: "EUR" } */
  current_value: Record<string, unknown>;
  /** What the employee is requesting, e.g. { amount: 2200, currency: "EUR" } */
  requested_value: Record<string, unknown>;
  reason: string;
}

export interface AssignmentExceptionRead {
  id: string;
  assignment_id: string;
  benefit_key: string;
  type_label: string | null;
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
 * GAP 7: Create an exception request for a benefit on an assignment.
 */
export async function createAssignmentException(
  assignmentId: string,
  body: AssignmentExceptionCreate,
): Promise<AssignmentExceptionRead> {
  return apiPost<AssignmentExceptionRead>(
    `/api/assignments/${assignmentId}/exceptions`,
    body,
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

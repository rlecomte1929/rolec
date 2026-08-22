/**
 * [AIQ-2088] HR case closure — the end of the relocation lifecycle.
 *
 * `AssignmentStatus.CLOSED` has always been a legal status and no HR-reachable code
 * path had ever written it: 0 of 1,418 production assignments were closed. These two
 * calls are that path.
 *
 * Keyed on the ASSIGNMENT id (`detail.id`), not the relocation-case UUID
 * (`detail.caseId`) — closure sets `case_assignments.status`.
 */
import { apiGet, apiPost } from './client';

export interface ClosureOutstanding {
  open_rfqs: number;
  incomplete_milestones: number;
}

export interface ClosureReadiness {
  assignment_id: string;
  status: string | null;
  already_closed: boolean;
  outstanding: ClosureOutstanding;
}

export interface CloseResult {
  assignment_id: string;
  status: string;
  already_closed: boolean;
  outstanding_at_close: ClosureOutstanding;
}

/** What is still open on the case. Advisory only — it can never refuse a closure. */
export const getClosureReadiness = (assignmentId: string): Promise<ClosureReadiness> =>
  apiGet<ClosureReadiness>(
    `/api/hr/assignments/${encodeURIComponent(assignmentId)}/closure-readiness`,
  );

/** Close the relocation. Idempotent; the backend records what was outstanding. */
export const closeAssignment = (assignmentId: string, reason?: string): Promise<CloseResult> =>
  apiPost<CloseResult>(`/api/hr/assignments/${encodeURIComponent(assignmentId)}/close`, {
    reason: reason?.trim() ? reason.trim() : null,
  });

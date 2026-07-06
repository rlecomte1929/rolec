import { apiGet, apiPost } from './client';

/** AIQ-1414 — one persisted conversational turn (user + coordinator reply). */
export interface CoordinatorTurn {
  user: string;
  assistant: string;
}

/** The persisted coordinator session for one relocation case. */
export interface CoordinatorSession {
  case_id: string;
  rolling_summary: string;
  recent_turns: CoordinatorTurn[];
  model: string;
  status: string;
}

/** One coordinator reply. */
export interface CoordinatorRespondResult {
  answer: string;
  model: string;
  case_id: string;
}

/**
 * Mobility Coordinator API (AIQ-1414). Both routes are flag-gated server-side
 * (`RELOPASS_AI_COORDINATOR_ENABLED`) and 404 when the feature is off — callers
 * treat 404 as "coordinator unavailable" (see CoordinatorChatPanel).
 */
export const coordinatorAPI = {
  getSession: (caseId: string): Promise<CoordinatorSession> =>
    apiGet(`/api/cases/${encodeURIComponent(caseId)}/coordinator/session`),
  respond: (caseId: string, message: string): Promise<CoordinatorRespondResult> =>
    apiPost(`/api/cases/${encodeURIComponent(caseId)}/coordinator/respond`, { message }),
};

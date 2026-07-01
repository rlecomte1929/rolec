/**
 * Setup & Help Assistant API — HR-facing.
 *
 * Two endpoints consumed by SetupAssistantPanel:
 *   GET  /api/hr/setup-status  → setup progress summary
 *   POST /api/hr/setup-assistant/query → Q&A answer with next-step deep link
 *
 * Uses the same apiGet/apiPost helpers as other thin API modules (e.g.
 * policyAssistantQuery.ts) so auth headers + timeout + perf tracking are
 * inherited automatically.
 */
import { apiGet, apiPost } from './client';

// ── Response shapes ─────────────────────────────────────────────────────────

export interface SetupNextStep {
  label: string;
  route: string | null;
}

/** GET /api/hr/setup-status */
export interface SetupStatus {
  company_profile_complete: boolean;
  policy_published: boolean;
  cases_count: number;
  employees_invited: number;
  first_case_id: string | null;
  next_step: SetupNextStep;
}

/** POST /api/hr/setup-assistant/query */
export interface SetupAssistantAnswer {
  answer: string;
  next_step: SetupNextStep | null;
  cited_topics: string[];
  error?: boolean;
}

// ── API functions ─────────────────────────────────────────────────────────

export async function getSetupStatus(): Promise<SetupStatus> {
  return apiGet<SetupStatus>('/api/hr/setup-status');
}

export async function askSetupAssistant(question: string): Promise<SetupAssistantAnswer> {
  return apiPost<SetupAssistantAnswer>('/api/hr/setup-assistant/query', { question });
}

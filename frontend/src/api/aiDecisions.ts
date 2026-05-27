/**
 * AI decisions API client (AI-002).
 *
 * Persists HR accept / override / reject actions on AI-generated recommendations
 * for EU AI Act Art. 14 (human oversight) compliance.
 */

import { apiGet, apiPost } from './client';

export type AIDecisionAction = 'accept' | 'override' | 'reject';

export interface AIDecisionRecord {
  id: string;
  created_at: string;
  updated_at: string;
  actor_id: string | null;
  company_id: string | null;
  feature: string;
  recommendation_id: string;
  ai_output: Record<string, unknown>;
  decision: AIDecisionAction;
  reason: string | null;
  outcome: string | null;
}

export interface CreateAIDecisionBody {
  feature: string;
  recommendation_id: string;
  ai_output: Record<string, unknown>;
  decision: AIDecisionAction;
  reason?: string;
}

export interface ListAIDecisionsParams {
  feature?: string;
  decision?: AIDecisionAction;
  limit?: number;
}

/** Record an HR admin's accept / override / reject on an AI recommendation. */
export const createAIDecision = (body: CreateAIDecisionBody): Promise<AIDecisionRecord> =>
  apiPost<AIDecisionRecord>('/api/ai/decisions', body);

/** List AI decisions for the caller's company, newest first. */
export const listAIDecisions = (params: ListAIDecisionsParams = {}): Promise<AIDecisionRecord[]> => {
  const qs = new URLSearchParams();
  if (params.feature) qs.set('feature', params.feature);
  if (params.decision) qs.set('decision', params.decision);
  if (params.limit) qs.set('limit', String(params.limit));
  const query = qs.toString();
  return apiGet<AIDecisionRecord[]>(`/api/ai/decisions${query ? `?${query}` : ''}`);
};

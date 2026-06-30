import { apiPost } from './client';

/**
 * Assistant domain routing (policy bridge). Calls the canonical backend router
 * (/api/assistant/route) so routing logic has a single, eval-measured source of
 * truth instead of a duplicated frontend lexicon. Returns immigration | policy |
 * ambiguous; callers treat any failure as 'ambiguous' (→ the clarifier).
 */
export type AssistantDomain = 'immigration' | 'policy' | 'ambiguous';

interface RouteResponse {
  domain: AssistantDomain;
  immigration_score?: number;
  policy_score?: number;
}

export async function routeAssistantDomain(question: string): Promise<AssistantDomain> {
  const res = await apiPost<RouteResponse>('/api/assistant/route', { question });
  return res.domain;
}

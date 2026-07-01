import { apiPost } from './client';
import { ragResponseToAnswer, type RagQueryResponse } from './policyAssistantRagAdapter';
import type { PolicyAssistantAnswer } from '../types/policyAssistant';

/**
 * Thin wrapper over the company-policy RAG endpoint for the unified relocation
 * assistant (Slice 5). Company scoping is server-derived from the auth token;
 * the body is just `{ question }`. Returns the adapted PolicyAssistantAnswer so
 * the assistant can render a grounded, cited, refusal-capable policy answer.
 */
export async function getPolicyAnswer(question: string): Promise<PolicyAssistantAnswer> {
  const res = await apiPost<RagQueryResponse>('/api/policy-assistant/rag-query', { question });
  return ragResponseToAnswer(res, 'employee');
}

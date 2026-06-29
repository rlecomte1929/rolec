import { apiPost } from './client';

/**
 * Employee-facing grounded immigration Q&A (N4/AIQ-843 backend).
 * POST /api/immigration/answer — corridor-scoped, citation-enforced answer.
 * Every response carries a `trace_id` used for verdict feedback (AIQ-856).
 */
export interface ImmigrationAnswerRequest {
  corridor_from: string;
  corridor_to: string;
  nationality: string;
  permit_type: string;
  is_eea?: boolean | null;
  query: string;
  top_k?: number;
}

export interface CitedSource {
  source_url: string;
  title?: string | null;
  fetched_at?: string | null;
  is_stale?: boolean | null;
  [key: string]: unknown;
}

export interface ImmigrationAnswer {
  answer_text: string;
  /** 'answer' | 'refusal_insufficient_context' | ... */
  answer_kind: string;
  cited_sources: CitedSource[];
  confidence?: string | null;
  all_stale_warning?: boolean;
  oldest_fetched_at?: string | null;
  grounding_verdict?: string | null;
  corridor?: string | null;
  trace_id: string;
}

export async function askImmigrationQuestion(
  body: ImmigrationAnswerRequest,
): Promise<ImmigrationAnswer> {
  return apiPost<ImmigrationAnswer>('/api/immigration/answer', body);
}

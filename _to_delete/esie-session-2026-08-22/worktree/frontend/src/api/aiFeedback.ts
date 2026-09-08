import { apiPost } from './client';

/**
 * Human verdict on an AI answer → ai_human_feedback (AIQ-856 producer side).
 * POST /api/ai/feedback. Thumbs-up → 'approved', thumbs-down → 'rejected'.
 * Idempotent server-side per (trace_session_id, reviewer).
 */
export type FeedbackVerdict = 'approved' | 'rejected' | 'edited';

export interface AiFeedbackInput {
  trace_session_id: string;
  verdict: FeedbackVerdict;
  comment?: string;
}

export async function submitAiFeedback(
  input: AiFeedbackInput,
): Promise<{ id?: string; verdict?: string }> {
  return apiPost('/api/ai/feedback', input);
}

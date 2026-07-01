/**
 * End-user helpfulness vote for policy-assistant answers.
 * Calls POST /api/policy-assistant/helpfulness.
 */
import api from './client';

export async function submitHelpfulness(
  traceSessionId: string,
  helpful: boolean,
  comment?: string,
): Promise<void> {
  await api.post('/api/policy-assistant/helpfulness', {
    trace_session_id: traceSessionId,
    helpful,
    comment,
  });
}

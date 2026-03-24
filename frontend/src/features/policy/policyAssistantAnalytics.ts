import { apiPost } from '../../api/client';

/** Fire-and-forget: follow-up chip from a policy assistant answer (no question text). */
export function trackPolicyAssistantFollowUpClicked(payload: {
  follow_up_intent?: string | null;
  follow_up_index: number;
  canonical_topic?: string | null;
  /** Matches ``request_id`` from the policy assistant query response for this answer card. */
  assistant_turn_request_id?: string | null;
}): void {
  void apiPost<{ ok: boolean }>('/api/policy-assistant/analytics/beacon', {
    event: 'assistant_follow_up_clicked',
    follow_up_intent: payload.follow_up_intent ?? undefined,
    follow_up_index: payload.follow_up_index,
    canonical_topic: payload.canonical_topic ?? undefined,
    assistant_turn_request_id: payload.assistant_turn_request_id ?? undefined,
  }).catch(() => {
    /* non-fatal */
  });
}

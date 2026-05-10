import { apiPost } from '../../api/client';

/**
 * Surface that fired the event. Lets us slice opens / submits / answers /
 * dismissals by mount point (FAB on employee pages vs HR sidesheet vs
 * legacy in-page card).
 */
export type PolicyAssistantSurface = 'employee_fab' | 'hr_sidesheet' | 'employee_card';

/** What initiated a question submission. */
export type PolicyAssistantQuestionSource = 'free_text' | 'shortcut' | 'follow_up';

/** Internal helper — every analytics call goes through this. */
function emit(payload: Record<string, unknown>): void {
  void apiPost<{ ok: boolean }>('/api/policy-assistant/analytics/beacon', payload).catch(() => {
    /* non-fatal — analytics must never throw or block the UI */
  });
}

/** Fire-and-forget: follow-up chip from a policy assistant answer (no question text). */
export function trackPolicyAssistantFollowUpClicked(payload: {
  follow_up_intent?: string | null;
  follow_up_index: number;
  canonical_topic?: string | null;
  /** Matches ``request_id`` from the policy assistant query response for this answer card. */
  assistant_turn_request_id?: string | null;
}): void {
  emit({
    event: 'assistant_follow_up_clicked',
    follow_up_intent: payload.follow_up_intent ?? undefined,
    follow_up_index: payload.follow_up_index,
    canonical_topic: payload.canonical_topic ?? undefined,
    assistant_turn_request_id: payload.assistant_turn_request_id ?? undefined,
  });
}

/** Fire when the assistant sheet/panel becomes visible to the user. */
export function trackPolicyAssistantOpened(payload: {
  surface: PolicyAssistantSurface;
}): void {
  emit({
    event: 'assistant_opened',
    surface: payload.surface,
  });
}

/** Fire just before the question hits the API. `source` distinguishes
 *  typed input from shortcut click from follow-up chip click. */
export function trackPolicyAssistantQuestionSubmitted(payload: {
  surface: PolicyAssistantSurface;
  source: PolicyAssistantQuestionSource;
}): void {
  emit({
    event: 'assistant_question_submitted',
    surface: payload.surface,
    source: payload.source,
  });
}

/** Fire when an answer comes back. `status` is the derived support
 *  status (answered / clarification / refused …) so we can track
 *  refusal and clarification rates per surface. */
export function trackPolicyAssistantAnswerReceived(payload: {
  surface: PolicyAssistantSurface;
  answer_type: string | null | undefined;
  status: string;
  request_id: string | null | undefined;
}): void {
  emit({
    event: 'assistant_answer_received',
    surface: payload.surface,
    answer_type: payload.answer_type ?? undefined,
    status: payload.status,
    request_id: payload.request_id ?? undefined,
  });
}

/** Fire when the user closes the assistant. The booleans capture
 *  whether they typed anything and whether they got at least one
 *  answer before closing — useful for "abandoned without answer" rates. */
export function trackPolicyAssistantDismissed(payload: {
  surface: PolicyAssistantSurface;
  had_question: boolean;
  had_answer: boolean;
}): void {
  emit({
    event: 'assistant_dismissed',
    surface: payload.surface,
    had_question: payload.had_question,
    had_answer: payload.had_answer,
  });
}

import { apiGet, apiPost, apiPatch } from './client';

export type FeedbackStream =
  | 'product'
  | 'ai_answers'
  | 'helpfulness'
  | 'hr_assignment'
  | 'hr_case';
export type TriageStatus = 'new' | 'reviewed' | 'acted_on' | 'closed';
export type DispatchStatus = 'pending' | 'dispatched' | 'failed';

export interface UnifiedFeedbackItem {
  id: string;
  stream: FeedbackStream;
  source_ref: string | null;
  text: string | null;
  verdict: string | null;
  user_id: string | null;
  company_id: string | null;
  created_at: string;
  status: TriageStatus | null;
  owner: string | null;
  resolution: string | null;
  /** BR-2 / D1: triage classifier + dispatch fields */
  severity?: string | null;
  area?: string | null;
  dispatch_status?: DispatchStatus | null;
  dispatch_ref?: string | null;
}

export interface DispatchResult {
  dispatched: boolean;
  dispatch_ref: string;
  status: string;
}

export async function listFeedback(params?: {
  stream?: FeedbackStream;
  status?: TriageStatus;
  since?: string;
  /** D1: when true, sends ?dispatched=true — returns only dispatched tickets */
  dispatched?: boolean;
}): Promise<UnifiedFeedbackItem[]> {
  const qs = new URLSearchParams();
  if (params?.stream) qs.set('stream', params.stream);
  if (params?.status) qs.set('status', params.status);
  if (params?.since) qs.set('since', params.since);
  if (params?.dispatched !== undefined) qs.set('dispatched', String(params.dispatched));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const data = await apiGet<{ items: UnifiedFeedbackItem[] }>(`/api/admin/feedback${suffix}`);
  return data.items ?? [];
}

export async function triageFeedback(
  stream: FeedbackStream,
  id: string,
  update: { status: TriageStatus; owner?: string; resolution?: string }
): Promise<void> {
  await apiPatch<unknown>(`/api/admin/feedback/${stream}/${id}`, update);
}

/**
 * Dispatch a feedback ticket to the engineering queue.
 * High-risk tickets (severity==='critical' OR area==='isolation') require confirm:true
 * or the backend returns 400.
 */
export async function dispatchTicket(
  stream: FeedbackStream,
  itemId: string,
  confirm?: boolean,
  note?: string,
): Promise<DispatchResult> {
  const body: Record<string, unknown> = {};
  if (confirm !== undefined) body.confirm = confirm;
  if (note !== undefined) body.note = note;
  return apiPost<DispatchResult>(`/api/admin/feedback/${stream}/${itemId}/dispatch`, body);
}

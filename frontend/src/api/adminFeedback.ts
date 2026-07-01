import axios from 'axios';

const API = import.meta.env.VITE_API_URL ?? '';

export type FeedbackStream = 'product' | 'ai_answers' | 'helpfulness';
export type TriageStatus = 'new' | 'reviewed' | 'acted_on' | 'closed';

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
}

export async function listFeedback(params?: {
  stream?: FeedbackStream;
  status?: TriageStatus;
  since?: string;
}): Promise<UnifiedFeedbackItem[]> {
  const { data } = await axios.get<{ items: UnifiedFeedbackItem[] }>(
    `${API}/api/admin/feedback`,
    { params }
  );
  return data.items;
}

export async function triageFeedback(
  stream: FeedbackStream,
  id: string,
  update: { status: TriageStatus; owner?: string; resolution?: string }
): Promise<void> {
  await axios.patch(`${API}/api/admin/feedback/${stream}/${id}`, update);
}

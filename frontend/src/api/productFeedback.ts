import { apiGet, apiPost } from './client';

/**
 * Product "Share feedback" widget submission. Routes through the FastAPI backend
 * (ReloPass session auth) instead of a direct Supabase insert — the widget used
 * to write straight to the `feedback` table, which silently failed for employees
 * without a live Supabase Auth session. The backend writes via the service role
 * and sets user_id, so any authenticated ReloPass user can submit.
 */
export interface ProductFeedbackInput {
  category: 'bug' | 'idea' | 'other';
  message: string;
  page_url: string;
  report_id?: string;
  screenshot_data?: string | null;
}

export async function submitProductFeedback(
  input: ProductFeedbackInput,
): Promise<{ ok: boolean; report_id: string }> {
  return apiPost<{ ok: boolean; report_id: string }>('/api/feedback', input);
}

/** One row returned by GET /api/feedback/mine */
export interface MyReport {
  report_id: string;
  category: string;
  message_excerpt: string;
  status: string | null;
  severity: string | null;
  area: string | null;
  dispatch_status: string | null;
  created_at: string;
}

/**
 * Fetch the authenticated user's own submitted reports.
 * GET /api/feedback/mine → { reports: MyReport[] }
 */
export async function getMyReports(): Promise<{ reports: MyReport[] }> {
  return apiGet<{ reports: MyReport[] }>('/api/feedback/mine');
}

import type { ClientContext } from '../lib/diagnostics';
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
  // TD-9: campaign slice stamped during a test-drive session (else omitted).
  campaign?: string;
  corridor_id?: string;
  tester_segment?: string;
  // Diagnostics snapshot (page, failing function, recent failed requests, breadcrumbs,
  // viewport, app version) auto-attached by the widget for the admin Diagnostics panel.
  client_context?: ClientContext;
}

/** Screenshot-bucket usage returned after a submit that stored a screenshot (AIQ-1480). */
export interface ScreenshotStorage {
  used_mb: number;
  budget_mb: number;
  remaining_mb: number;
}

export async function submitProductFeedback(
  input: ProductFeedbackInput,
): Promise<{ ok: boolean; report_id: string; screenshot_storage?: ScreenshotStorage }> {
  return apiPost<{ ok: boolean; report_id: string; screenshot_storage?: ScreenshotStorage }>(
    '/api/feedback', input,
  );
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

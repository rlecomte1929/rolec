import type { ClientContext } from '../lib/diagnostics';
import { apiGet, apiPost, apiPatch, apiPut, apiDelete } from './client';

export type FeedbackStream =
  | 'product'
  | 'ai_answers'
  | 'helpfulness'
  | 'hr_assignment'
  | 'hr_case';
export type TriageStatus = 'new' | 'reviewed' | 'acted_on' | 'closed';
export type DispatchStatus =
  | 'new' | 'triaged' | 'spec_drafted' | 'dispatched' | 'in_progress'
  | 'in_review' | 'deployed' | 'done' | 'verify_failed' | 'dismissed' | 'wont_fix'
  | 'pending' | 'failed'; // legacy, tolerated on read
export type AutonomyTier = 'green' | 'yellow' | 'red';

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
  /** Reporter identity — snapshot at submit (product) or resolved from profiles. */
  reporter_name?: string | null;
  reporter_email?: string | null;
  reporter_role?: string | null;
  /** BR-2 / D1: triage classifier + dispatch fields */
  severity?: string | null;
  area?: string | null;
  dispatch_status?: DispatchStatus | null;
  dispatch_ref?: string | null;
  /** Manual-lane risk tier computed at dispatch (Task 2) — drives the ProgressStrip badge. */
  autonomy_tier?: AutonomyTier | null;
  /** Admin-authored context used to engineer the dispatched task. */
  dispatch_context?: string | null;
  /** Soft-dismissed (hidden from the default list). Serialized 0/1 — read via truthiness. */
  dismissed?: boolean;
  /** True when this item has a screenshot attached (product stream only). The
   *  image itself is fetched lazily via getFeedbackScreenshot to keep the list
   *  payload small. Serialized as 0/1 by the backend — read via truthiness. */
  has_screenshot?: boolean;
  /** Diagnostics snapshot captured by the widget at submit (product stream only):
   *  page/route, failing function, recent failed requests + correlation id, breadcrumbs,
   *  viewport, app version. Null for other streams / older rows. */
  client_context?: ClientContext | null;
}

export interface DispatchResult {
  dispatched: boolean;
  dispatch_ref: string;
  status: string;
}

/** AIQ-1492 — admin authors a new product-stream feedback item, dispatch-ready. */
export interface NewFeedbackInput {
  page_url: string;
  category: 'bug' | 'idea' | 'other';
  message: string;
  dispatch_context: string;              // required — makes it immediately dispatchable
  severity?: string | null;
  area?: string | null;
  screenshot_data?: string | null;       // base64 data-URL (optional)
  reporter_name?: string | null;
  reporter_email?: string | null;
  reporter_role?: string | null;
  client_context?: Record<string, unknown> | null;  // steps_to_reproduce, expected, actual, persona, …
}

export async function createAdminFeedback(
  input: NewFeedbackInput,
): Promise<{ id: string; report_id: string }> {
  return apiPost<{ id: string; report_id: string }>('/api/admin/feedback', input);
}

export async function listFeedback(params?: {
  stream?: FeedbackStream;
  status?: TriageStatus;
  since?: string;
  /** D1: when true, sends ?dispatched=true — returns only dispatched tickets */
  dispatched?: boolean;
  /** When true, also returns soft-dismissed rows (flagged with dismissed=true). */
  includeDismissed?: boolean;
}): Promise<UnifiedFeedbackItem[]> {
  const qs = new URLSearchParams();
  if (params?.stream) qs.set('stream', params.stream);
  if (params?.status) qs.set('status', params.status);
  if (params?.since) qs.set('since', params.since);
  if (params?.dispatched !== undefined) qs.set('dispatched', String(params.dispatched));
  if (params?.includeDismissed) qs.set('include_dismissed', 'true');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const data = await apiGet<{ items: UnifiedFeedbackItem[] }>(`/api/admin/feedback${suffix}`);
  // has_screenshot / dismissed are serialized 0/1 — coerce to real booleans so JSX
  // `{row.x && …}` never renders a stray "0".
  return (data.items ?? []).map((it) => ({
    ...it,
    has_screenshot: Boolean(it.has_screenshot),
    dismissed: Boolean(it.dismissed),
  }));
}

/**
 * Fetch a renderable screenshot src for a single feedback item, on demand.
 * Storage-backed screenshots (AIQ-1480) resolve to a short-lived signed URL; older ones
 * to an inline base64 data URL. Only the `product` stream carries screenshots.
 * Called lazily when an admin expands a row (keeps the list response small).
 */
export async function getFeedbackScreenshot(
  stream: FeedbackStream,
  id: string,
): Promise<string | null> {
  const data = await apiGet<{ screenshot_data: string | null; screenshot_url?: string | null }>(
    `/api/admin/feedback/${stream}/${id}/screenshot`,
  );
  return data.screenshot_url ?? data.screenshot_data ?? null;
}

export async function triageFeedback(
  stream: FeedbackStream,
  id: string,
  update: { status: TriageStatus; owner?: string; resolution?: string }
): Promise<void> {
  await apiPatch<unknown>(`/api/admin/feedback/${stream}/${id}`, update);
}

/**
 * Manually advance (or reject) a feedback item's pipeline `dispatch_status`.
 * The backend validates the transition against the state machine — 409 on an
 * illegal transition, 422 on an unknown target state.
 */
export async function advanceState(
  stream: FeedbackStream,
  id: string,
  target: DispatchStatus,
): Promise<{ ok: boolean; dispatch_status: DispatchStatus }> {
  return apiPatch<{ ok: boolean; dispatch_status: DispatchStatus }>(
    `/api/admin/feedback/${stream}/${id}/state`,
    { target },
  );
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

// ── Dispatch → AI Work Queue (context → engineered task → Notion) ─────────────

/** The engineered task an admin reviews/edits before it becomes a Notion page. */
export interface EngineeredTask {
  title: string;
  strategic_objective: string;
  execution_prompt: string;
  expected_output: string;
  validation_criteria: string;
  test_command?: string;
  technical_constraints?: string;
  files_to_touch?: string;
  risk_rollback?: string;
  priority: string;
  complexity: string;
  task_type: string;
  layer: string;
  product_area: string;
  status: string;
}

/** Save the admin's per-item dispatch context (required before dispatch). */
export async function saveDispatchContext(
  stream: FeedbackStream,
  itemId: string,
  context: string,
): Promise<void> {
  await apiPut<unknown>(`/api/admin/feedback/${stream}/${itemId}/context`, { context });
}

/** Generate (no side effects) an engineered AI Work Queue task for review.
 *
 * The backend caps at 55 s (single attempt, no retries). We add a 65 s client-side
 * AbortController so the UI receives a clear "timed out" message rather than the
 * generic "Unable to reach the server" that raw fetch throws on a dropped connection.
 */
export async function dispatchPreview(
  stream: FeedbackStream,
  itemId: string,
  input: { text?: string | null; category?: string },
): Promise<EngineeredTask> {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 65_000);
  try {
    const data = await apiPost<{ task: EngineeredTask }>(
      `/api/admin/feedback/${stream}/${itemId}/dispatch/preview`,
      { text: input.text ?? '', category: input.category ?? 'bug' },
      { signal: ac.signal },
    );
    return data.task;
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Task spec generation timed out — please try again.');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/** Create the Notion AI Work Queue page from the reviewed task; returns its URL. */
export async function dispatchCreate(
  stream: FeedbackStream,
  itemId: string,
  task: EngineeredTask,
): Promise<{ dispatched: boolean; url: string; dispatch_ref: string; notion_url?: string; already_exists?: boolean }> {
  return apiPost(`/api/admin/feedback/${stream}/${itemId}/dispatch/create`, { task, confirm: true });
}

// ── Trigger fix (skill handoff) + Auto-attempt (autofix pipeline) ─────────────

/** Result of Trigger fix — the exact skill command to run in Claude Code. */
export interface FixTriggerResult {
  triggered: boolean;
  skill: string;
  command: string;
  routes_to: string;
  aiq_id: string | null;
  url: string | null;
}

/**
 * Mark a dispatched task 'Ready for AI' and return the /relopass-dev-queue command.
 * The button hands off to the skill; it does not run any code itself.
 */
export async function triggerFix(
  stream: FeedbackStream,
  itemId: string,
): Promise<FixTriggerResult> {
  return apiPost<FixTriggerResult>(`/api/admin/feedback/${stream}/${itemId}/fix`, {});
}

/** Fire the autofix pipeline for this one dispatched task (Trivial/Low, non-Red only). */
export async function autoAttempt(
  stream: FeedbackStream,
  itemId: string,
): Promise<{ status: string; url: string | null }> {
  return apiPost(`/api/admin/feedback/${stream}/${itemId}/auto-attempt`, {});
}

// ── Manage: dismiss (hide, reversible) + delete (product only) ────────────────

/** Soft-dismiss (hide) or restore a feedback row. Works for every stream. */
export async function dismissFeedback(
  stream: FeedbackStream,
  itemId: string,
  dismissed: boolean,
): Promise<void> {
  await apiPost<unknown>(`/api/admin/feedback/${stream}/${itemId}/dismiss`, { dismissed });
}

/** Permanently delete a PRODUCT feedback row (widget bug/idea/other). */
export async function deleteFeedback(itemId: string): Promise<void> {
  await apiDelete<unknown>(`/api/admin/feedback/product/${itemId}`);
}

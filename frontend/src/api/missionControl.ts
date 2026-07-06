import { apiGet, apiPost, apiPatch } from './client';

/**
 * Mission Control P1 — the demands console API. Reads the canonical work_items
 * store + runs ingestion/triage. Admin-only (server-enforced). No execution here.
 */
export interface WorkItem {
  id: string;
  source: string;
  source_url?: string | null;
  kind: string;
  title: string;
  body?: string | null;
  reporter_role?: string | null;
  company_id?: string | null;
  status: string;
  priority: string;
  complexity?: string | null;
  auto_fixable: boolean;
  triage_json?: { rationale?: string; blocked?: boolean } | null;
  plan_json?: WorkItemPlan | null;
  dedupe_key?: string | null;
  pr_url?: string | null;
  created_at?: string;
}

export interface WorkItemPlan {
  summary?: string;
  affected_files?: string[];
  approach?: string;
  test_plan?: string;
  risk?: string;
  confidence?: string;
  approved?: boolean;
}

export interface WorkItemsResponse {
  items: WorkItem[];
  table_ready: boolean;
}

export async function listWorkItems(
  params: { status?: string; kind?: string; priority?: string } = {},
): Promise<WorkItemsResponse> {
  const q = new URLSearchParams();
  if (params.status) q.set('status', params.status);
  if (params.kind) q.set('kind', params.kind);
  if (params.priority) q.set('priority', params.priority);
  const qs = q.toString();
  return apiGet<WorkItemsResponse>(`/api/admin/work-items${qs ? `?${qs}` : ''}`);
}

export async function syncWorkItems(): Promise<{ ok: boolean; inserted?: number; table_ready?: boolean }> {
  return apiPost('/api/admin/work-items/sync', {});
}

export async function retriageWorkItem(id: string): Promise<{ ok: boolean }> {
  return apiPost(`/api/admin/work-items/${encodeURIComponent(id)}/triage`, {});
}

export async function patchWorkItem(
  id: string,
  body: { status?: string; priority?: string; assignee?: string; notes?: string },
): Promise<{ ok: boolean }> {
  return apiPatch(`/api/admin/work-items/${encodeURIComponent(id)}`, body);
}

/**
 * P2 — launch the autofix agent for one agent-eligible demand. Server-gated
 * (admin + feature flag + auto_fixable + not blocked); opens a draft PR.
 */
export async function dispatchWorkItem(id: string): Promise<{ ok: boolean; run_id?: string; pr_url?: string | null }> {
  return apiPost(`/api/admin/work-items/${encodeURIComponent(id)}/dispatch`, {});
}

/**
 * Draft a fully-engineered task into the Notion AI Work Queue — the single dispatch
 * engine shared with the feedback inbox. Runs an LLM + Notion call server-side.
 */
export async function dispatchWorkItemToNotion(
  id: string,
): Promise<{ ok: boolean; url: string; dispatch_ref: string }> {
  return apiPost(`/api/admin/work-items/${encodeURIComponent(id)}/dispatch-notion`, {});
}

/** P3 — draft a structured plan for a demand (LLM, PII-masked). */
export async function planWorkItem(id: string): Promise<{ ok: boolean; plan: WorkItemPlan }> {
  return apiPost(`/api/admin/work-items/${encodeURIComponent(id)}/plan`, {});
}

/** P3 — mark the drafted plan approved. */
export async function approvePlan(id: string): Promise<{ ok: boolean; approved: boolean }> {
  return apiPost(`/api/admin/work-items/${encodeURIComponent(id)}/plan/approve`, {});
}

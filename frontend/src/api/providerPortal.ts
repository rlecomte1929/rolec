/**
 * providerPortal.ts — API client for the external provider portal.
 *
 * Uses a separate axios instance that injects the provider JWT as the
 * Bearer token. The token comes from the magic link (?token=...) and is
 * stored in sessionStorage for the lifetime of the portal session.
 *
 * All calls go to the backend /api/provider/* routes; Supabase RLS and
 * provider_jwt.py handle isolation — no service-role key used client-side.
 */

import axios from 'axios';

// ── Token management ──────────────────────────────────────────────────────────

const PORTAL_TOKEN_KEY = 'relopass_provider_token';

export function storeProviderToken(token: string): void {
  sessionStorage.setItem(PORTAL_TOKEN_KEY, token);
}

export function getStoredProviderToken(): string | null {
  return sessionStorage.getItem(PORTAL_TOKEN_KEY);
}

export function clearProviderToken(): void {
  sessionStorage.removeItem(PORTAL_TOKEN_KEY);
}

// ── Axios instance ────────────────────────────────────────────────────────────

function createPortalClient(token: string) {
  return axios.create({
    baseURL: (import.meta as unknown as { env: Record<string, string> }).env.VITE_API_BASE_URL ?? '',
    headers: { Authorization: `Bearer ${token}` },
    timeout: 15_000,
  });
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PortalTask {
  id: string;
  case_id: string;
  title: string;
  description: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  due_date: string | null;
  provider_note: string | null;
  billable_amount: number | null;
  hr_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortalTasksResponse {
  tasks: PortalTask[];
  provider_name: string | null;
  case_id: string;
}

export interface CaseSummary {
  case_id: string;
  budget_cap: number | null;
  currency: string;
  tasks_total: number;
  tasks_completed: number;
  total_billable: number | null;
}

export interface ProviderProfile {
  provider_id: string;
  name: string;
  display_name: string | null;
  company_name: string | null;
  email: string | null;
  onboarded: boolean;
}

export interface TokenVerifyResult {
  valid: boolean;
  provider_id?: string;
  org_id?: string;
  case_id?: string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

/** Verify token via backend — public, no auth needed. */
export async function verifyProviderToken(token: string): Promise<TokenVerifyResult> {
  // Uses the public HR-side verify endpoint (no portal client needed)
  const base = (import.meta as unknown as { env: Record<string, string> }).env.VITE_API_BASE_URL ?? '';
  const r = await axios.get<TokenVerifyResult>(`${base}/api/provider/auth/verify`, {
    params: { token },
    timeout: 10_000,
  });
  return r.data;
}

/** Get tasks for the authenticated provider. */
export async function getPortalTasks(token: string): Promise<PortalTasksResponse> {
  const r = await createPortalClient(token).get<PortalTasksResponse>('/api/provider/tasks');
  return r.data;
}

/** Update a task (status / provider_note / billable_amount). */
export async function patchPortalTask(
  token: string,
  taskId: string,
  updates: {
    status?: PortalTask['status'];
    provider_note?: string;
    billable_amount?: number;
  }
): Promise<PortalTask> {
  const r = await createPortalClient(token).patch<PortalTask>(
    `/api/provider/tasks/${taskId}`,
    updates
  );
  return r.data;
}

/** Get case financial summary. */
export async function getPortalCaseSummary(token: string): Promise<CaseSummary> {
  const r = await createPortalClient(token).get<CaseSummary>('/api/provider/case-summary');
  return r.data;
}

/** Update provider display name / company name (onboarding). */
export async function updatePortalProfile(
  token: string,
  payload: { display_name?: string; company_name?: string }
): Promise<ProviderProfile> {
  const r = await createPortalClient(token).patch<ProviderProfile>('/api/provider/profile', payload);
  return r.data;
}

/**
 * providers.ts — Typed API client for provider coordination.
 *
 * All HR routes require an active Supabase session (Bearer token injected
 * automatically by the Axios interceptor in client.ts).
 */

import api from './client';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ProviderItem {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  service_type: string | null;
  notes: string | null;
  created_at: string;
}

export interface ProviderTaskItem {
  id: string;
  case_id: string;
  provider_id: string;
  provider_name: string | null;
  title: string;
  description: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  due_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface InviteProviderResponse {
  invite_id: string;
  email: string;
  expires_at: string;
  magic_link?: string | null;
}

// ── Provider endpoints ────────────────────────────────────────────────────────

/** List all providers registered for the caller's org (no case filter). */
export async function listOrgProviders(): Promise<ProviderItem[]> {
  const r = await api.get<{ providers: ProviderItem[] }>('/api/hr/providers/org');
  return r.data.providers ?? [];
}

/** List providers linked to a specific case (falls back to all org providers). */
export async function listCaseProviders(caseId: string): Promise<ProviderItem[]> {
  const r = await api.get<{ providers: ProviderItem[] }>('/api/hr/providers', {
    params: { case_id: caseId },
  });
  return r.data.providers ?? [];
}

/** Create a new provider in the caller's org. */
export async function createProvider(payload: {
  name: string;
  email?: string;
  phone?: string;
  service_type?: string;
  notes?: string;
}): Promise<ProviderItem> {
  const r = await api.post<ProviderItem>('/api/hr/providers', payload);
  return r.data;
}

/** Invite an existing provider to a case via magic link. */
export async function inviteProvider(payload: {
  provider_id: string;
  email: string;
  case_id: string;
}): Promise<InviteProviderResponse> {
  const r = await api.post<InviteProviderResponse>('/api/hr/providers/invite', payload);
  return r.data;
}

// ── Provider task endpoints ───────────────────────────────────────────────────

/** List all provider tasks for a case. */
export async function listProviderTasks(
  caseId: string,
  opts?: { signal?: AbortSignal }
): Promise<ProviderTaskItem[]> {
  const r = await api.get<{ tasks: ProviderTaskItem[] }>('/api/hr/provider-tasks', {
    params: { case_id: caseId },
    signal: opts?.signal,
  });
  return r.data.tasks ?? [];
}

/** Create a task and assign it to a provider. */
export async function createProviderTask(payload: {
  case_id: string;
  provider_id: string;
  title: string;
  description?: string;
  due_date?: string;
  notes?: string;
}): Promise<ProviderTaskItem> {
  const r = await api.post<ProviderTaskItem>('/api/hr/provider-tasks', payload);
  return r.data;
}

/** Update status / fields of a provider task. */
export async function patchProviderTask(
  taskId: string,
  updates: {
    status?: 'pending' | 'in_progress' | 'completed' | 'blocked';
    title?: string;
    description?: string;
    due_date?: string;
    notes?: string;
  }
): Promise<ProviderTaskItem> {
  const r = await api.patch<ProviderTaskItem>(`/api/hr/provider-tasks/${taskId}`, updates);
  return r.data;
}

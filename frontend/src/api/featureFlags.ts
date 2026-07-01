import { apiDelete, apiGet, apiPatch, apiPost } from './client';

/** Admin feature-flag console (DB-backed flags, no redeploy to toggle). */

export interface FeatureFlagRow {
  key: string;
  enabled: boolean;
  description?: string | null;
  account_count: number;
  updated_at?: string | null;
}

export async function listFeatureFlags(): Promise<{ items: FeatureFlagRow[] }> {
  return apiGet<{ items: FeatureFlagRow[] }>('/api/admin/feature-flags');
}

export async function upsertFeatureFlag(body: { key: string; enabled?: boolean; description?: string }): Promise<{ ok: boolean; key: string }> {
  return apiPost<{ ok: boolean; key: string }>('/api/admin/feature-flags', body);
}

export async function patchFeatureFlag(key: string, body: { enabled?: boolean; description?: string }): Promise<{ ok: boolean }> {
  return apiPatch<{ ok: boolean }>(`/api/admin/feature-flags/${encodeURIComponent(key)}`, body);
}

export async function addFlagAccount(key: string, accountId: string): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>(`/api/admin/feature-flags/${encodeURIComponent(key)}/accounts`, { account_id: accountId });
}

export async function removeFlagAccount(key: string, accountId: string): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`/api/admin/feature-flags/${encodeURIComponent(key)}/accounts/${encodeURIComponent(accountId)}`);
}

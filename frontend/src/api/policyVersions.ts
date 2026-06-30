import { apiGet, apiPost } from './client';

/**
 * Admin policy-version browse + rollback. Rollback reuses the existing publish path
 * (`POST /api/policy/publish` with an older version_id) — admins bypass the
 * cross-company guard, so re-publishing an older version IS the rollback.
 */

export interface PolicyVersion {
  id: string;
  policy_id: string;
  version_number: number;
  status: string;
  effective_date?: string | null;
  expiry_date?: string | null;
  published_by?: string | null;
  published_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CompanyOption {
  id: string;
  name: string;
}

function str(v: unknown): string {
  return typeof v === 'string' ? v : typeof v === 'number' ? String(v) : '';
}

export async function listCompaniesForVersions(): Promise<CompanyOption[]> {
  const raw = await apiGet<unknown>('/api/admin/companies');
  const arr = Array.isArray(raw) ? raw : ((raw as { items?: unknown[] })?.items ?? []);
  return (arr as Array<Record<string, unknown>>).map((c) => {
    const id = str(c.id) || str(c.company_id);
    return { id, name: str(c.name) || str(c.company_name) || id || 'Company' };
  }).filter((c) => c.id);
}

export async function listPolicyVersions(companyId: string): Promise<PolicyVersion[]> {
  return apiGet<PolicyVersion[]>(`/api/policy/versions/${encodeURIComponent(companyId)}`);
}

export async function getActivePolicyVersion(companyId: string): Promise<PolicyVersion | null> {
  return apiGet<PolicyVersion | null>(`/api/policy/active/${encodeURIComponent(companyId)}`);
}

/** Rollback = re-publish an older version (today's effective date). */
export async function rollbackToVersion(versionId: string, notes?: string): Promise<unknown> {
  const today = new Date().toISOString().slice(0, 10);
  return apiPost('/api/policy/publish', { version_id: versionId, effective_date: today, notes });
}

import { apiDelete, apiGet, apiPost } from './client';

/** Admin-allowlist + audit-trail (admin-only governance console). */

export interface AllowlistEntry {
  email: string;
  enabled?: number;
  added_by_user_id?: string | null;
  user_id?: string | null;
  created_at?: string;
}

export interface AuditLogRow {
  id: string;
  entity_type: string;
  entity_id: string;
  action_type: string;
  event?: string | null;
  actor_type?: string | null;
  actor_id?: string | null;
  actor_name?: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogRow[];
  total: number;
  limit: number;
  offset: number;
  table_ready?: boolean;
}

export interface AuditLogQuery {
  entity_type?: string;
  action_type?: string;
  event?: string;
  actor_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listAllowlist(): Promise<{ items: AllowlistEntry[] }> {
  return apiGet<{ items: AllowlistEntry[] }>('/api/admin/allowlist');
}

export async function grantAdmin(email: string): Promise<{ ok: boolean; email: string }> {
  return apiPost<{ ok: boolean; email: string }>('/api/admin/allowlist', { email });
}

export async function revokeAdmin(email: string): Promise<{ ok: boolean; email: string }> {
  return apiDelete<{ ok: boolean; email: string }>(`/api/admin/allowlist/${encodeURIComponent(email)}`);
}

export async function listAuditLogs(q: AuditLogQuery = {}): Promise<AuditLogPage> {
  const params = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  });
  const qs = params.toString();
  return apiGet<AuditLogPage>(`/api/admin/audit-logs${qs ? `?${qs}` : ''}`);
}

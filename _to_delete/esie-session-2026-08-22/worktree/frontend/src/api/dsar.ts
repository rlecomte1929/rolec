import { apiDelete, apiGet, apiPatch } from './client';

/** Admin GDPR/DSAR desk. List reuses the new cross-tenant registry; export/erase
 *  reuse the existing admin-authorized subject endpoints. */

export interface ErasureRequest {
  id: string;
  case_id?: string | null;
  employee_id?: string | null;
  org_id?: string | null;
  status: string;
  reason?: string | null;
  requested_at?: string | null;
  statutory_due_at?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  completed_at?: string | null;
}

export interface ErasureRequestPage {
  items: ErasureRequest[];
  total: number;
  table_ready?: boolean;
}

export async function listErasureRequests(status?: string): Promise<ErasureRequestPage> {
  const qs = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';
  return apiGet<ErasureRequestPage>(`/api/admin/erasure-requests${qs}`);
}

/** Art.20 portability export (admin-authorized, cross-tenant by user id). */
export async function exportUserData(userId: string): Promise<unknown> {
  return apiGet<unknown>(`/api/users/${encodeURIComponent(userId)}/data-export`);
}

/** Art.17 erasure — permanently deletes/anonymises the subject's data. */
export async function eraseUserData(userId: string): Promise<unknown> {
  return apiDelete<unknown>(`/api/users/${encodeURIComponent(userId)}/data`);
}

export type ErasureAction = 'approve' | 'reject' | 'complete';

/** Transition an erasure request through its review lifecycle (registry state only —
 *  the actual data export/erase runs via export/eraseUserData). */
export async function patchErasureRequest(
  requestId: string,
  action: ErasureAction,
): Promise<{ ok: boolean; item: ErasureRequest | null }> {
  return apiPatch<{ ok: boolean; item: ErasureRequest | null }>(
    `/api/admin/erasure-requests/${encodeURIComponent(requestId)}`,
    { action },
  );
}

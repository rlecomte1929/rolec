// AIQ-1349 P2 — research-request API wrappers.
import { apiGet, apiPost, apiPatch } from './client';

export interface ResearchRequest {
  id: string;
  company_id: string;
  requester_user_id: string;
  origin_country: string | null;
  dest_country: string;
  corridor: string;
  purpose: string | null;
  scope: string | null;
  estimated_cost: number | null;
  actual_cost: number | null;
  status: 'pending' | 'approved' | 'in_progress' | 'completed' | 'rejected';
  created_queue_item_id: string | null;
  result_summary: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** HR/employee: request immigration research for an uncovered corridor.
 *  company_id is resolved server-side from the caller (not sent). */
export const createResearchRequest = (body: {
  dest_country: string;
  origin_country?: string;
  purpose?: string;
  scope?: string;
}): Promise<ResearchRequest> => apiPost('/api/research-requests', body);

/** Admin: list research requests (optionally by status). */
export const listResearchRequests = (status?: string): Promise<ResearchRequest[]> =>
  apiGet(`/api/admin/research-requests${status ? `?status=${encodeURIComponent(status)}` : ''}`);

/** Admin: approve (→ in_progress) or reject a request. */
export const resolveResearchRequest = (
  id: string,
  status: 'approved' | 'rejected',
  notes?: string,
): Promise<ResearchRequest> =>
  apiPatch(`/api/admin/research-requests/${id}`, { status, notes });

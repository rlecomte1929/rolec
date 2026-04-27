/**
 * Admin catalog API client (Phase 2a + 2b-secured).
 * Pairs with backend/app/routers/admin_catalog.py.
 */

import { apiGet, apiPatch, apiPost } from './client';
import type { DestinationRequest } from './hrCatalog';

export type CatalogSource = 'scraper' | 'manual' | 'seed' | 'hr_promoted';

export interface AdminCatalogItem {
  id: string;
  category: string;
  city: string | null;
  country: string | null;
  name: string;
  attributes_json: Record<string, unknown>;
  source: CatalogSource;
  active: boolean;
  external_id: string | null;
  created_at: string;
  updated_at: string;
  created_by_user_id: string | null;
}

export interface AllowlistEntry {
  city: string;
  country: string;
  approved_by: string | null;
  approved_at: string;
  notes: string | null;
}

export const listCatalogItems = (params: {
  category?: string;
  city?: string;
  country?: string;
  source?: CatalogSource;
  active_only?: boolean;
  limit?: number;
} = {}): Promise<AdminCatalogItem[]> => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '') qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return apiGet<AdminCatalogItem[]>(`/api/admin/catalog/items${suffix}`);
};

export const listAllowlist = (): Promise<AllowlistEntry[]> =>
  apiGet('/api/admin/catalog/destinations/allowlist');

export const addAllowlistEntry = (
  city: string,
  country: string,
  notes?: string,
): Promise<AllowlistEntry> =>
  apiPost('/api/admin/catalog/destinations/allowlist', { city, country, notes });

export const listAdminDestinationRequests = (
  status?: 'pending' | 'approved' | 'rejected',
): Promise<DestinationRequest[]> => {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiGet(`/api/admin/catalog/destination-requests${qs}`);
};

export const resolveDestinationRequest = (
  id: string,
  status: 'approved' | 'rejected',
  notes?: string,
): Promise<DestinationRequest> =>
  apiPatch(`/api/admin/catalog/destination-requests/${encodeURIComponent(id)}`, {
    status,
    notes,
  });

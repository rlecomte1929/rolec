/**
 * HR catalog curation API client (Phase 2e).
 * Pairs with backend/app/routers/hr_catalog.py (PR #53).
 */

import { apiDelete, apiGet, apiPost } from './client';

export type CurationKind = 'master' | 'custom';

export interface CurationRow {
  kind: CurationKind;
  selection_id: string | null;
  master_item_id: string | null;
  name: string;
  selected: boolean;
  attributes: Record<string, unknown>;
  source: string | null;
  city: string | null;
  country: string | null;
}

export interface CurationView {
  company_id: string;
  category: string;
  destination_city: string | null;
  rows: CurationRow[];
}

export interface SelectToggle {
  master_item_id: string;
  selected: boolean;
}

export interface BulkSelectBody {
  category: string;
  destination_city?: string | null;
  country?: string | null;
  toggles: SelectToggle[];
}

export interface CustomVendorBody {
  category: string;
  name: string;
  attributes?: Record<string, unknown>;
  destination_city?: string | null;
  country?: string | null;
  display_order?: number;
}

export const getCurationView = (
  category: string,
  destinationCity?: string | null,
): Promise<CurationView> => {
  const qs = new URLSearchParams({ category });
  if (destinationCity) qs.set('destination_city', destinationCity);
  return apiGet<CurationView>(`/api/hr/catalog/curation?${qs.toString()}`);
};

export const bulkSelect = (body: BulkSelectBody): Promise<{ updated: number; rows: unknown[] }> =>
  apiPost('/api/hr/catalog/curation/select', body);

export const addCustomVendor = (body: CustomVendorBody): Promise<unknown> =>
  apiPost('/api/hr/catalog/curation/custom', body);

export const deleteCustomVendor = (rowId: string): Promise<{ deleted: boolean; id: string }> =>
  apiDelete(`/api/hr/catalog/curation/custom/${encodeURIComponent(rowId)}`);

// ---------------------------------------------------------------------------
// Phase 2b-secured: scraper trigger + ticket queue (HR side)
// ---------------------------------------------------------------------------

export interface ScrapeQuotaState {
  day: string;
  used: number;
  limit: number;
  remaining: number;
}

export interface DestinationRequest {
  id: string;
  city: string;
  country: string;
  category: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_by: string;
  company_id: string;
  resolved_by: string | null;
  resolved_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PopulateWithAiResult {
  status: 'completed' | 'pending_admin_approval';
  category?: string;
  destination_city?: string;
  country?: string;
  inserted?: number;
  quota?: ScrapeQuotaState;
  request?: DestinationRequest;
  message?: string;
}

export const populateVendorsWithAi = (
  category: string,
  destinationCity: string,
  country: string,
): Promise<PopulateWithAiResult> =>
  apiPost('/api/hr/catalog/populate-with-ai', {
    category,
    destination_city: destinationCity,
    country,
  });

export const getScrapeQuota = (): Promise<ScrapeQuotaState> =>
  apiGet('/api/hr/catalog/scrape-quota');

export const listMyDestinationRequests = (): Promise<DestinationRequest[]> =>
  apiGet('/api/hr/catalog/destination-requests');

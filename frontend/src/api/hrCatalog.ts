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

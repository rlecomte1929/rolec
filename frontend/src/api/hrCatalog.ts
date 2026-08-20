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
  /**
   * Human-authoritative ReloPass accreditation check. Lifted out of `attributes` by the
   * backend so the UI does not parse a free-form blob. Unverified vendors stay selectable
   * but must be visibly flagged; nothing in the product ever sets this true in code.
   */
  verified: boolean;
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
  /**
   * ISO alpha-2 destination country. Scopes the catalog proposal to that country so a case
   * bound for Ireland is offered Ireland's vendors. Omitted keeps the unscoped behaviour.
   */
  country?: string | null,
): Promise<CurationView> => {
  const qs = new URLSearchParams({ category });
  if (destinationCity) qs.set('destination_city', destinationCity);
  if (country) qs.set('country', country);
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

// HR-readable allowlist (same shape as admin endpoint).
export interface AllowlistedDestination {
  city: string;
  country: string;
  approved_by: string | null;
  approved_at: string;
  notes: string | null;
}

export const listAllowlistedDestinations = (): Promise<AllowlistedDestination[]> =>
  apiGet('/api/hr/catalog/destinations');

// Destination-level scraper trigger — fires across ALL service categories
// for the (city, country) in one HR click.
export interface PopulateDestinationResult {
  status: 'completed' | 'pending_admin_approval';
  destination_city?: string;
  country?: string;
  categories_total?: number;
  categories_populated?: number;
  categories_skipped_existing?: number;
  categories_quota_blocked?: number;
  total_inserted?: number;
  per_category?: Array<{ category: string; status: string; inserted: number }>;
  quota?: ScrapeQuotaState;
  request?: DestinationRequest;
  message?: string;
}

export const populateDestinationWithAi = (
  destinationCity: string,
  country: string,
): Promise<PopulateDestinationResult> =>
  apiPost('/api/hr/catalog/populate-destination-with-ai', {
    destination_city: destinationCity,
    country,
  });

// Real-business discovery (Google Places) for one category × city → master catalog.
export interface DiscoveredVendor {
  name: string;
  rating?: number;
  user_ratings_total?: number;
  business_status?: string;
  website?: string;
  accreditation_tags?: string[];
}

export interface DiscoverVendorsResult {
  vendors: DiscoveredVendor[];
  count: number;
  status?: 'pending_admin_approval';
  message?: string;
}

export const discoverVendorsForCity = (
  category: string,
  destinationCity: string,
  country: string,
): Promise<DiscoverVendorsResult> =>
  apiPost('/api/hr/catalog/discover', {
    category,
    destination_city: destinationCity,
    country,
  });

// ---------------------------------------------------------------------------
// Phase 2 notifications: employee demand + nav badges
// ---------------------------------------------------------------------------

export interface EmployeeDemandRow {
  id: string;
  company_id: string;
  category: string;
  destination_city: string | null;
  destination_country: string | null;
  last_seen_by_user_id: string | null;
  last_seen_at: string;
  demand_count: number;
}

export const listEmployeeDemand = (signal?: AbortSignal): Promise<EmployeeDemandRow[]> =>
  apiGet('/api/hr/catalog/employee-demand', { signal });

export interface HrNotificationCounts {
  employees_waiting: number;
  destinations_with_demand: number;
  pending_admin_tickets: number;
}

export const getHrNotificationCounts = (): Promise<HrNotificationCounts> =>
  apiGet('/api/hr/catalog/notification-counts');

// ---------------------------------------------------------------------------
// AIQ-1602 Seg 4: HR preferred-supplier submissions (admin moderation queue)
// ---------------------------------------------------------------------------

export interface SupplierSubmission {
  id: string;
  company_id: string;
  name: string;
  service_category: string;
  coverage_scope_type: string;
  country_code: string | null;
  city_name: string | null;
  contact_email: string | null;
  status: 'pending' | 'approved' | 'rejected';
  review_notes: string | null;
  created_supplier_id: string | null;
  created_at: string;
}

export interface SupplierSubmissionBody {
  name: string;
  service_category: string;
  coverage_scope_type?: string;
  country_code?: string | null;
  city_name?: string | null;
  contact_email?: string | null;
}

export const createSupplierSubmission = (
  body: SupplierSubmissionBody,
): Promise<SupplierSubmission> =>
  apiPost('/api/hr/catalog/supplier-submissions', body);

export const listMySupplierSubmissions = (): Promise<{ submissions: SupplierSubmission[] }> =>
  apiGet('/api/hr/catalog/supplier-submissions');

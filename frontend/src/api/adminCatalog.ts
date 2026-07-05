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

// CATALOG-1: demand-driven coverage worklist.
export interface DemandGap {
  category: string;
  city: string;
  country: string;
  demand: number;
  companies: number;
  last_seen_at: string | null;
  allowlisted: boolean;
}

/** Highest-demand (category, city) combos with no catalog coverage yet. */
export const listDemandGaps = (limit = 50): Promise<DemandGap[]> =>
  apiGet(`/api/admin/catalog/demand-gaps?limit=${limit}`);

/** Allowlist the destination and fire the scraper for one (category, city). */
export const fillDemandGap = (
  category: string,
  city: string,
  country: string,
): Promise<{ allowlisted: boolean; scraped_count: number; category: string; city: string; country: string }> =>
  apiPost('/api/admin/catalog/demand-gaps/fill', { category, city, country });

// CATALOG-4: proactive intake-driven corridors (pre-warm before employees hit gaps).
export interface IntakeCorridor {
  city: string;
  country: string;
  top_origin: string | null;
  intake_count: number;
  last_intake_at: string | null;
  uncovered_categories: string[];
  allowlisted: boolean;
}

/** Emerging corridors from intake volume, with the categories still uncovered. */
export const listIntakeCorridors = (limit = 50): Promise<IntakeCorridor[]> =>
  apiGet(`/api/admin/catalog/intake-corridors?limit=${limit}`);

export interface AdminNotificationCounts {
  pending_tickets: number;
  allowlisted_destinations: number;
  pending_capabilities: number;
}

export const getAdminNotificationCounts = (): Promise<AdminNotificationCounts> =>
  apiGet('/api/admin/catalog/notification-counts');

// GAP 5 — real supplier discovery
export interface DiscoveryStatus {
  provider: string;
  configured: boolean;
}

export interface DiscoveryResult {
  name: string;
  website: string | null;
  phone: string | null;
  formatted_address: string | null;
  rating: number | null;
  user_ratings_total: number | null;
  place_id: string | null;
  already_in_catalog: boolean;
}

export const getDiscoveryStatus = (): Promise<DiscoveryStatus> =>
  apiGet('/api/admin/catalog/discovery-status');

export const discoverSuppliers = (
  category: string,
  city: string,
  country: string
): Promise<{ results: DiscoveryResult[]; total: number; provider: string }> =>
  apiPost('/api/admin/catalog/discover', { category, city, country });

export const importDiscovered = (payload: {
  category: string;
  city: string;
  country: string;
  items: Array<{ name: string; website?: string | null; place_id?: string | null; formatted_address?: string | null }>;
}): Promise<{ created: number; requested: number }> =>
  apiPost('/api/admin/catalog/discover/import', payload);

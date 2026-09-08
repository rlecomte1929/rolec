import { apiGet } from './client';

/**
 * Admin coverage dashboard (admin-only). One aggregated per-destination payload:
 * immigration facts split by review_status, and provider capabilities per service
 * category split by vetting status. Served from an in-process cache on the backend;
 * `getCoverage(true)` hits `?refresh=true` to force a live recompute.
 */
export interface CoverageCountry {
  iso: string;
  name: string;
  flag: string | null;
  catalog_name: string | null;
  facts: { approved: number; pending: number; rejected: number; total: number };
  providers: {
    by_cat: Record<string, number>;
    approved: number;
    pending: number;
    total: number;
  };
}

export interface CoverageTotals {
  destinations: number;
  facts_approved: number;
  facts_pending: number;
  facts_rejected: number;
  facts_total: number;
  caps_total: number;
  caps_approved: number;
  caps_pending: number;
  suppliers: number;
  expert_verified: number;
}

export interface CoverageSummary {
  generated_at: string;
  serving_categories: string[];
  countries: CoverageCountry[];
  totals: CoverageTotals;
}

export async function getCoverage(refresh = false): Promise<CoverageSummary> {
  return apiGet<CoverageSummary>(`/api/admin/coverage${refresh ? '?refresh=true' : ''}`);
}

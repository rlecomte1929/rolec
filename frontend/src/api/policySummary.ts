// policySummary.ts — thin wrapper around the policy & benefits summary endpoint.
//
// Endpoint: GET /api/policy/summary  (backend/app/routers/policy_summary.py)
// Auth:     HR/employee → backend resolves their own company_id from the token;
//           admin must pass company_id explicitly (else 400).
//
// AIQ-225 (P1-5). Consumed by PolicyBenefitsSummary, rendered as the
// "Benefits summary" tab on /hr/policy. Lives in its own module rather than
// bolting onto client.ts (already 3000+ LOC).

import api from './client';

export type PolicyStatusBanner = 'no_policy' | 'active' | 'under_review' | 'expired';

export interface PolicySummaryVersion {
  id: string;
  version_number: number;
  status: string;
  effective_date: string | null;
  expiry_date: string | null;
  published_by: string | null;
  published_at: string | null;
}

export interface PolicySummaryRow {
  tier_id: string | null; // null = applies to all tiers
  tier_name: string | null;
  cap_value: number | null;
  cap_unit: string | null;
  cap_currency: string; // defaults to 'EUR' server-side
  value_notes: string | null;
  validated_by_id: string | null;
  validated_by_name: string | null;
  validated_at: string | null;
}

export interface PolicySummaryCategory {
  code: string;
  display_name: string;
  sort_order: number;
  rows: PolicySummaryRow[];
}

export interface PolicySummaryResponse {
  company_id: string;
  version: PolicySummaryVersion | null;
  status_banner: PolicyStatusBanner;
  categories: PolicySummaryCategory[];
}

export const policySummaryAPI = {
  get: async (params?: { companyId?: string; tier?: string }): Promise<PolicySummaryResponse> => {
    const query: Record<string, string> = {};
    if (params?.companyId) query.company_id = params.companyId;
    if (params?.tier) query.tier = params.tier;
    const { data } = await api.get<PolicySummaryResponse>('/api/policy/summary', {
      params: query,
    });
    return data;
  },
};

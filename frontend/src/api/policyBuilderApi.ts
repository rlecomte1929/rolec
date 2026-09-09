import { api } from './client';

// ── Policy Builder API ────────────────────────────────────────────────────────
export interface PolicyTemplateCategoryOut {
  category_id: string;
  code: string;
  display_name: string;
  cap_value: number;
  cap_unit: string;
  cap_currency: string;
  benchmark_source: string;
}

export interface PolicyTemplateTierOut {
  tier: string;
  tier_order: number;
  categories: PolicyTemplateCategoryOut[];
}

export interface PolicyTemplatesResponse {
  ok: boolean;
  tiers: PolicyTemplateTierOut[];
}

export const policyBuilderAPI = {
  getTemplates: (): Promise<PolicyTemplatesResponse> =>
    api.get<PolicyTemplatesResponse>('/api/policy/templates').then((r) => r.data),
};

/**
 * AI unit-economics dashboard API client (Parker-G).
 *
 * Per-call cost (USD), tokens, and CO₂e attributed by customer_id + feature_key.
 * Admin-only; backed by GET /api/admin/ai-unit-economics (reads policy_assistant_traces).
 */

import { apiGet } from './client';

export interface AiUnitEconomicsRow {
  customer_id: string | null;
  feature_key: string;
  n_calls: number;
  total_cost_usd: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_co2e_grams: number;
}

export interface AiUnitEconomicsTotals {
  n_calls: number;
  total_cost_usd: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_co2e_grams: number;
}

export interface AiUnitEconomicsRollup {
  rows: AiUnitEconomicsRow[];
  totals: AiUnitEconomicsTotals;
  filters: {
    customer_id: string | null;
    feature_key: string | null;
    from: string | null;
    to: string | null;
  };
}

/** Fetch the AI unit-economics rollup (admin only). All recorded usage. */
export const getAiUnitEconomics = (): Promise<AiUnitEconomicsRollup> =>
  apiGet<AiUnitEconomicsRollup>('/api/admin/ai-unit-economics');

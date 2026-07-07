/**
 * Feedback Autopilot metrics API client (Phase 4).
 *
 * Admin-only; backed by GET /api/admin/autopilot-metrics. Reads the ingest→dispatch→fix→
 * merge→done funnel from public.events (autopilot.* stages) plus month-to-date spend.
 */

import { apiGet } from './client';

export interface AutopilotCostStage {
  stage: string;
  cost_usd: number;
  n_calls?: number;
  tokens_in?: number;
  tokens_out?: number;
}

export interface AutopilotMetrics {
  since: string | null;
  funnel: Record<string, number>;
  dedup: { raw: number; unique: number; dedup_factor: number | null };
  cost: {
    by_stage: AutopilotCostStage[];
    total_usd: number;
    monthly_cap_usd: number;
    remaining_usd: number;
  };
  kpis: {
    dedup_factor: number | null;
    tasks_dispatched: number;
    merged: number;
    tasks_done: number;
    reverted: number;
    escalated_to_human: number;
    runs_halted: number;
    canary_pass_rate: number | null;
    revert_rate: number | null;
  };
}

/** Fetch the autopilot funnel + cost metrics (admin only). */
export const getAutopilotMetrics = (): Promise<AutopilotMetrics> =>
  apiGet<AutopilotMetrics>('/api/admin/autopilot-metrics');

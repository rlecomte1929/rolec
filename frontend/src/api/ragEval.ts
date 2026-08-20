/**
 * RAG-quality dashboard API client (P3-01e).
 *
 * Reads the time-series of the three P3-01 RAG evaluation metrics
 * (context precision, factual consistency, outcome accuracy) with per-metric
 * threshold-alert state. Admin-only; backed by GET /api/admin/rag-eval/metrics.
 */

import { apiGet } from './client';

export type RagEvalAlertReason =
  | 'below_threshold'
  | 'declining'
  | 'healthy'
  | 'no_data';

export interface RagEvalAlert {
  firing: boolean;
  reason: RagEvalAlertReason;
}

export interface RagEvalPoint {
  date: string; // ISO date (YYYY-MM-DD)
  aggregate: number;
  passes_threshold: boolean;
}

/**
 * One (corridor x employee_type) slice of a sliced metric (nonobvious_recall).
 * recall = non-obvious requirements correctly served / lawyer-verified HLP
 * total for the slice; null means the slice has no produced roadmaps yet.
 */
export interface RagEvalSlice {
  corridor: string;
  employee_type: string;
  label?: string | null;
  recall: number | null;
  served: number;
  total: number;
  missing: string[];
  n_roadmaps: number;
  hlp_status: string;
}

export interface RagEvalWorstSlice {
  corridor: string;
  employee_type: string;
  recall: number;
  missing?: string[];
}

export interface RagEvalMetric {
  metric: string;
  label: string;
  threshold: number;
  points: RagEvalPoint[];
  latest: number | null;
  alert: RagEvalAlert;
  /**
   * Sliced metrics only (nonobvious_recall): per-slice recall sorted
   * WORST-FIRST, plus the worst slice's identity. The plotted aggregate is the
   * worst slice's recall \u2014 a minimum, never an average.
   */
  slices?: RagEvalSlice[];
  worst_slice?: RagEvalWorstSlice | null;
}

export interface RagEvalDashboard {
  /** "live" when real eval reports exist on disk; "mock" when synthetic. */
  source: 'live' | 'mock';
  metrics: RagEvalMetric[];
}

/** Fetch the RAG-quality dashboard payload (admin only). */
export const getRagEvalMetrics = (): Promise<RagEvalDashboard> =>
  apiGet<RagEvalDashboard>('/api/admin/rag-eval/metrics');

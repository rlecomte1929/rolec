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

export interface RagEvalMetric {
  metric: string;
  label: string;
  threshold: number;
  points: RagEvalPoint[];
  latest: number | null;
  alert: RagEvalAlert;
}

export interface RagEvalDashboard {
  /** "live" when real eval reports exist on disk; "mock" when synthetic. */
  source: 'live' | 'mock';
  metrics: RagEvalMetric[];
}

/** Fetch the RAG-quality dashboard payload (admin only). */
export const getRagEvalMetrics = (): Promise<RagEvalDashboard> =>
  apiGet<RagEvalDashboard>('/api/admin/rag-eval/metrics');

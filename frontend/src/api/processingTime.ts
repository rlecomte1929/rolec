/**
 * processingTime.ts — fetch the corridor-level processing-time estimate (P2-04).
 *
 * Wraps GET /api/cases/:caseId/processing-time. The endpoint 404s when the
 * feature flag is off, the case is unknown, or no source is available — in every
 * one of those cases we resolve to null so the caller renders nothing (never a
 * processing time without a source).
 */
import type { ProcessingTimeEstimate } from '../components/ProcessingTimeBadge';
import api from './client';

export async function getProcessingTime(
  caseId: string,
): Promise<ProcessingTimeEstimate | null> {
  try {
    const res = await api.get<ProcessingTimeEstimate>(
      `/api/cases/${caseId}/processing-time`,
    );
    return res.data;
  } catch {
    // 404 (flag off / unknown case / no source) or any error → render nothing.
    return null;
  }
}

/**
 * AIQ-554 / AIQ-595: Corrections analytics API wrapper.
 *
 * GET /api/admin/corrections/by-reason — weekly buckets of HR corrections,
 * grouped by reason_code (and optionally corridor / clause_type). Powers the
 * AIQ-598 corrections-trend dashboard (/admin/corrections/trends).
 *
 * Backend enforces HR-Operator RLS, so the rows returned are already scoped to
 * the caller's tenant — the frontend does not (and must not) widen that scope.
 *
 * NOTE: this wrapper was originally introduced on the AIQ-595 branch. If that
 * branch lands first this file may conflict-merge; the contract below matches
 * the AIQ-554 endpoint (weekly buckets grouped by reason / corridor /
 * clause_type with counts).
 */
import { apiGet } from './client';

/** ISO date (Monday) marking the start of a weekly bucket, e.g. "2026-05-25". */
export type WeekStart = string;

/** A single weekly bucket: week start + a count per dimension value. */
export interface CorrectionsWeeklyBucket {
  /** ISO date of the Monday that starts this week. */
  week_start: WeekStart;
  /**
   * Map from dimension value (reason_code, agent name, corridor, …) to the
   * number of corrections in that week. Keys vary by `group_by`.
   */
  counts: Record<string, number>;
}

export interface CorrectionsByReasonResponse {
  /** Weekly buckets, ordered oldest → newest. */
  buckets: CorrectionsWeeklyBucket[];
  /**
   * Distinct dimension values present across all buckets (stable ordering for
   * chart series / legend). E.g. all reason_codes seen in the window.
   */
  series: string[];
  /** The dimension the data was grouped by. */
  group_by: CorrectionsGroupBy;
}

/** Dimension the weekly buckets are grouped by. */
export type CorrectionsGroupBy = 'reason' | 'agent' | 'corridor' | 'clause_type';

export interface GetCorrectionsByReasonParams {
  /** Group buckets by this dimension. Defaults to `reason` server-side. */
  groupBy?: CorrectionsGroupBy;
  /** Inclusive ISO date (YYYY-MM-DD) for the start of the window. */
  from?: string;
  /** Inclusive ISO date (YYYY-MM-DD) for the end of the window. */
  to?: string;
}

/**
 * Fetch weekly correction counts grouped by a dimension. Requires admin / HR
 * role — the backend returns only tenant-scoped rows (HR Operator RLS).
 */
export async function getCorrectionsByReason(
  params?: GetCorrectionsByReasonParams,
  opts?: { signal?: AbortSignal },
): Promise<CorrectionsByReasonResponse> {
  const qs = new URLSearchParams();
  if (params?.groupBy) qs.set('group_by', params.groupBy);
  if (params?.from) qs.set('from', params.from);
  if (params?.to) qs.set('to', params.to);
  const query = qs.toString();
  return apiGet<CorrectionsByReasonResponse>(
    `/api/admin/corrections/by-reason${query ? `?${query}` : ''}`,
    { signal: opts?.signal },
  );
}

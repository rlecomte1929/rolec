/**
 * GAP 3: HR policy compliance matrix — GET /api/hr/policy-compliance-matrix
 *
 * Cross-case aggregated view: all active assignments × 13 benefit types → compliance cell status.
 * Used by S5c (Policy vs. Reality heatmap in the HR Control Center).
 *
 * Cell statuses:
 *   green  = within policy, no issues
 *   amber  = within policy but <20% headroom
 *   red    = over policy cap
 *   grey   = benefit not applicable / not selected
 *   blue   = exception request pending
 */
import { apiGet } from './client';

// [AIQ-2087] The Policy-vs-Reality matrix client was removed with its endpoint,
// its export and its page. The matrix filtered on four non-canonical case statuses
// (so it returned nothing) and computed every cell from a hardcoded spend of 0 (so
// fixing that filter alone would have rendered every benefit GREEN — compliance
// asserted from no measurement). See backend/app/routers/hr_analytics.py.

export interface AnswerProvenanceResponse {
  total: number;
  answers: number;
  refusals: number;
  grounded: number;
  unverified_count: number;
  /** 0–1 share of all questions that were refused */
  refusal_rate: number;
  /** 0–1 share of answered questions verified as grounded */
  grounded_rate: number;
  window_days: number;
}

export async function getAnswerProvenance(
  windowDays = 30,
): Promise<AnswerProvenanceResponse> {
  return apiGet<AnswerProvenanceResponse>(
    `/api/hr/answer-provenance?window_days=${windowDays}`,
  );
}

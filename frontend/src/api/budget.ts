// budget.ts — thin wrapper around the case budget-summary endpoint.
//
// Endpoint: GET /api/cases/:caseId/budget-summary  (backend/app/routers/cases.py:3228)
// Auth:     any authenticated role; caps come from the *caller's* company policy.
//
// AIQ-280 (T1.5 Wire Estimate Review). Consumed by BudgetSummaryTable, which
// is rendered on both /employee/services/estimate and the new
// /hr/cases/:caseId/estimate HR surface.
//
// Lives in its own module rather than bolting onto client.ts (already 2700+ LOC)
// so future budget-related endpoints have an obvious home.

import api from './client';

export type BudgetSummaryStatus = 'within_budget' | 'over_budget' | 'no_cap';

export interface BudgetSummaryCategory {
  /** Service category key, e.g. 'housing', 'schools', 'movers'. */
  name: string;
  /** Cap amount in the policy's native currency; null when no cap. */
  cap_amount: number | null;
  /** Policy currency. Defaults to 'EUR' upstream. */
  cap_currency: string;
  /** Estimated cost for this category. Backend returns null today (placeholder). */
  estimated_amount: number | null;
  /** Within/over/no_cap. Defaults to 'within_budget' when cap exists + estimate null. */
  status: BudgetSummaryStatus;
}

export interface BudgetSummaryResponse {
  case_id: string;
  categories: BudgetSummaryCategory[];
}

export const budgetAPI = {
  /** Fetch budget caps + estimates for a case. Throws on non-2xx. */
  getBudgetSummary: async (caseId: string): Promise<BudgetSummaryResponse> => {
    const { data } = await api.get<BudgetSummaryResponse>(
      `/api/cases/${caseId}/budget-summary`,
    );
    return data;
  },
};

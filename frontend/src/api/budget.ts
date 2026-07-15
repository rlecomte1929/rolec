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

export type BudgetSummaryStatus = 'within_budget' | 'over_budget' | 'no_cap' | 'no_estimate';

export interface BudgetSummaryCategory {
  /** Service category key, e.g. 'housing', 'schools', 'movers'. */
  name: string;
  /** Cap amount in the policy's native currency; null when no cap. */
  cap_amount: number | null;
  /** Policy currency. Defaults to 'EUR' upstream. */
  cap_currency: string;
  /** Estimated cost for this category. Backend returns null today (placeholder). */
  estimated_amount: number | null;
  /** within_budget | over_budget | no_cap | no_estimate (cap set but estimate pending). */
  status: BudgetSummaryStatus;
}

/** [AIQ-1551] One published HR-policy Cost Allowance Package (CAP). */
export interface HrPolicyCap {
  /** Stable benefit key from the policy config, e.g. 'host_housing_cap'. */
  benefit_key: string;
  /** Human label, e.g. 'Housing allowance'. */
  name: string;
  category: string | null;
  /** normalized_cap_type: 'currency_amount' | 'percentage' | 'no_monetary_cap' | … */
  cap_type: string | null;
  /** Cap amount in `currency`; null for a covered-but-unquantified benefit. */
  amount: number | null;
  currency: string | null;
  /** e.g. 'yearly' | 'monthly' | 'one_time' | 'per_trip'. */
  unit_frequency: string | null;
  notes: string | null;
}

export interface BudgetSummaryResponse {
  case_id: string;
  categories: BudgetSummaryCategory[];
  /**
   * [AIQ-1551] The FULL list of the company's published CAPs — all of them, not just the
   * caps for the services the employee selected. Optional for backward-compat with older
   * responses that predate the field.
   */
  hr_policy_caps?: HrPolicyCap[];
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

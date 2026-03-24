/** One row from POST /api/hr/policy-config/caps/compare → results[] */
export interface PolicyCapCompareResultRow {
  benefit_key: string;
  matched_cap?: boolean;
  supported_comparison?: boolean;
  within_cap?: boolean | null;
  cap_amount?: number | null;
  estimate_amount?: number | null;
  difference_amount?: number | null;
  difference_direction?: 'over' | 'under' | 'equal' | null;
  currency_code?: string | null;
  reason_unsupported?: string | null;
  normalized_cap_type?: string | null;
}

export type PolicyCapCompareUiStatus = 'within' | 'exceeds' | 'no_cap';

export function derivePolicyCapCompareUiStatus(row: PolicyCapCompareResultRow): PolicyCapCompareUiStatus {
  if (!row.matched_cap || row.supported_comparison === false) return 'no_cap';
  if (row.supported_comparison && row.within_cap === true) return 'within';
  if (row.supported_comparison && row.within_cap === false) return 'exceeds';
  return 'no_cap';
}

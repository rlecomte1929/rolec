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

export type ComplianceCellStatus = 'green' | 'amber' | 'red' | 'grey' | 'blue';

export interface ComplianceCaseRow {
  id: string;
  name: string;
  /** Two-letter initials for avatar */
  init: string;
  origin: string | null;
  dest: string | null;
  tier: string | null;
  assignment_type: string | null;
  start_date: string | null;
  budget_eur: number | null;
  spend_eur: number | null;
  /** Map from benefit_key → cell status colour */
  cells: Record<string, ComplianceCellStatus>;
}

export interface ComplianceKpis {
  compliance_pct: number;
  active_count: number;
  avg_overage_eur: number | null;
  most_overrun_benefit: string | null;
  benefit_columns: string[];
  benefit_labels: Record<string, string>;
}

export interface PolicyComplianceMatrixResponse {
  cases: ComplianceCaseRow[];
  kpis: ComplianceKpis;
}

export type CompliancePeriod = '6mo' | '12mo' | '24mo';

/**
 * GAP 3: Fetch the cross-case policy compliance heatmap for the HR control center (S5c).
 * Requires admin or HR role — will 403 for regular employees.
 */
export async function getPolicyComplianceMatrix(params?: {
  period?: CompliancePeriod;
  tier?: string;
  destination?: string;
}): Promise<PolicyComplianceMatrixResponse> {
  const qs = new URLSearchParams();
  if (params?.period) qs.set('period', params.period);
  if (params?.tier) qs.set('tier', params.tier);
  if (params?.destination) qs.set('destination', params.destination);
  const query = qs.toString();
  return apiGet<PolicyComplianceMatrixResponse>(
    `/api/hr/policy-compliance-matrix${query ? `?${query}` : ''}`,
  );
}

export type EmployeePolicyMaturity = 'no_policy' | 'under_review' | 'partial_comparison' | 'full_comparison';

type Readiness = {
  comparison_ready?: boolean;
  comparison_blockers?: string[];
  partial_numeric_coverage?: boolean;
} | null;

export function deriveEmployeePolicyMaturity(args: {
  hasPolicy: boolean;
  comparisonAvailable: boolean;
  readiness: Readiness;
  benefitsCount: number;
  effectiveRowsCount: number;
}): EmployeePolicyMaturity {
  const { hasPolicy, comparisonAvailable, readiness, benefitsCount, effectiveRowsCount } = args;
  if (!hasPolicy) return 'under_review';
  if (comparisonAvailable) return 'full_comparison';
  const partial = readiness?.partial_numeric_coverage === true;
  if (partial || benefitsCount > 0 || effectiveRowsCount > 0) return 'partial_comparison';
  return 'under_review';
}

const SERVICE_KEY_LABELS: Record<string, string> = {
  visa_support: 'Visa / immigration support',
  temporary_housing: 'Temporary housing',
  home_search: 'Home search',
  school_search: 'School search',
  household_goods_shipment: 'Household goods shipment',
};

export function labelForServiceKey(key: string): string {
  const k = (key || '').trim();
  if (!k) return 'Service';
  return SERVICE_KEY_LABELS[k] || k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Map engine comparison_status to employee-facing line (never raw codes). */
export function labelForEngineComparisonStatus(status: string): string {
  const s = (status || '').toLowerCase();
  if (s === 'within_envelope') return 'Within policy limit';
  if (s === 'exceeds_envelope') return 'Above policy limit';
  if (s === 'excluded') return 'Excluded';
  if (s === 'information_only') return 'Informational';
  if (s === 'not_enough_policy_data') return 'Needs more detail';
  if (s === 'conditional') return 'Conditional';
  return 'Status unavailable';
}

export function labelForCoverageStatus(status: string): string {
  const s = (status || '').toLowerCase();
  if (s === 'excluded') return 'Excluded';
  if (s === 'included') return 'Included';
  if (s === 'conditional') return 'Conditional';
  if (s === 'unknown') return 'Unclear from policy';
  return 'See notes';
}

/** Legacy comparison item policy_status → display. */
export function labelForLegacyPolicyStatus(status: string): string {
  const s = (status || '').toLowerCase();
  if (s === 'included') return 'Included';
  if (s === 'excluded') return 'Excluded';
  if (s === 'capped') return 'Included (limit applies)';
  if (s === 'approval_required') return 'Included — approval required';
  if (s === 'partial') return 'Partially covered';
  if (s === 'out_of_scope') return 'Outside policy scope';
  if (s === 'uncertain' || s === 'informational') return 'Informational';
  return 'See explanation';
}

export function formatPolicyLimitSnapshot(snap: Record<string, unknown>): string | null {
  const max = snap.max_value ?? snap.standard_value ?? snap.min_value;
  const cur = snap.currency;
  const unit = snap.amount_unit;
  const freq = snap.frequency;
  if (max == null && !unit && !freq) return null;
  const parts: string[] = [];
  if (max != null) parts.push(`${cur ? `${String(cur)} ` : ''}${max}${unit ? ` ${unit}` : ''}`.trim());
  else if (cur || unit) parts.push([cur, unit].filter(Boolean).join(' '));
  if (freq) parts.push(String(freq));
  return parts.length ? parts.join(' · ') : null;
}

export function formatSelectedSnapshot(snap: Record<string, unknown>): string | null {
  const est = snap.estimated_cost;
  const cur = snap.currency;
  if (est == null) return null;
  return `${cur ? `${String(cur)} ` : ''}${est}`;
}

export type PackBenefitRow = {
  benefit_key: string;
  included: boolean;
  min_value?: number | null;
  standard_value?: number | null;
  max_value?: number | null;
  currency?: string;
  amount_unit?: string;
  frequency?: string;
  approval_required: boolean;
  evidence_required_json?: string[];
  exclusions_json?: Array<{ domain?: string; description?: string }>;
  condition_summary?: string;
};

export function formatBenefitCapLine(b: PackBenefitRow): string | null {
  const cur = b.currency || 'USD';
  const vals = [b.min_value, b.standard_value, b.max_value].filter((v) => v != null && Number(v) > 0) as number[];
  if (vals.length === 0) return null;
  const max = Math.max(...vals);
  return `${cur} ${max.toLocaleString()}${b.amount_unit ? ` ${b.amount_unit}` : ''}${b.frequency ? ` · ${b.frequency}` : ''}`;
}

export function deriveBenefitRowStatus(b: PackBenefitRow): 'included' | 'excluded' | 'conditional' {
  if (!b.included) return 'excluded';
  if (b.approval_required) return 'conditional';
  const hasCap = b.max_value != null || b.standard_value != null || b.min_value != null;
  if (!hasCap && !(b.condition_summary || '').trim()) return 'included';
  if (!hasCap) return 'conditional';
  return 'included';
}

export function employeeLabelForBenefitStatus(s: 'included' | 'excluded' | 'conditional'): string {
  if (s === 'excluded') return 'Not included';
  if (s === 'conditional') return 'Included — conditions or approval may apply';
  return 'Included';
}

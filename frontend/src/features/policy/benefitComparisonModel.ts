/**
 * Pure mapping + aggregation for the employee Benefit Comparison dashboard (P3-2 / AIQ-237).
 *
 * Source of truth is the comparison engine's honest `effective_service_comparison`
 * rows (see backend/app/services/service_comparison_engine.py). The engine
 * deliberately withholds numeric caps/deltas when a policy version or rule is not
 * comparison-ready — this module NEVER fabricates a cap, ask, or delta. Rows the
 * engine can't compare numerically surface as `info` with null amounts, and the
 * KPI totals only aggregate values the engine actually provided.
 *
 * No React here so the rules are unit-testable in isolation.
 */
import type { EffectiveServiceComparisonRow } from '../../types';
import { labelForServiceKey } from './employeePolicyPanelModel';

/** Coverage badge buckets. green/amber/red mirror the task's badge spec; `info`
 *  is the honest fallback for rows the engine cannot numerically classify. */
export type CoverageBadge = 'covered' | 'partial' | 'uncovered' | 'info';

export interface ComparisonRow {
  serviceKey: string;
  label: string;
  /** Policy cap (max → standard) when the engine exposes one; null otherwise. */
  policyCap: number | null;
  /** Employee's estimated ask when known; null otherwise. */
  ask: number | null;
  currency: string;
  coverage: CoverageBadge;
  /** Employee-facing coverage word (never a raw engine code). */
  coverageLabel: string;
  /** Engine delta (ask − cap); positive = over cap. null when not comparable. */
  delta: number | null;
  /** Per-category amount the employee is expected to pay; null = not computable. */
  outOfPocket: number | null;
  comparisonStatus: string;
  explanation: string;
  approvalRequired: boolean;
  /** True for Partial (over-cap) and Uncovered rows — drives the exception CTA. */
  canRequestException: boolean;
}

export interface ComparisonKpis {
  /** Σ of known policy caps; null when no row exposes a numeric cap. */
  totalAllocation: number | null;
  /** Σ of known asks; null when no row exposes an estimate. */
  totalAsk: number | null;
  /** Σ of per-category out-of-pocket the engine could compute (≥ 0). */
  outOfPocket: number;
  currency: string;
  /** True when at least one selected service could not be numerically compared. */
  hasUncomparable: boolean;
}

const COVERAGE_LABELS: Record<CoverageBadge, string> = {
  covered: 'Covered',
  partial: 'Partial',
  uncovered: 'Not covered',
  info: 'Coverage info',
};

function firstNumber(snap: Record<string, unknown>, keys: string[]): number | null {
  for (const k of keys) {
    const v = snap[k];
    if (typeof v === 'number' && isFinite(v)) return v;
    if (typeof v === 'string' && v.trim() !== '' && isFinite(Number(v))) return Number(v);
  }
  return null;
}

function snapshotCurrency(
  policy: Record<string, unknown>,
  selected: Record<string, unknown>,
): string {
  const c = policy.currency ?? selected.currency;
  return typeof c === 'string' && c.trim() ? c.toUpperCase() : 'USD';
}

/** Comparable single cap, matching the engine: prefer max, then standard. */
function policyCapFromSnapshot(snap: Record<string, unknown>): number | null {
  return firstNumber(snap, ['max_value', 'standard_value']);
}

function coverageBadge(row: EffectiveServiceComparisonRow): CoverageBadge {
  const cov = (row.coverage_status || '').toLowerCase();
  const cmp = (row.comparison_status || '').toLowerCase();
  if (cov === 'excluded' || cmp === 'excluded') return 'uncovered';
  if (cmp === 'within_envelope') return 'covered';
  if (cmp === 'exceeds_envelope') return 'partial';
  return 'info';
}

/**
 * Per-category amount the employee pays out of pocket:
 *   covered   → 0
 *   partial   → delta (the over-cap amount)
 *   uncovered → full ask (policy covers nothing), when the ask is known
 *   info      → null (not computable — never guessed)
 */
function rowOutOfPocket(
  coverage: CoverageBadge,
  delta: number | null,
  ask: number | null,
): number | null {
  if (coverage === 'covered') return 0;
  if (coverage === 'partial') return delta; // exceeds_envelope always carries a positive delta
  if (coverage === 'uncovered') return ask != null ? ask : null;
  return null;
}

export function mapComparisonRow(row: EffectiveServiceComparisonRow): ComparisonRow {
  const policy = (row.policy_limit_snapshot || {});
  const selected = (row.selected_value_snapshot || {});
  const coverage = coverageBadge(row);
  const policyCap = policyCapFromSnapshot(policy);
  const ask = firstNumber(selected, ['estimated_cost']);
  const oop = rowOutOfPocket(coverage, row.delta, ask);
  return {
    serviceKey: row.service_key,
    label: labelForServiceKey(row.service_key),
    policyCap,
    ask,
    currency: snapshotCurrency(policy, selected),
    coverage,
    coverageLabel: COVERAGE_LABELS[coverage],
    delta: row.delta,
    outOfPocket: oop,
    comparisonStatus: row.comparison_status,
    explanation: row.explanation,
    approvalRequired: Boolean(row.approval_required),
    canRequestException: coverage === 'partial' || coverage === 'uncovered',
  };
}

export function mapComparisonRows(rows: EffectiveServiceComparisonRow[]): ComparisonRow[] {
  return (rows || []).map(mapComparisonRow);
}

export function buildKpis(rows: ComparisonRow[]): ComparisonKpis {
  const caps = rows.map((r) => r.policyCap).filter((v): v is number => v != null);
  const asks = rows.map((r) => r.ask).filter((v): v is number => v != null);
  const oop = rows
    .map((r) => r.outOfPocket)
    .filter((v): v is number => v != null && v > 0)
    .reduce((a, b) => a + b, 0);
  const currency = rows.find((r) => r.currency)?.currency ?? 'USD';
  // A selected service is "uncomparable" when we could not compute its
  // out-of-pocket contribution (info rows, or uncovered rows without an ask).
  const hasUncomparable = rows.some((r) => r.outOfPocket == null);
  return {
    totalAllocation: caps.length ? caps.reduce((a, b) => a + b, 0) : null,
    totalAsk: asks.length ? asks.reduce((a, b) => a + b, 0) : null,
    outOfPocket: oop,
    currency,
    hasUncomparable,
  };
}

/** Rows that belong in the out-of-pocket summary section (Partial + Uncovered). */
export function outOfPocketRows(rows: ComparisonRow[]): ComparisonRow[] {
  return rows.filter((r) => r.coverage === 'partial' || r.coverage === 'uncovered');
}

/**
 * True when the policy's expiry date is strictly in the past.
 *
 * NOTE: the employee `services-policy-context` payload does not yet carry an
 * `expiry_date` (only `effective_date`). This helper reads it defensively so the
 * amber "expired" banner fires correctly the moment the backend surfaces it —
 * see the follow-up note in the handoff. Returns false for missing/unparseable
 * dates so the banner never falsely fires.
 */
export function isPolicyExpired(
  expiryDate: string | null | undefined,
  now: Date,
): boolean {
  if (!expiryDate) return false;
  const t = Date.parse(expiryDate);
  if (Number.isNaN(t)) return false;
  return t < now.getTime();
}

/** Format a money amount with the row/KPI currency; falls back gracefully. */
export function formatMoney(value: number | null | undefined, currency = 'USD'): string {
  if (typeof value !== 'number' || !isFinite(value)) return '—';
  try {
    return value.toLocaleString('en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    });
  } catch {
    return `${currency} ${Math.round(value).toLocaleString('en-US')}`;
  }
}

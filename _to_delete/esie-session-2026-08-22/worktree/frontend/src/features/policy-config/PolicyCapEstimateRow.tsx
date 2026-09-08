import React from 'react';
import { PolicyCapComparisonBadge } from './PolicyCapComparisonBadge';
import { formatPolicyCurrency, formatPolicyPercentage } from './formatPolicyMoney';
import {
  derivePolicyCapCompareUiStatus,
  type PolicyCapCompareResultRow,
} from './policyCapCompareTypes';

function exceedsCopy(row: PolicyCapCompareResultRow): string {
  const cur = row.currency_code || 'USD';
  const diff = row.difference_amount;
  if (row.difference_direction === 'over' && diff != null && Number.isFinite(diff)) {
    return `Estimate exceeds approved budget by ${formatPolicyCurrency(diff, cur)}`;
  }
  return 'Estimate exceeds approved budget';
}

export const PolicyCapEstimateRow: React.FC<{
  title: string;
  subtitle?: string;
  result?: PolicyCapCompareResultRow | null;
  /** When the service is not mapped to a benefit_key */
  unmapped?: boolean;
  estimateAmount: number;
  estimateCurrency: string;
}> = ({ title, subtitle, result, unmapped, estimateAmount, estimateCurrency }) => {
  if (unmapped) {
    return (
      <div className="rounded-lg border border-[#e2e8f0] bg-white p-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="font-medium text-[#0b2b43]">{title}</div>
            {subtitle ? <div className="text-xs text-[#6b7280] mt-0.5">{subtitle}</div> : null}
          </div>
          <PolicyCapComparisonBadge status="no_cap" />
        </div>
        <div className="mt-2 text-xs text-[#6b7280]">
          Provider estimate: {formatPolicyCurrency(estimateAmount, estimateCurrency)}
        </div>
        <div className="mt-1 text-xs text-[#64748b]">No approved cap available for this service</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="rounded-lg border border-[#e2e8f0] p-3 text-sm text-[#6b7280]">
        <div className="font-medium text-[#0b2b43]">{title}</div>
        <div className="mt-1">Loading comparison…</div>
      </div>
    );
  }

  const status = derivePolicyCapCompareUiStatus(result);
  const cur = result.currency_code || estimateCurrency;
  const cap =
    result.supported_comparison && result.cap_amount != null && Number.isFinite(result.cap_amount)
      ? formatPolicyCurrency(result.cap_amount, cur)
      : null;
  const est =
    result.estimate_amount != null && Number.isFinite(result.estimate_amount)
      ? formatPolicyCurrency(result.estimate_amount, estimateCurrency)
      : formatPolicyCurrency(estimateAmount, estimateCurrency);
  const overBudgetPct =
    status === 'exceeds' &&
    result.supported_comparison &&
    result.cap_amount != null &&
    result.cap_amount > 0 &&
    result.estimate_amount != null
      ? formatPolicyPercentage((result.estimate_amount - result.cap_amount) / result.cap_amount)
      : null;

  return (
    <div
      className={`rounded-lg border p-3 text-sm ${
        status === 'exceeds'
          ? 'border-red-200 bg-red-50/80'
          : status === 'within'
            ? 'border-emerald-200 bg-emerald-50/50'
            : 'border-[#e2e8f0] bg-white'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium text-[#0b2b43]">{title}</div>
          {subtitle ? <div className="text-xs text-[#6b7280] mt-0.5">{subtitle}</div> : null}
        </div>
        <PolicyCapComparisonBadge status={status} />
      </div>
      <dl className="mt-2 grid grid-cols-1 gap-1 text-xs text-[#4b5563] sm:grid-cols-3">
        <div>
          <dt className="text-[#94a3b8]">Approved cap</dt>
          <dd className="font-medium text-[#0b2b43]">{cap ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-[#94a3b8]">Provider estimate</dt>
          <dd className="font-medium text-[#0b2b43]">{est}</dd>
        </div>
        <div>
          <dt className="text-[#94a3b8]">Difference</dt>
          <dd className="font-medium text-[#0b2b43]">
            {result.supported_comparison &&
            result.difference_amount != null &&
            result.difference_direction &&
            result.difference_direction !== 'equal'
              ? `${result.difference_direction === 'over' ? '+' : '−'}${formatPolicyCurrency(
                  result.difference_amount,
                  cur
                )}`
              : result.supported_comparison && result.difference_direction === 'equal'
                ? formatPolicyCurrency(0, cur)
                : '—'}
          </dd>
        </div>
      </dl>
      {status === 'no_cap' ? (
        <div className="mt-2 text-xs text-[#64748b]">No approved cap available for this service</div>
      ) : null}
      {status === 'exceeds' ? (
        <div className="mt-2 text-xs font-medium text-red-800">
          {exceedsCopy(result)}
          {overBudgetPct ? ` (${overBudgetPct} over cap)` : null}
        </div>
      ) : null}
    </div>
  );
};

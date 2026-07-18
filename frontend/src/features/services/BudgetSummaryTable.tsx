// BudgetSummaryTable.tsx — 4-column policy-cap view (AIQ-280 / T1.5).
//
// Rendered on:
//   - /employee/services/estimate (above PackageSummary)
//   - /hr/cases/:caseId/estimate    (HrCaseEstimatePage primary surface)
//
// Independent of the recommendation/shortlist flow so it works even when the
// employee hasn't picked any services yet. Backend endpoint is shared
// (GET /api/cases/:id/budget-summary) but the two surfaces consume the same
// data with slightly different display rules:
//
//   * Employee: amounts converted to displayCurrency (matches PackageSummary).
//   * HR: amounts in the policy's native currency so HR sees the policy as
//     written, with the currency code suffixed for clarity.
//
// `estimated_amount` is null in the backend today (no quote pipeline wired);
// surfaced honestly as 'Not yet estimated' rather than a fake number.

import React, { useEffect, useRef, useState } from 'react';
import { trackEstimateReviewOpened } from '../../analyticsEvents';
import { Alert, Button, Card } from '../../components/antigravity';
import {
  budgetAPI,
  type BudgetSummaryCategory,
  type BudgetSummaryResponse,
  type BudgetSummaryStatus,
} from '../../api/budget';
import { logger } from '../../lib/logger';
import {
  convertUsdToDisplay,
  formatServicesMoney,
} from './servicesCurrency';

// ── Category label map ─────────────────────────────────────────────────────────
// Matches the canonical labels used in PackageSummary / ServicesEstimate.
const CATEGORY_LABELS: Record<string, string> = {
  housing: 'Housing',
  schools: 'Schools',
  movers: 'Movers',
  moving: 'Movers',
  immigration: 'Immigration',
  insurance: 'Insurance',
  banks: 'Banks',
  electricity: 'Electricity',
  living_areas: 'Living Areas',
  spouse: 'Spouse support',
  tax: 'Tax assistance',
  travel: 'Travel',
  settling_in: 'Settling-in',
  integration: 'Language / integration',
  repatriation: 'Repatriation',
  home_sale: 'Home sale / purchase',
};

function labelFor(name: string): string {
  return CATEGORY_LABELS[name] ?? name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Status badge ───────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<BudgetSummaryStatus, { label: string; className: string }> = {
  within_budget: {
    label: 'Within budget',
    className: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  },
  over_budget: {
    label: 'Over budget',
    className: 'bg-rose-50 text-rose-700 ring-rose-200',
  },
  no_cap: {
    label: 'No company cap',
    className: 'bg-amber-50 text-amber-700 ring-amber-200',
  },
  no_estimate: {
    label: 'Pending estimate',
    className: 'bg-slate-50 text-slate-600 ring-slate-200',
  },
};

function StatusBadge({ status }: { status: BudgetSummaryStatus }) {
  const s = STATUS_STYLES[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${s.className}`}
    >
      {s.label}
    </span>
  );
}

// ── Amount formatting ──────────────────────────────────────────────────────────

interface FormatOpts {
  amount: number | null;
  capCurrency: string;
  displayCurrency: string;
  /** When true, render the amount in capCurrency natively (HR view). */
  nativeCurrency: boolean;
}

function formatCap({ amount, capCurrency, displayCurrency, nativeCurrency }: FormatOpts): string {
  if (amount == null) return '—';
  if (nativeCurrency) {
    // HR view: display in the policy's native currency, suffixed with the code
    // when it differs from the page's display currency so HR sees the actual
    // policy denomination unambiguously.
    return formatServicesMoney(amount, capCurrency);
  }
  // Employee view: convert from the policy currency to the employee's chosen
  // display currency. The codebase assumes a USD baseline for the FX helper;
  // we treat cap_amount as already in cap_currency and convert pragmatically:
  // if cap_currency matches displayCurrency, display as-is; otherwise approximate
  // via USD-pivot (cap → USD → displayCurrency).
  if (capCurrency.toUpperCase() === displayCurrency.toUpperCase()) {
    return formatServicesMoney(amount, displayCurrency);
  }
  // No direct cap-currency → USD inverse helper exists in servicesCurrency.
  // For the placeholder/null-estimate world we live in today, displaying the
  // native amount with a code suffix is the safest behavior — promises no FX
  // accuracy we can't deliver.
  return `${formatServicesMoney(amount, capCurrency)} (${capCurrency})`;
}

function formatEstimate(
  amount: number | null,
  displayCurrency: string,
): string {
  if (amount == null) return 'Not yet estimated';
  // Estimates, when present, are stored in USD baseline (matches PackageSummary).
  const display = convertUsdToDisplay(amount, displayCurrency);
  return formatServicesMoney(display, displayCurrency);
}

// ── Component ─────────────────────────────────────────────────────────────────

export interface BudgetSummaryTableProps {
  caseId: string;
  /** Display currency for the 'Your estimate' column. */
  displayCurrency: string;
  /**
   * When true, cap amounts render in the policy's native currency (HR mode).
   * When false (employee mode), cap amounts attempt to convert to displayCurrency,
   * falling back to native + suffix when currencies don't match the FX baseline.
   */
  nativeCurrencyForCaps?: boolean;
  /** Optional className for the outer wrapper. */
  className?: string;
}

export const BudgetSummaryTable: React.FC<BudgetSummaryTableProps> = ({
  caseId,
  displayCurrency,
  nativeCurrencyForCaps = false,
  className = '',
}) => {
  const [data, setData] = useState<BudgetSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState<number>(0);
  // Analytics: fire estimate_review_opened once per case (not on every retry).
  const reportedCaseRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    budgetAPI
      .getBudgetSummary(caseId)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        // Analytics: policy-vs-estimate health, once per case view. PII-free —
        // category status counts only (no names, no cost amounts).
        if (reportedCaseRef.current !== caseId) {
          reportedCaseRef.current = caseId;
          const cats = res.categories ?? [];
          const count = (s: BudgetSummaryStatus) => cats.filter((c) => c.status === s).length;
          trackEstimateReviewOpened({
            case_id: caseId,
            categories_count: cats.length,
            any_line_over_policy: count('over_budget') > 0,
            lines_over_policy_count: count('over_budget'),
            lines_within_policy_count: count('within_budget'),
            lines_no_cap_count: count('no_cap'),
            lines_no_estimate_count: count('no_estimate'),
            hr_policy_caps_count: res.hr_policy_caps?.length ?? 0,
          });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        logger.error('BudgetSummaryTable: load failed', { caseId, err });
        setError(
          'We couldn’t load the policy caps for this case. Try again, or contact your administrator if the issue persists.',
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, reloadKey]);

  if (loading) {
    return (
      <Card padding="lg" className={className}>
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Policy caps</div>
        <div className="space-y-2" aria-busy="true" aria-label="Loading policy caps">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-[#e2e8f0]" />
          ))}
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card padding="lg" className={className}>
        <Alert variant="error">{error}</Alert>
        <Button
          variant="outline"
          className="mt-3"
          onClick={() => setReloadKey((k) => k + 1)}
        >
          Retry
        </Button>
      </Card>
    );
  }

  const categories: BudgetSummaryCategory[] = data?.categories ?? [];

  if (categories.length === 0) {
    return (
      <Card padding="lg" className={className}>
        <div className="text-sm font-semibold text-[#0b2b43] mb-1">Policy caps</div>
        <p className="text-sm text-[#6b7280]">
          No policy caps to compare against yet. Once HR publishes a policy for your company,
          per-category caps will show here.
        </p>
      </Card>
    );
  }

  return (
    <Card padding="lg" className={className}>
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-[#0b2b43]">Policy caps</div>
        <span className="text-[11px] text-slate-500">
          Cap source: your company&apos;s published HR policy
        </span>
      </div>
      <Alert variant="info" className="mb-3">
        <p className="text-sm">
          Estimates wire up after vendor quotes come back — currently showing policy caps
          only. Each row shows what your company budgeted; the estimate column will populate
          as quotes arrive.
        </p>
      </Alert>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500 border-b border-slate-200">
              <th scope="col" className="py-2 pr-4">Category</th>
              <th scope="col" className="py-2 pr-4">Your estimate</th>
              <th scope="col" className="py-2 pr-4">Policy cap</th>
              <th scope="col" className="py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((row) => (
              <tr key={row.name} className="border-b border-slate-100 last:border-b-0">
                <td className="py-2.5 pr-4 font-medium text-slate-900">{labelFor(row.name)}</td>
                <td className="py-2.5 pr-4 text-slate-600">
                  {formatEstimate(row.estimated_amount, displayCurrency)}
                </td>
                <td className="py-2.5 pr-4 text-slate-700">
                  {formatCap({
                    amount: row.cap_amount,
                    capCurrency: row.cap_currency,
                    displayCurrency,
                    nativeCurrency: nativeCurrencyForCaps,
                  })}
                </td>
                <td className="py-2.5">
                  <StatusBadge status={row.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

export default BudgetSummaryTable;

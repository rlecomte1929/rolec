// HrPolicyCapsSection.tsx — [AIQ-1551] the FULL list of the company's published HR-policy
// CAPs (Cost Allowance Packages), shown on the estimate page.
//
// Complements BudgetSummaryTable, which only compares caps for the services the employee
// *selected*. This section lists everything HR configured, so a tester who set up caps sees
// them even before picking services (BUG-260715-557D: "I cannot see any CAP associated with
// the HR Policy of this company"). Self-fetches the shared budget-summary endpoint and reads
// its `hr_policy_caps` field. Amounts are shown honestly — a covered-but-unquantified benefit
// renders as "Covered", never a fabricated number.

import React, { useEffect, useState } from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import { budgetAPI, type BudgetSummaryResponse, type HrPolicyCap } from '../../api/budget';
import { logger } from '../../lib/logger';
import { formatServicesMoney } from './servicesCurrency';

const FREQUENCY_SUFFIX: Record<string, string> = {
  monthly: '/ month',
  yearly: '/ year',
  per_trip: '/ trip',
  per_day: '/ day',
  per_dependent: '/ dependent',
  one_time: '',
  custom: '',
};

function labelCategory(category: string | null): string {
  if (!category) return '—';
  return category.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function CapAmount({ cap }: { cap: HrPolicyCap }) {
  if (cap.amount == null || !cap.currency) {
    // Honest: covered but not quantified — never a fabricated number.
    return (
      <span className="inline-flex items-center rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-inset ring-slate-200">
        Covered
      </span>
    );
  }
  const suffix = FREQUENCY_SUFFIX[cap.unit_frequency ?? ''] ?? '';
  return (
    <span className="text-slate-700">
      {formatServicesMoney(cap.amount, cap.currency)}
      {suffix ? ` ${suffix}` : ''}
    </span>
  );
}

export interface HrPolicyCapsSectionProps {
  caseId: string;
  className?: string;
}

export const HrPolicyCapsSection: React.FC<HrPolicyCapsSectionProps> = ({ caseId, className = '' }) => {
  const [data, setData] = useState<BudgetSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    budgetAPI
      .getBudgetSummary(caseId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        logger.error('HrPolicyCapsSection: load failed', { caseId, err });
        setError(
          'We couldn’t load your HR policy caps. Try again, or contact your administrator if the issue persists.',
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
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">HR Policy — Cost Allowance Packages</div>
        <div className="space-y-2" aria-busy="true" aria-label="Loading HR policy caps">
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
        <Button variant="outline" className="mt-3" onClick={() => setReloadKey((k) => k + 1)}>
          Retry
        </Button>
      </Card>
    );
  }

  const caps: HrPolicyCap[] = data?.hr_policy_caps ?? [];

  if (caps.length === 0) {
    return (
      <Card padding="lg" className={className}>
        <div className="text-sm font-semibold text-[#0b2b43] mb-1">HR Policy — Cost Allowance Packages</div>
        <p className="text-sm text-[#6b7280]">
          No CAPs published yet. Once HR publishes a policy with cost allowances for your company,
          the full list will appear here.
        </p>
      </Card>
    );
  }

  return (
    <Card padding="lg" className={className}>
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-[#0b2b43]">HR Policy — Cost Allowance Packages</div>
        <span className="text-[11px] text-slate-500">Source: your company&apos;s published HR policy</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500 border-b border-slate-200">
              <th scope="col" className="py-2 pr-4">Package</th>
              <th scope="col" className="py-2 pr-4">Category</th>
              <th scope="col" className="py-2">Cap</th>
            </tr>
          </thead>
          <tbody>
            {caps.map((cap) => (
              <tr key={cap.benefit_key} className="border-b border-slate-100 last:border-b-0">
                <td className="py-2.5 pr-4 font-medium text-slate-900">
                  {cap.name}
                  {cap.notes ? <span className="block text-[11px] text-slate-400">{cap.notes}</span> : null}
                </td>
                <td className="py-2.5 pr-4 text-slate-600">{labelCategory(cap.category)}</td>
                <td className="py-2.5">
                  <CapAmount cap={cap} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

export default HrPolicyCapsSection;

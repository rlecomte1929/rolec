import React, { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import type { RecommendationResponse, RecommendationItem } from './types';
import {
  EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_PRIMARY,
  EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_SECONDARY,
} from '../policy/employeePolicyMessages';
import {
  convertUsdToDisplay,
  formatEstimationFromUsd,
  formatServicesMoney,
  SERVICES_CURRENCY_FOOTNOTE,
} from '../services/servicesCurrency';

/** Category key to policy-budget cap key (from resolved HR policy) */
const CATEGORY_TO_CAP: Record<string, string> = {
  housing: 'housing_monthly_usd',
  schools: 'schools_usd',
  movers: 'movers_usd',
};

const CATEGORY_COST_TYPE: Record<string, 'monthly' | 'annual' | 'one_time'> = {
  housing: 'monthly',
  schools: 'annual',
  movers: 'one_time',
};

function getItemCost(item: RecommendationItem, costType: string): number {
  const usd = item.metadata?.estimated_cost_usd;
  if (usd == null) return 0;
  if (costType === 'monthly') return usd;
  if (costType === 'annual') return usd;
  return usd;
}

interface PolicyCaps {
  housing_monthly_usd: number;
  movers_usd: number;
  schools_usd: number;
}

interface Props {
  results: Record<string, RecommendationResponse>;
  selectedPackage: Map<string, string>;
  categoryLabels: Record<string, string>;
  onBack: () => void;
  onStartOver: () => void;
  /** Employee-chosen display currency (services flow). Amounts convert from USD baseline. */
  displayCurrency: string;
}

export const PackageSummary: React.FC<Props> = ({
  results,
  selectedPackage,
  categoryLabels,
  onBack,
  onStartOver,
  displayCurrency,
}) => {
  const [policyCaps, setPolicyCaps] = useState<PolicyCaps | null>(null);
  const [comparisonAvailable, setComparisonAvailable] = useState<boolean | null>(null);
  const [hasPublishedPolicy, setHasPublishedPolicy] = useState(false);
  const [capsLoading, setCapsLoading] = useState(true);
  const location = useLocation();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
  } = useEmployeeAssignment();
  const queryAssignmentId = useMemo(() => parseAssignmentSearchParam(location.search), [location.search]);
  const { effectiveId: assignmentId } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );

  useEffect(() => {
    let cancelled = false;
    setCapsLoading(true);

    const run = async () => {
      try {
        if (assignmentId) {
          try {
            const res = await employeeAPI.getPolicyBudget(assignmentId);
            if (cancelled) return;
            const hp = res?.has_policy === true;
            setHasPublishedPolicy(hp);
            const cmp = res?.comparison_available !== false;
            setComparisonAvailable(cmp);
            if (!cmp) {
              setPolicyCaps(null);
              return;
            }
            const caps = res?.caps || {};
            if (Object.keys(caps).length > 0) {
              setPolicyCaps({
                housing_monthly_usd: caps.housing ?? 0,
                movers_usd: caps.movers ?? 0,
                schools_usd: caps.schools ?? 0,
              });
              return;
            }
            const c = await employeeAPI.getPolicyCaps();
            if (!cancelled) setPolicyCaps(c);
          } catch {
            if (cancelled) return;
            setComparisonAvailable(null);
            setHasPublishedPolicy(false);
            try {
              const c = await employeeAPI.getPolicyCaps();
              if (!cancelled) setPolicyCaps(c);
            } catch {
              if (!cancelled) setPolicyCaps(null);
            }
          }
        } else {
          setComparisonAvailable(null);
          setHasPublishedPolicy(false);
          try {
            const c = await employeeAPI.getPolicyCaps();
            if (!cancelled) setPolicyCaps(c);
          } catch {
            if (!cancelled) setPolicyCaps(null);
          }
        }
      } finally {
        if (!cancelled) setCapsLoading(false);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  const packageItems: { category: string; item: RecommendationItem }[] = [];
  for (const [category, res] of Object.entries(results)) {
    const itemId = selectedPackage.get(category);
    if (!itemId) continue;
    const item = res.recommendations.find((r) => r.item_id === itemId);
    if (item) packageItems.push({ category, item });
  }

  const comparison: {
    category: string;
    label: string;
    total: number;
    cap: number;
    covered: number;
    extra: number;
    /** Published policy exists but no mapped numeric cap for this service category — treat as uncovered for estimates. */
    noPublishedCapForCategory: boolean;
  }[] = [];
  if (policyCaps) {
    for (const { category, item } of packageItems) {
      const capKey = CATEGORY_TO_CAP[category];
      const costType = CATEGORY_COST_TYPE[category] || 'one_time';
      const total = getItemCost(item, costType);
      const cap =
        capKey === 'housing_monthly_usd'
          ? policyCaps.housing_monthly_usd
          : capKey === 'movers_usd'
            ? policyCaps.movers_usd
            : capKey === 'schools_usd'
              ? policyCaps.schools_usd
              : 0;
      const noPublishedCapForCategory = Boolean(hasPublishedPolicy && capKey && cap <= 0);
      const covered = Math.min(total, cap);
      const extra = Math.max(0, total - cap);
      comparison.push({
        category,
        label: categoryLabels[category] || category,
        total,
        cap,
        covered,
        extra,
        noPublishedCapForCategory,
      });
    }
  }

  const totalPackage = comparison.reduce((s, c) => s + c.total, 0);
  const totalCovered = comparison.reduce((s, c) => s + c.covered, 0);
  const totalExtra = comparison.reduce((s, c) => s + c.extra, 0);

  const fmt = (usd: number) => formatServicesMoney(convertUsdToDisplay(usd, displayCurrency), displayCurrency);

  return (
    <div className="space-y-8">
      {capsLoading && (
        <div
          role="status"
          aria-live="polite"
          aria-busy="true"
          className="flex items-center gap-3 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#475569]"
        >
          <div className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
          <span>Loading policy caps and cost comparison…</span>
        </div>
      )}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[#0b2b43]">My Relocation Service Package</h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onBack}>
            ← Edit selections
          </Button>
          <button onClick={onStartOver} className="text-sm text-[#0b2b43] hover:underline">
            Start over
          </button>
        </div>
      </div>

      {packageItems.length === 0 ? (
        <Card padding="lg">
          <p className="text-[#6b7280]">
            No items in your package yet. Go back and add recommendations to compare with your HR policy.
          </p>
          <Button className="mt-4" onClick={onBack}>
            Edit selections
          </Button>
        </Card>
      ) : (
        <>
          <Card padding="lg">
            <h3 className="font-semibold text-[#0b2b43] mb-4">Selected services</h3>
            <ul className="space-y-2">
              {packageItems.map(({ category, item }) => {
                const cost = item.metadata?.estimated_cost_usd;
                const costType = item.metadata?.cost_type || 'one_time';
                const costLabel =
                  formatEstimationFromUsd(cost, costType, displayCurrency) ?? '-';
                return (
                  <li key={`${category}-${item.item_id}`} className="flex justify-between py-2 border-b border-[#e2e8f0] last:border-0">
                    <span>
                      <strong>{item.name}</strong>
                      <span className="ml-2 text-sm text-[#6b7280]">
                        ({categoryLabels[category] || category})
                      </span>
                    </span>
                    <span className="font-medium text-[#0b2b43]">{costLabel}</span>
                  </li>
                );
              })}
            </ul>
          </Card>

          {hasPublishedPolicy && comparisonAvailable === false && packageItems.length > 0 && (
            <Card padding="lg" className="border-[#e2e8f0] bg-[#fafbfc]">
              <p className="text-[#4b5563] font-medium">{EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_PRIMARY}</p>
              <p className="text-sm text-[#6b7280] mt-2">{EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_SECONDARY}</p>
            </Card>
          )}

          {policyCaps && comparison.length > 0 && comparisonAvailable !== false && (
            <Card padding="lg">
              <h3 className="font-semibold text-[#0b2b43] mb-2">HR Policy Comparison</h3>
              <p className="text-sm text-[#6b7280] mb-2">
                Caps below are from your company&apos;s published policy. See how much your company covers vs. what you may pay out of pocket.
              </p>
              <p className="text-sm text-[#6b7280] mb-6">
                For full policy details, open <strong>Compensation &amp; Allowance</strong> or <strong>HR Policy</strong> in
                the menu. Limits below use the same published policy as those pages when a numeric cap is available for
                this service type.
              </p>

              {comparison.some((c) => c.noPublishedCapForCategory) && (
                <p className="text-sm text-[#92400e] bg-[#fffbeb] border border-[#fde68a] rounded-lg px-3 py-2 mb-4">
                  Where your employer has not published a matching numeric limit for a selected service category, we treat
                  the employer-covered amount as zero for this estimate so you can see the full cost. See your policy
                  pages for benefits that use allowances or non-cash support.
                </p>
              )}

              <div className="space-y-6 mb-8">
                {comparison.map((c) => (
                  <div key={c.category}>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="font-medium text-[#0b2b43]">{c.label}</span>
                      <span>
                        Total: {fmt(c.total)}
                        {c.cap > 0 && (
                          <span className="ml-2 text-[#6b7280]">
                            (Cap: {fmt(c.cap)})
                          </span>
                        )}
                      </span>
                    </div>
                    {c.noPublishedCapForCategory && (
                      <p className="text-xs text-[#b45309] mb-2">
                        No employer cap is modeled in ReloPass for this category — estimate shown as out-of-pocket unless
                        your formal policy says otherwise.
                      </p>
                    )}
                    <div className="h-8 flex rounded-lg overflow-hidden bg-[#e2e8f0]">
                      <div
                        className="bg-[#22c55e] flex items-center justify-end pr-2 transition-all"
                        style={{
                          width: c.total > 0 ? `${(c.covered / c.total) * 100}%` : '0%',
                          minWidth: c.covered > 0 ? 48 : 0,
                        }}
                      >
                        {c.covered > 0 && (
                          <span className="text-xs font-medium text-white">Covered</span>
                        )}
                      </div>
                      <div
                        className="bg-[#f97316] flex items-center pl-2 transition-all"
                        style={{
                          width: c.total > 0 ? `${(c.extra / c.total) * 100}%` : '0%',
                          minWidth: c.extra > 0 ? 48 : 0,
                        }}
                      >
                        {c.extra > 0 && (
                          <span className="text-xs font-medium text-white">Extra</span>
                        )}
                      </div>
                    </div>
                    <div className="flex justify-between text-xs text-[#6b7280] mt-1">
                      <span>Company covers: {fmt(c.covered)}</span>
                      {c.extra > 0 && (
                        <span className="text-[#f97316] font-medium">You pay: {fmt(c.extra)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-6 border-t border-[#e2e8f0] space-y-2">
                <div className="flex justify-between font-semibold text-[#0b2b43]">
                  <span>Total package cost</span>
                  <span>{fmt(totalPackage)}</span>
                </div>
                <div className="flex justify-between text-[#22c55e]">
                  <span>Company covered</span>
                  <span>{fmt(totalCovered)}</span>
                </div>
                {totalExtra > 0 && (
                  <div className="flex justify-between text-[#f97316] font-medium">
                    <span>Your out-of-pocket</span>
                    <span>{fmt(totalExtra)}</span>
                  </div>
                )}
              </div>
            </Card>
          )}

          {!policyCaps && comparisonAvailable !== false && !capsLoading && (
            <p className="text-sm text-[#6b7280]">
              Policy caps could not be loaded. Cost comparison is based on estimated values from recommendations. View &quot;Assignment Package &amp; Limits&quot; for your company&apos;s policy summary.
            </p>
          )}
          {!capsLoading && packageItems.length > 0 && (
            <p className="text-xs text-[#94a3b8]">{SERVICES_CURRENCY_FOOTNOTE}</p>
          )}
        </>
      )}
    </div>
  );
};

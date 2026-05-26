import React, { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import {
  listExceptionRequestsForCase,
  type ExceptionRequest,
} from '../../api/exceptions';
import { RequestExceptionModal } from '../exceptions/RequestExceptionModal';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';
import type { RecommendationResponse, RecommendationItem } from './types';
import {
  EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_PRIMARY,
  EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_SECONDARY,
} from '../policy/employeePolicyMessages';
import {
  convertToUsd,
  convertUsdToDisplay,
  formatEstimationFromUsd,
  formatServicesMoney,
  SERVICES_CURRENCY_FOOTNOTE,
} from '../services/servicesCurrency';
import { budgetAPI, type BudgetSummaryCategory } from '../../api/budget';

// AIQ-280 follow-up #4 — replaced the hardcoded CATEGORY_TO_CAP map with
// a runtime lookup driven by GET /api/cases/:caseId/budget-summary. The
// previous map was a 3-entry compile-time list (housing/movers/schools);
// the new approach keys directly by the backend category name so adding
// a category to a policy doesn't need a frontend code change.
//
// Categories on the recommendation side that don't have a backend cap
// (banks, insurance, electricity, etc.) map to "no_cap" naturally —
// categoryCaps.get(category) returns undefined and the comparison logic
// falls into the noCapMapping branch.

const CATEGORY_COST_TYPE: Record<string, 'monthly' | 'annual' | 'one_time'> = {
  housing: 'monthly',
  schools: 'annual',
  movers: 'one_time',
};

/** Build a category-name → USD-cap map from a BudgetSummary response. */
function budgetSummaryToCategoryCaps(
  categories: BudgetSummaryCategory[] | null | undefined,
): Map<string, number> {
  const out = new Map<string, number>();
  if (!categories) return out;
  for (const c of categories) {
    if (c.cap_amount == null) continue;
    // Caps come back in the policy's native currency; PackageSummary's
    // comparison logic expects USD baseline (matches the recommendation
    // items' estimated_cost_usd). Convert here so the existing math
    // stays correct.
    const usd = convertToUsd(c.cap_amount, c.cap_currency || 'USD');
    out.set(c.name, usd);
    // Accept the 'moving' alias the backend can emit alongside 'movers'.
    if (c.name === 'moving') out.set('movers', usd);
    if (c.name === 'movers') out.set('moving', usd);
  }
  return out;
}

function getItemCost(item: RecommendationItem, costType: string): number {
  const usd = item.metadata?.estimated_cost_usd;
  if (usd == null) return 0;
  if (costType === 'monthly') return usd;
  if (costType === 'annual') return usd;
  return usd;
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
  // AIQ-280 follow-up #4 — categoryCaps is keyed by backend category name
  // (e.g. 'housing', 'movers', 'schools') and stores per-category USD caps.
  // Replaces the old PolicyCaps shape (housing_monthly_usd / movers_usd /
  // schools_usd) which required a hardcoded mapping.
  const [categoryCaps, setCategoryCaps] = useState<Map<string, number> | null>(null);
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

    // Helper: convert the legacy PolicyCaps shape (USD numerics) into the
    // categoryCaps Map shape the new comparison loop expects. Used by the
    // company-default fallback path below.
    const fromPolicyCaps = (c: { housing_monthly_usd: number; movers_usd: number; schools_usd: number } | null): Map<string, number> | null => {
      if (!c) return null;
      const m = new Map<string, number>();
      if (c.housing_monthly_usd) m.set('housing', c.housing_monthly_usd);
      if (c.movers_usd) {
        m.set('movers', c.movers_usd);
        m.set('moving', c.movers_usd);
      }
      if (c.schools_usd) m.set('schools', c.schools_usd);
      return m;
    };

    const run = async () => {
      try {
        if (assignmentId) {
          try {
            // AIQ-280 follow-up #4 — primary path is the new budget-summary
            // endpoint. Returns categories keyed by backend service name with
            // cap_amount in the policy's native currency.
            const res = await budgetAPI.getBudgetSummary(assignmentId);
            if (cancelled) return;
            const caps = budgetSummaryToCategoryCaps(res?.categories);
            const anyCap = Array.from(caps.values()).some((v) => v > 0);
            setHasPublishedPolicy(anyCap);
            setComparisonAvailable(true);
            if (caps.size > 0) {
              setCategoryCaps(caps);
              return;
            }
            // Empty categories — fall through to company-defaults.
            const c = await employeeAPI.getPolicyCaps();
            if (!cancelled) setCategoryCaps(fromPolicyCaps(c));
          } catch {
            if (cancelled) return;
            setComparisonAvailable(null);
            setHasPublishedPolicy(false);
            try {
              const c = await employeeAPI.getPolicyCaps();
              if (!cancelled) setCategoryCaps(fromPolicyCaps(c));
            } catch {
              if (!cancelled) setCategoryCaps(null);
            }
          }
        } else {
          setComparisonAvailable(null);
          setHasPublishedPolicy(false);
          try {
            const c = await employeeAPI.getPolicyCaps();
            if (!cancelled) setCategoryCaps(fromPolicyCaps(c));
          } catch {
            if (!cancelled) setCategoryCaps(null);
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

  type CapStatus = 'within' | 'over' | 'not_capped';
  const comparison: {
    category: string;
    label: string;
    total: number;
    cap: number;
    covered: number;
    extra: number;
    /** Published policy exists but no numeric cap for this service category — treat as uncovered for estimates. */
    noPublishedCapForCategory: boolean;
    /** No cap available for this category at all (e.g. banks/insurance/electricity have no policy entry). */
    noCapMapping: boolean;
    status: CapStatus;
  }[] = [];
  if (categoryCaps) {
    for (const { category, item } of packageItems) {
      const costType = CATEGORY_COST_TYPE[category] || 'one_time';
      const total = getItemCost(item, costType);
      // AIQ-280 follow-up #4 — direct category-name lookup instead of the
      // old hardcoded CATEGORY_TO_CAP intermediate. categoryCaps stores
      // USD-normalised caps (currency conversion happened in the adapter).
      const capLookup = categoryCaps.get(category);
      const cap = capLookup ?? 0;
      const noCapMapping = capLookup === undefined;
      const noPublishedCapForCategory = Boolean(hasPublishedPolicy && !noCapMapping && cap <= 0);
      const covered = Math.min(total, cap);
      const extra = Math.max(0, total - cap);
      const status: CapStatus =
        noCapMapping || cap <= 0 ? 'not_capped' : extra > 0 ? 'over' : 'within';
      comparison.push({
        category,
        label: categoryLabels[category] || category,
        total,
        cap,
        covered,
        extra,
        noPublishedCapForCategory,
        noCapMapping,
        status,
      });
    }
  }

  const viewerRole = useMemo(() => normalizeStoredRole(getAuthItem('relopass_role')), []);
  const isHrViewer = viewerRole === 'HR' || viewerRole === 'ADMIN';
  const isEmployeeViewer = viewerRole === 'EMPLOYEE';

  // Existing exception requests on this case, keyed by category. Refresh after
  // any new request the employee submits. Demo simplification: we use the
  // assignment id as the case_id surrogate — the backend stores it as TEXT and
  // the prod migration FK to mobility_cases will be wired in T1.4 follow-up.
  const [exceptionsByCategory, setExceptionsByCategory] = useState<
    Map<string, ExceptionRequest>
  >(new Map());
  const [modalState, setModalState] = useState<{
    category: string;
    label: string;
    requestedUsd: number;
    capUsd: number;
  } | null>(null);

  const [exceptionRows, setExceptionRows] = useState<ExceptionRequest[]>([]);
  const [exceptionsRefreshNonce, setExceptionsRefreshNonce] = useState(0);
  useEffect(() => {
    if (!assignmentId) return;
    let cancelled = false;
    listExceptionRequestsForCase(assignmentId)
      .then((rows) => {
        if (cancelled) return;
        setExceptionRows(rows);
        const next = new Map<string, ExceptionRequest>();
        // Most recent (server returns DESC) wins per category.
        for (const row of rows) {
          if (!next.has(row.category)) next.set(row.category, row);
        }
        setExceptionsByCategory(next);
      })
      .catch(() => {
        // Non-fatal — the page still works without exception status.
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId, exceptionsRefreshNonce]);

  // Re-fetch when the user comes back to this tab so HR's decisions show
  // up without requiring a hard refresh.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        setExceptionsRefreshNonce((n) => n + 1);
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  const EXCEPTION_BADGE: Record<
    ExceptionRequest['status'],
    { label: string; className: string }
  > = {
    pending: {
      label: 'Exception pending HR review',
      className: 'bg-[#fef9c3] text-[#854d0e] border-[#fde68a]',
    },
    approved: {
      label: 'Exception approved by HR',
      className: 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]',
    },
    rejected: {
      label: 'Exception rejected',
      className: 'bg-[#fee2e2] text-[#991b1b] border-[#fecaca]',
    },
  };

  const STATUS_BADGE: Record<CapStatus, { label: string; className: string }> = {
    within: {
      label: 'Within cap',
      className: 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]',
    },
    over: {
      label: 'Over cap',
      className: 'bg-[#ffedd5] text-[#9a3412] border-[#fed7aa]',
    },
    not_capped: {
      label: 'Not capped',
      className: 'bg-[#f1f5f9] text-[#475569] border-[#e2e8f0]',
    },
  };

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

      {exceptionRows.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-[#0b2b43]">Your exception requests</h3>
            <button
              type="button"
              onClick={() => setExceptionsRefreshNonce((n) => n + 1)}
              className="text-xs text-[#0b2b43] hover:underline"
            >
              Refresh
            </button>
          </div>
          <p className="text-sm text-[#6b7280] mb-3">
            Saved with your case. The decision shows here even if you re-build your shortlist.
          </p>
          <ul className="space-y-3">
            {exceptionRows.map((row) => {
              const badge = EXCEPTION_BADGE[row.status];
              return (
                <li
                  key={row.id}
                  className="rounded-lg border border-[#e2e8f0] bg-white p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[#0b2b43] capitalize">
                          {categoryLabels[row.category] || row.category}
                        </span>
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </div>
                      <div className="mt-1 text-sm text-[#334155]">
                        Requested {fmt(row.requested_amount)} vs cap {fmt(row.cap_amount)}
                      </div>
                      <p className="mt-2 whitespace-pre-line text-sm text-[#475569]">
                        Your reason: {row.reason}
                      </p>
                      {row.hr_note && (
                        <p className="mt-1 text-sm text-[#0b2b43]">
                          <span className="font-medium">HR note:</span> {row.hr_note}
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

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

          {categoryCaps && comparison.length > 0 && comparisonAvailable !== false && (
            <Card padding="lg">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <h3 className="font-semibold text-[#0b2b43]">HR Policy Comparison</h3>
                {isHrViewer && (
                  <span className="inline-flex items-center rounded-full border border-[#bfdbfe] bg-[#eff6ff] px-2 py-0.5 text-xs font-medium text-[#1d4ed8]">
                    HR view — same numbers the employee sees
                  </span>
                )}
              </div>
              <p className="text-sm text-[#6b7280] mb-2">
                Caps below are from your company&apos;s published policy. See how much your company covers vs. what you may pay out of pocket.
              </p>
              <p className="text-sm text-[#6b7280] mb-6">
                For full policy details, open <strong>Compensation &amp; Allowance</strong> or <strong>HR Policy</strong> in
                the menu. Limits below use the same published policy as those pages when a numeric cap is available for
                this service type.
              </p>

              {comparison.some((c) => c.noPublishedCapForCategory || c.noCapMapping) && (
                <p className="text-sm text-[#92400e] bg-[#fffbeb] border border-[#fde68a] rounded-lg px-3 py-2 mb-4">
                  Where your employer has not published a matching numeric limit for a selected service category, we treat
                  the employer-covered amount as zero for this estimate so you can see the full cost. See your policy
                  pages for benefits that use allowances or non-cash support.
                </p>
              )}

              <div className="space-y-6 mb-8">
                {comparison.map((c) => {
                  const badge = STATUS_BADGE[c.status];
                  return (
                    <div key={c.category}>
                      <div className="flex flex-wrap items-center justify-between gap-2 text-sm mb-2">
                        <span className="flex items-center gap-2">
                          <span className="font-medium text-[#0b2b43]">{c.label}</span>
                          <span
                            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${badge.className}`}
                          >
                            {badge.label}
                          </span>
                        </span>
                        <span>
                          Total: {fmt(c.total)}
                          {c.cap > 0 && (
                            <span className="ml-2 text-[#6b7280]">
                              (Cap: {fmt(c.cap)})
                            </span>
                          )}
                        </span>
                      </div>
                      {c.noCapMapping && hasPublishedPolicy && (
                        <p className="text-xs text-[#475569] mb-2">
                          Not capped by your employer policy in ReloPass — this category is shown as fully out-of-pocket
                          for the estimate.
                        </p>
                      )}
                      {c.noPublishedCapForCategory && (
                        <p className="text-xs text-[#b45309] mb-2">
                          No employer cap is modeled in ReloPass for this category — estimate shown as out-of-pocket unless
                          your formal policy says otherwise.
                        </p>
                      )}
                      {c.cap > 0 ? (
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
                      ) : (
                        <div className="h-8 flex items-center justify-end rounded-lg bg-[#f1f5f9] px-2">
                          <span className="text-xs font-medium text-[#475569]">No cap published</span>
                        </div>
                      )}
                      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-[#6b7280] mt-1">
                        <span>Company covers: {fmt(c.covered)}</span>
                        {c.extra > 0 && (
                          <span className="text-[#f97316] font-medium">You pay: {fmt(c.extra)}</span>
                        )}
                        {(() => {
                          const existing = exceptionsByCategory.get(c.category);
                          if (existing) {
                            const badge = EXCEPTION_BADGE[existing.status];
                            return (
                              <span
                                className={`ml-auto inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${badge.className}`}
                                title={existing.hr_note || undefined}
                              >
                                {badge.label}
                              </span>
                            );
                          }
                          if (isEmployeeViewer && c.status === 'over' && assignmentId) {
                            return (
                              <button
                                type="button"
                                onClick={() =>
                                  setModalState({
                                    category: c.category,
                                    label: c.label,
                                    requestedUsd: c.total,
                                    capUsd: c.cap,
                                  })
                                }
                                className="ml-auto inline-flex items-center rounded-md border border-[#0b2b43] bg-white px-2 py-1 text-xs font-medium text-[#0b2b43] hover:bg-[#eef4f8]"
                              >
                                Request exception
                              </button>
                            );
                          }
                          if (isHrViewer) {
                            return (
                              <span
                                className="ml-auto text-xs text-[#94a3b8]"
                                title="Resolve in HR Command Center → Exceptions queue."
                              >
                                Resolve in HR queue
                              </span>
                            );
                          }
                          return null;
                        })()}
                      </div>
                    </div>
                  );
                })}
              </div>

              {modalState && assignmentId && (
                <RequestExceptionModal
                  open
                  onClose={() => setModalState(null)}
                  onSuccess={(req) => {
                    setExceptionsByCategory((prev) => {
                      const next = new Map(prev);
                      next.set(req.category, req);
                      return next;
                    });
                    setModalState(null);
                  }}
                  caseId={assignmentId}
                  category={modalState.category}
                  categoryLabel={modalState.label}
                  requestedAmountUsd={modalState.requestedUsd}
                  capAmountUsd={modalState.capUsd}
                  displayRequested={fmt(modalState.requestedUsd)}
                  displayCap={fmt(modalState.capUsd)}
                />
              )}

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

          {!categoryCaps && comparisonAvailable !== false && !capsLoading && (
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

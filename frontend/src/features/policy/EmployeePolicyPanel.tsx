/**
 * Employee-facing read-only policy + entitlements, with maturity-aware copy and optional service comparison.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Card } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import type { EffectiveServiceComparisonRow, PolicyServiceComparisonItem } from '../../types';
import { buildRoute } from '../../navigation/routes';
import { formatBenefitLabel } from './benefitCategories';
import {
  EMPLOYEE_POLICY_LOADING_ASSIGNMENT,
  EMPLOYEE_HR_POLICY_WAIT_PRIMARY,
  EMPLOYEE_HR_POLICY_WAIT_SECONDARY,
} from './employeePolicyMessages';
import {
  EMPLOYEE_POLICY_PANEL_FULL_BODY,
  EMPLOYEE_POLICY_PANEL_FULL_TITLE,
  EMPLOYEE_POLICY_PANEL_INFO_ONLY_BADGE,
  EMPLOYEE_POLICY_PANEL_INFO_ONLY_HINT,
  EMPLOYEE_POLICY_PANEL_NO_POLICY_BODY,
  EMPLOYEE_POLICY_PANEL_NO_POLICY_TITLE,
  EMPLOYEE_POLICY_PANEL_NO_SELECTIONS,
  EMPLOYEE_POLICY_PANEL_PARTIAL_BODY,
  EMPLOYEE_POLICY_PANEL_PARTIAL_TITLE,
  EMPLOYEE_POLICY_PANEL_UNDER_REVIEW_BODY,
  EMPLOYEE_POLICY_PANEL_UNDER_REVIEW_TITLE,
} from './employeePolicyPanelCopy';
import {
  deriveBenefitRowStatus,
  deriveEmployeePolicyMaturity,
  employeeLabelForBenefitStatus,
  formatBenefitCapLine,
  formatPolicyLimitSnapshot,
  formatSelectedSnapshot,
  labelForCoverageStatus,
  labelForEngineComparisonStatus,
  labelForLegacyPolicyStatus,
  labelForServiceKey,
  type PackBenefitRow,
} from './employeePolicyPanelModel';

export type AssignmentPackagePolicyPayload = Awaited<ReturnType<typeof employeeAPI.getMyAssignmentPackagePolicy>>;

function formatDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return String(val);
  }
}

function MaturityBanner({
  maturity,
}: {
  maturity: 'no_policy' | 'under_review' | 'partial_comparison' | 'full_comparison';
}) {
  const styles: Record<string, string> = {
    no_policy: 'bg-slate-50 border-slate-200 text-slate-800',
    under_review: 'bg-sky-50 border-sky-200 text-sky-950',
    partial_comparison: 'bg-amber-50/90 border-amber-200 text-amber-950',
    full_comparison: 'bg-emerald-50 border-emerald-200 text-emerald-950',
  };
  const titles: Record<string, string> = {
    no_policy: EMPLOYEE_POLICY_PANEL_NO_POLICY_TITLE,
    under_review: EMPLOYEE_POLICY_PANEL_UNDER_REVIEW_TITLE,
    partial_comparison: EMPLOYEE_POLICY_PANEL_PARTIAL_TITLE,
    full_comparison: EMPLOYEE_POLICY_PANEL_FULL_TITLE,
  };
  const bodies: Record<string, string> = {
    no_policy: EMPLOYEE_POLICY_PANEL_NO_POLICY_BODY,
    under_review: EMPLOYEE_POLICY_PANEL_UNDER_REVIEW_BODY,
    partial_comparison: EMPLOYEE_POLICY_PANEL_PARTIAL_BODY,
    full_comparison: EMPLOYEE_POLICY_PANEL_FULL_BODY,
  };
  return (
    <div className={`rounded-lg border px-4 py-3 ${styles[maturity]}`}>
      <div className="text-sm font-semibold">{titles[maturity]}</div>
      <p className="text-sm mt-1.5 leading-relaxed opacity-95">{bodies[maturity]}</p>
    </div>
  );
}

function ReadOnlyRow({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm text-slate-800">
      <div className="font-medium text-slate-900">{title}</div>
      {subtitle && <div className="text-xs text-slate-600 mt-0.5">{subtitle}</div>}
      <div className="mt-2 space-y-1 text-sm text-slate-700">{children}</div>
    </div>
  );
}

function BenefitEntitlementRow({ b }: { b: PackBenefitRow }) {
  const status = deriveBenefitRowStatus(b);
  const cap = formatBenefitCapLine(b);
  const evid = (b.evidence_required_json || []).filter(Boolean);
  const excl = (b.exclusions_json || []).map((e) => e.description || e.domain).filter(Boolean);
  return (
    <ReadOnlyRow title={formatBenefitLabel(b.benefit_key)} subtitle={employeeLabelForBenefitStatus(status)}>
      {cap && (
        <div>
          <span className="text-slate-500">Limit: </span>
          {cap}
        </div>
      )}
      {!cap && status !== 'excluded' && (
        <div className="text-slate-600">
          {EMPLOYEE_POLICY_PANEL_INFO_ONLY_BADGE} — no numeric cap is shown for this item in ReloPass.
        </div>
      )}
      {b.approval_required && (
        <div>
          <span className="text-slate-500">Approval: </span>Your employer requires approval before this benefit is used.
        </div>
      )}
      {b.condition_summary && (
        <div>
          <span className="text-slate-500">Notes: </span>
          {b.condition_summary}
        </div>
      )}
      {excl.length > 0 && (
        <div className="text-amber-900/90">
          <span className="text-slate-500">Applies with exceptions: </span>
          {excl.join(' · ')}
        </div>
      )}
      {evid.length > 0 && (
        <div>
          <span className="text-slate-500">Documentation: </span>
          {evid.join(', ')}
        </div>
      )}
    </ReadOnlyRow>
  );
}

function EffectiveComparisonRow({
  row,
  showInfoStamp,
}: {
  row: EffectiveServiceComparisonRow;
  showInfoStamp: boolean;
}) {
  const title = labelForServiceKey(row.service_key);
  const limit = formatPolicyLimitSnapshot(row.policy_limit_snapshot || {});
  const selected = formatSelectedSnapshot(row.selected_value_snapshot || {});
  const cmpLabel = labelForEngineComparisonStatus(row.comparison_status);
  const covLabel = labelForCoverageStatus(row.coverage_status);
  const showNumeric =
    row.delta != null &&
    row.comparison_status !== 'not_enough_policy_data' &&
    row.comparison_status !== 'information_only';

  return (
    <ReadOnlyRow
      title={title}
      subtitle={`${covLabel} · ${cmpLabel}${showInfoStamp ? ` · ${EMPLOYEE_POLICY_PANEL_INFO_ONLY_BADGE}` : ''}`}
    >
      {limit && (
        <div>
          <span className="text-slate-500">Policy limit (as modeled): </span>
          {limit}
        </div>
      )}
      {selected && (
        <div>
          <span className="text-slate-500">Your estimate: </span>
          {selected}
        </div>
      )}
      {showNumeric && (
        <div>
          <span className="text-slate-500">Difference vs limit: </span>
          {row.delta != null && row.delta > 0 ? `Over by ${row.delta.toLocaleString()}` : `Within limit`}
        </div>
      )}
      <div className="text-slate-700">{row.explanation}</div>
      {row.approval_required && (
        <div className="text-slate-600">Approval may be required under your employer&apos;s rules.</div>
      )}
      {showInfoStamp && <p className="text-xs text-slate-500 mt-2">{EMPLOYEE_POLICY_PANEL_INFO_ONLY_HINT}</p>}
    </ReadOnlyRow>
  );
}

function LegacyComparisonRow({ item }: { item: PolicyServiceComparisonItem }) {
  const capParts = [item.policy_max_value ?? item.policy_standard_value ?? item.policy_min_value]
    .filter((v) => v != null)
    .map((v) => `${item.currency || 'USD'} ${Number(v).toLocaleString()}`);
  return (
    <ReadOnlyRow title={item.label || labelForServiceKey(item.service_category)} subtitle={labelForLegacyPolicyStatus(item.policy_status)}>
      {capParts.length > 0 && (
        <div>
          <span className="text-slate-500">Policy limit: </span>
          {capParts[0]}
        </div>
      )}
      <div>{item.explanation}</div>
      {item.approval_required && <div className="text-slate-600">Approval required under policy.</div>}
    </ReadOnlyRow>
  );
}

export const EmployeePolicyPanel: React.FC<{
  pack: AssignmentPackagePolicyPayload | null;
  loading: boolean;
}> = ({ pack, loading }) => {
  const [comp, setComp] = useState<Awaited<ReturnType<typeof employeeAPI.getPolicyServiceComparison>> | null>(null);
  const [compLoading, setCompLoading] = useState(false);

  const assignmentId = pack?.assignment_id ? String(pack.assignment_id) : null;
  const shouldFetchComp = pack?.status === 'found' && Boolean(assignmentId);

  useEffect(() => {
    if (!shouldFetchComp || !assignmentId) {
      setComp(null);
      return;
    }
    let cancelled = false;
    setCompLoading(true);
    employeeAPI
      .getPolicyServiceComparison(assignmentId)
      .then((res) => {
        if (!cancelled) setComp(res);
      })
      .catch(() => {
        if (!cancelled) setComp(null);
      })
      .finally(() => {
        if (!cancelled) setCompLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [shouldFetchComp, assignmentId]);

  const benefits = useMemo(() => (Array.isArray(pack?.benefits) ? (pack!.benefits as PackBenefitRow[]) : []), [pack?.benefits]);

  const effectiveRows = comp?.effective_service_comparison ?? [];

  const maturity = useMemo(() => {
    if (!pack || pack.status !== 'found') return 'no_policy' as const;
    const hasPolicy = pack.has_policy !== false && Boolean(pack.policy && (pack.policy as { id?: string }).id);
    const compAvail = pack.comparison_available === true || comp?.comparison_available === true;
    const readiness = pack.comparison_readiness || comp?.comparison_readiness || null;
    return deriveEmployeePolicyMaturity({
      hasPolicy,
      comparisonAvailable: compAvail,
      readiness,
      benefitsCount: benefits.length,
      effectiveRowsCount: effectiveRows.length,
    });
  }, [pack, comp?.comparison_available, comp?.comparison_readiness, benefits.length, effectiveRows.length]);

  if (loading) {
    return (
      <Card padding="lg" className="border-[#e2e8f0]">
        <div role="status" aria-live="polite">
          <p className="text-sm font-medium text-[#0b2b43]">{EMPLOYEE_POLICY_LOADING_ASSIGNMENT}</p>
          <p className="text-xs text-[#6b7280] mt-2">This usually finishes in a few seconds.</p>
        </div>
      </Card>
    );
  }

  if (!pack || pack.status === 'error') {
    return (
      <Card padding="lg" className="border-slate-200 bg-slate-50/50">
        <p className="text-sm text-slate-800 font-medium">We couldn&apos;t load this page right now</p>
        <p className="text-sm text-slate-600 mt-2">
          {pack?.message || 'Please refresh the page or try again shortly. Your assignment is unchanged.'}
        </p>
      </Card>
    );
  }

  if (pack.status === 'no_assignment') {
    return (
      <Card padding="lg" className="border-slate-200 bg-white">
        <p className="text-slate-700">
          You don&apos;t have an active assignment yet. When HR links you to a case, your published policy and limits
          will show here.
        </p>
      </Card>
    );
  }

  if (pack.status === 'no_policy_found') {
    return (
      <div className="space-y-4">
        <MaturityBanner maturity="no_policy" />
        <Card padding="lg" className="border-slate-200 bg-white">
          <p className="text-slate-700">{pack.message || EMPLOYEE_HR_POLICY_WAIT_PRIMARY}</p>
          <p className="text-sm text-slate-600 mt-2">{pack.message_secondary || EMPLOYEE_HR_POLICY_WAIT_SECONDARY}</p>
        </Card>
        <Link to={buildRoute('services')}>
          <Button variant="outline">Back to Services</Button>
        </Link>
      </div>
    );
  }

  const policy = pack.policy as {
    id?: string;
    title?: string;
    version?: number;
    effective_date?: string;
    company_name?: string | null;
  } | null;

  const ctx = (pack.resolution_context || {}) as { assignment_type?: string; family_status?: string; tier?: string };
  const assignmentTypeLabel = ctx.assignment_type ? String(ctx.assignment_type).replace(/_/g, ' ') : null;

  const showInfoStamp = maturity === 'under_review' || maturity === 'partial_comparison';
  const legacyComparisons = Array.isArray(comp?.comparisons) ? comp!.comparisons : [];

  return (
    <div className="space-y-6">
      <MaturityBanner maturity={maturity} />

      {compLoading && (
        <p className="text-xs text-slate-500" role="status">
          Updating selections and comparisons…
        </p>
      )}

      {policy?.title && (
        <Card padding="lg" className="border-slate-200 bg-white">
          <div className="text-sm font-semibold text-slate-900">{policy.title}</div>
          {policy.company_name && <div className="text-sm text-slate-600 mt-1">Company: {policy.company_name}</div>}
          <div className="text-sm text-slate-600 mt-2 flex flex-wrap gap-x-3 gap-y-1">
            {assignmentTypeLabel && <span className="capitalize">Assignment: {assignmentTypeLabel}</span>}
            <span>Effective: {formatDate(policy.effective_date)}</span>
            {policy.version != null && <span>Version {policy.version}</span>}
          </div>
          <p className="text-sm text-slate-600 mt-3">
            Read-only summary for your assignment. For questions about interpretation or exceptions, contact HR through
            Messages.
          </p>
        </Card>
      )}

      {benefits.length > 0 && (
        <section aria-labelledby="employee-policy-entitlements-heading">
          <h2 id="employee-policy-entitlements-heading" className="text-sm font-semibold text-slate-900 mb-3">
            Entitlements from your policy
          </h2>
          {showInfoStamp && (
            <p className="text-xs text-slate-600 mb-3">{EMPLOYEE_POLICY_PANEL_INFO_ONLY_HINT}</p>
          )}
          <div className="space-y-3">
            {benefits.map((b) => (
              <BenefitEntitlementRow key={b.benefit_key} b={b} />
            ))}
          </div>
        </section>
      )}

      {benefits.length === 0 && maturity !== 'no_policy' && (
        <Card padding="lg" className="border-slate-200 bg-white">
          <p className="text-sm text-slate-700">
            {maturity === 'under_review'
              ? 'Detailed benefit rows are not shown yet because your policy is not in a comparison-ready shape in ReloPass. HR can complete the required categories and limits.'
              : 'No individual benefit rows were returned for your profile in this view. If you believe this is wrong, contact HR.'}
          </p>
        </Card>
      )}

      {effectiveRows.length > 0 && (
        <section aria-labelledby="employee-policy-services-heading">
          <h2 id="employee-policy-services-heading" className="text-sm font-semibold text-slate-900 mb-3">
            Your selected services vs policy
          </h2>
          <p className="text-xs text-slate-600 mb-3">
            {maturity === 'full_comparison'
              ? 'Based on services you selected and any estimates you entered where ReloPass can compare them safely.'
              : EMPLOYEE_POLICY_PANEL_INFO_ONLY_HINT}
          </p>
          <div className="space-y-3">
            {effectiveRows.map((row, i) => (
              <EffectiveComparisonRow key={`${row.service_key}-${i}`} row={row} showInfoStamp={showInfoStamp} />
            ))}
          </div>
        </section>
      )}

      {maturity === 'full_comparison' && legacyComparisons.length > 0 && (
        <section aria-labelledby="employee-policy-legacy-comp-heading">
          <h2 id="employee-policy-legacy-comp-heading" className="text-sm font-semibold text-slate-900 mb-3">
            Additional service checks
          </h2>
          <div className="space-y-3">
            {legacyComparisons.map((item, i) => (
              <LegacyComparisonRow key={`${item.service_category}-${i}`} item={item} />
            ))}
          </div>
        </section>
      )}

      {effectiveRows.length === 0 && legacyComparisons.length === 0 && maturity === 'full_comparison' && (
        <Card padding="lg" className="border-slate-200 bg-slate-50/50">
          <p className="text-sm text-slate-700">{EMPLOYEE_POLICY_PANEL_NO_SELECTIONS}</p>
        </Card>
      )}

      {comp?.message && maturity !== 'full_comparison' && (
        <p className="text-xs text-slate-600">{comp.message}</p>
      )}

      <Link to={buildRoute('services')}>
        <Button variant="outline">Back to Services</Button>
      </Link>
    </div>
  );
};

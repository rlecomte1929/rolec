/**
 * Single source of truth for the employee-side policy view.
 *
 * Renders the same theme accordion HR sees on /hr/policy under
 * "What employees see today", but driven by the employee-scoped
 * `/api/employee/policy-config` endpoint. The endpoint already:
 *   - filters to `covered === true` (no excluded rows leak through)
 *   - matches the employee's assignment_type + family_status
 *   - returns the latest published version (auto-updates when HR
 *     republishes — no client-side cache to bust)
 *
 * Used by:
 *   - EmployeePolicyPage (route /employee/policy)
 *   - HrPolicy dispatcher when role === EMPLOYEE (route /hr/policy)
 *
 * Self-contained: owns its own data fetch + URL-param resolution.
 * Renders body only (no AppShell, no Container) so the parent page
 * controls the page chrome.
 */
import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { Alert, Button, Card } from '../../components/antigravity';
import { employeeAPI, policyConfigMatrixAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import type {
  PolicyConfigBenefitRow,
  PolicyConfigCategoryBlock,
  PolicyConfigWorkingPayload,
} from '../policy-config/types';
import { POLICY_CONFIG_CATEGORIES } from '../policy-config/constants';
import {
  humanizeAssignmentTypeLabel,
  humanizeFamilyStatusLabel,
  normalizeAssignmentType,
  normalizeFamilyStatus,
} from '../policy-config/policyTargeting';
import {
  EMPLOYEE_POLICY_PER_BENEFIT_EXPLANATION,
  formatBenefitBudgetSummary,
  humanizeUnitFrequency,
  mergeNotesAndConditions,
} from '../../pages/employee/employeePolicyMatrixDisplay';
import { glossaryIdForBenefitKey } from '../policy-config/compensationGlossary';
import { PolicyGlossarySection } from '../policy-config/PolicyGlossarySection';
import { TermHelpIcon } from '../policy-config/TermHelpIcon';
import { PolicyTopicSummaryList } from './PolicyTopicSummaryList';
import { referenceToElementId } from './policyAssistantCitations';

type ServicesPolicyContext = Awaited<ReturnType<typeof employeeAPI.getServicesPolicyContext>>;

const EMPTY_UNPUBLISHED =
  'Your company has not yet published a policy for this assignment.';

type EmployeePolicyPayload = {
  has_policy_config?: boolean;
  effective_date?: string | null;
  policy_version?: string | null;
  version_number?: number | null;
  categories?: PolicyConfigCategoryBlock[];
  message?: string;
  assignment_context?: { assignment_type?: string | null; family_status?: string | null };
};

function countBenefits(cats: PolicyConfigCategoryBlock[] | undefined): number {
  return (cats ?? []).reduce((acc, c) => acc + (c.benefits?.length ?? 0), 0);
}

function BenefitReadOnlyCard({ b }: { b: PolicyConfigBenefitRow }) {
  const budget = formatBenefitBudgetSummary(b);
  const unit = humanizeUnitFrequency(b.unit_frequency);
  const notesBlock = mergeNotesAndConditions(b);
  const glossaryId = glossaryIdForBenefitKey(b.benefit_key);
  const sourceRef = b.id ? `policy_config_benefits.${b.id}` : undefined;
  // Anchor for Policy Assistant citation deep-linking. The backend
  // returns evidence.reference == benefit_key for matrix-derived rows;
  // mirroring that as both an id and a data attribute lets either
  // lookup path resolve.
  const policyAnchorId = b.benefit_key ? referenceToElementId(b.benefit_key) : undefined;

  return (
    <li
      id={policyAnchorId}
      className="rounded-xl border border-[#e2e8f0] bg-white p-5 shadow-sm"
      data-policy-source-ref={sourceRef}
      data-policy-reference={b.benefit_key || undefined}
    >
      <h3 className="text-base font-semibold text-[#0b2b43] leading-snug flex flex-wrap items-center gap-1.5">
        <span>{b.benefit_label || 'Benefit'}</span>
        {glossaryId ? <TermHelpIcon glossaryId={glossaryId} /> : null}
      </h3>

      <dl className="mt-4 space-y-3 text-sm">
        {budget && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-[#64748b]">Maximum budget / cap</dt>
            <dd className="mt-0.5 text-[#1e293b]">{budget}</dd>
          </div>
        )}
        {unit && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-[#64748b]">How often it applies</dt>
            <dd className="mt-0.5 text-[#1e293b] capitalize">{unit}</dd>
          </div>
        )}
        {notesBlock && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-[#64748b]">Notes &amp; conditions</dt>
            <dd className="mt-0.5 text-[#475569] whitespace-pre-wrap leading-relaxed">{notesBlock}</dd>
          </div>
        )}
      </dl>

      <p className="mt-4 text-xs text-[#64748b] leading-relaxed border-t border-[#f1f5f9] pt-3">
        {EMPLOYEE_POLICY_PER_BENEFIT_EXPLANATION}
      </p>
    </li>
  );
}

export type EmployeePolicyViewProps = {
  /** Caller may already have an assignment id from context — passing it
   *  here skips the URL-param fallback. */
  assignmentIdOverride?: string | null;
};

export const EmployeePolicyView: React.FC<EmployeePolicyViewProps> = ({
  assignmentIdOverride,
}) => {
  const [searchParams] = useSearchParams();
  const { assignmentId: contextAssignmentId, linkedCount, isLoading: assignmentLoading } = useEmployeeAssignment();
  const assignmentId =
    assignmentIdOverride ??
    searchParams.get('assignmentId') ??
    contextAssignmentId ??
    undefined;

  const caseId = searchParams.get('caseId') || undefined;
  const assignmentTypeRaw = searchParams.get('assignmentType');
  const familyStatusRaw = searchParams.get('familyStatus');
  const assignmentType = normalizeAssignmentType(assignmentTypeRaw ?? '') ?? undefined;
  const familyStatus = normalizeFamilyStatus(familyStatusRaw ?? '') ?? undefined;

  // Don't attempt a network call if there's nothing to load against — the
  // early-return above already handles the no-assignment UI state.
  const hasPolicyParams = Boolean(assignmentId || caseId || assignmentType || familyStatus);

  const policyQuery = useQuery({
    queryKey: ['employee', 'policy-config', { assignmentId, caseId, assignmentType, familyStatus }],
    queryFn: () =>
      policyConfigMatrixAPI.employeeGet({
        assignmentId: assignmentId ?? undefined,
        caseId,
        assignmentType,
        familyStatus,
      }),
    enabled: hasPolicyParams,
  });
  const data: EmployeePolicyPayload | null = policyQuery.data ?? null;
  const loading = policyQuery.isLoading;
  const error = policyQuery.isError
    ? 'We could not load your compensation policy right now. Please try again later.'
    : null;

  const servicesCtxQuery = useQuery({
    queryKey: ['employee', 'services-policy-context', assignmentId],
    queryFn: () => employeeAPI.getServicesPolicyContext(assignmentId as string),
    enabled: Boolean(assignmentId),
  });
  const servicesPolicyCtx: ServicesPolicyContext | null = servicesCtxQuery.data ?? null;

  const categoryOrder = useMemo(
    () => new Map(POLICY_CONFIG_CATEGORIES.map((c, i) => [c.key, i])),
    []
  );

  const sortedCategories = useMemo(() => {
    const list = [...(data?.categories ?? [])].sort(
      (a, b) =>
        (categoryOrder.get(a.category_key || '') ?? 99) -
        (categoryOrder.get(b.category_key || '') ?? 99)
    );
    return list.filter((c) => (c.benefits?.length ?? 0) > 0);
  }, [data?.categories, categoryOrder]);

  const totalBenefits = countBenefits(data?.categories);

  const ctx = data?.assignment_context;
  const assignmentLabel = humanizeAssignmentTypeLabel(ctx?.assignment_type ?? undefined);
  const familyLabel = humanizeFamilyStatusLabel(ctx?.family_status ?? undefined);
  const versionLabel =
    data?.version_number != null && data.version_number > 0
      ? `Version ${data.version_number}`
      : data?.policy_version
        ? `Reference ${String(data.policy_version).slice(0, 8)}…`
        : '—';
  const effectiveLabel = data?.effective_date ? String(data.effective_date).slice(0, 10) : '—';

  // Friendly holding state while the assignment context is still loading, or if the
  // employee isn't yet linked to a company/assignment. (Must come AFTER all hooks —
  // an early return above them would call the hooks conditionally; LINT-3 rules-of-hooks.)
  if (!assignmentLoading && !assignmentId && linkedCount === 0) {
    return (
      <Card padding="lg" className="border-[#e2e8f0]">
        <p className="text-sm font-medium text-[#0b2b43] mb-1">No company linked yet</p>
        <p className="text-sm text-[#64748b]">
          Your company&apos;s relocation policy will appear here automatically once HR links your account to an assignment.
          No action is needed on your part — you&apos;ll be able to view your full benefit entitlements as soon as they&apos;ve set it up.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6" data-employee-policy-view="v1">
      {error && (
        <Alert variant="error" title="Unable to load">
          {error}
        </Alert>
      )}

      {loading ? (
        <Card padding="lg" className="border-[#e2e8f0]">
          <p className="text-sm text-[#64748b]">Loading your company policy…</p>
        </Card>
      ) : !data?.has_policy_config ? (
        <Card padding="lg" className="border-[#e2e8f0] bg-[#fafbfc]">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-2">No published policy yet</h2>
          <p className="text-sm text-[#475569] leading-relaxed max-w-2xl">
            {EMPTY_UNPUBLISHED} Your HR team may have a draft in progress — it
            becomes visible here as soon as they click <strong>Publish</strong>.
            Reach out to HR via <Link to={buildRoute('messages')} className="text-[#0b2b43] underline">Messages</Link>{' '}
            if you have benefit questions in the meantime.
          </p>
          {(assignmentLabel !== '—' || familyLabel !== '—') && (
            <p className="text-xs text-[#94a3b8] mt-4">
              Context we used: {assignmentLabel} · {familyLabel}
            </p>
          )}
        </Card>
      ) : totalBenefits === 0 ? (
        <>
          <Card padding="lg" className="border border-[#e2e8f0] bg-[#f8fafc]">
            <h2 className="text-sm font-semibold text-[#0b2b43] mb-3">Your situation</h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wide text-[#64748b]">Assignment type</dt>
                <dd className="font-medium text-[#0b2b43] mt-0.5">{assignmentLabel}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[#64748b]">Family status</dt>
                <dd className="font-medium text-[#0b2b43] mt-0.5">{familyLabel}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[#64748b]">Company policy</dt>
                <dd className="font-medium text-[#0b2b43] mt-0.5">{versionLabel}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[#64748b]">Effective date</dt>
                <dd className="font-medium text-[#0b2b43] mt-0.5">{effectiveLabel}</dd>
              </div>
            </dl>
          </Card>
          <Card padding="lg" className="border-[#e2e8f0] bg-white">
            <p className="text-sm text-[#475569] leading-relaxed max-w-2xl">
              Your employer has published a policy, but <strong>no allowance rows apply</strong> to your assignment
              and household context as we understand it today. If this looks wrong, contact your mobility or HR
              contact.
            </p>
          </Card>
        </>
      ) : (
        <>
          <Card padding="lg" className="border border-[#e2e8f0] bg-[#f8fafc]">
            <h2 className="text-sm font-semibold text-[#0b2b43] mb-3">What this page shows</h2>
            <p className="text-sm text-[#475569] leading-relaxed max-w-3xl mb-4">
              Below are the <strong>covered</strong> benefits from your company&apos;s published compensation &amp;
              allowance policy that <strong>apply to you</strong> for this assignment. This page is{' '}
              <strong>read-only</strong>—only your employer can change policy rules.
            </p>
            <div className="rounded-lg border border-[#e2e8f0] bg-white px-4 py-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mb-2">
                Case &amp; policy context
              </h3>
              <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-[#64748b]">Assignment type</dt>
                  <dd className="font-medium text-[#0b2b43] mt-0.5">{assignmentLabel}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[#64748b]">Family status</dt>
                  <dd className="font-medium text-[#0b2b43] mt-0.5">{familyLabel}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[#64748b]">Company policy version</dt>
                  <dd className="font-medium text-[#0b2b43] mt-0.5">{versionLabel}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[#64748b]">Effective date</dt>
                  <dd className="font-medium text-[#0b2b43] mt-0.5">{effectiveLabel}</dd>
                </div>
              </dl>
            </div>
          </Card>

          {servicesPolicyCtx?.has_policy && servicesPolicyCtx.policy_surface && (
            <Card padding="lg" className="border border-[#e2e8f0] bg-white">
              <h2 className="text-base font-semibold text-[#0b2b43]">
                {servicesPolicyCtx.policy_surface.title?.trim() || 'Compensation & allowance (published)'}
              </h2>
              <div className="text-xs text-[#64748b] mt-2 space-y-0.5">
                {servicesPolicyCtx.policy_surface.company_name && (
                  <div>Company: {servicesPolicyCtx.policy_surface.company_name}</div>
                )}
                <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {servicesPolicyCtx.policy_surface.version != null && (
                    <span>Version {servicesPolicyCtx.policy_surface.version}</span>
                  )}
                  {servicesPolicyCtx.policy_surface.effective_date && (
                    <span>Effective {String(servicesPolicyCtx.policy_surface.effective_date).slice(0, 10)}</span>
                  )}
                </div>
                {servicesPolicyCtx.resolution_context && (
                  <div className="mt-2 text-[#475569]">
                    Your profile for policy matching:{' '}
                    {humanizeAssignmentTypeLabel(
                      normalizeAssignmentType(servicesPolicyCtx.resolution_context.assignment_type ?? '') ?? undefined
                    )}
                    {' · '}
                    {humanizeFamilyStatusLabel(
                      normalizeFamilyStatus(servicesPolicyCtx.resolution_context.family_status ?? '') ?? undefined
                    )}
                  </div>
                )}
              </div>
              <p className="text-xs text-[#64748b] mt-2 leading-relaxed">
                This matrix, the Services flow, and HR Policy use the same published policy snapshot where available.
              </p>
              <div className="mt-4 p-3 bg-[#eef4f8] border border-[#0b2b43]/20 rounded-lg">
                <p className="text-sm text-[#4b5563] mb-2">
                  Full policy wording and benefit details are on the HR Policy page. For questions, contact your
                  company HR.
                </p>
                <Link to={buildRoute('hrPolicy')}>
                  <Button variant="outline" className="mt-1">
                    View HR Policy &amp; limits
                  </Button>
                </Link>
              </div>
            </Card>
          )}

          <PolicyGlossarySection variant="employee" />

          {/* Theme-grouped read-only summary mirroring the HR-side
              "What employees see today" card. The employee endpoint
              already filters to covered + applicable rows, so every
              row in `data.categories` is something HR has approved
              for this assignment & level. */}
          {sortedCategories.length > 0 && (
            <Card padding="lg" className="border-[#e2e8f0]">
              <PolicyTopicSummaryList
                matrixPayload={
                  {
                    ...(data ?? {}),
                    categories: sortedCategories,
                  } as PolicyConfigWorkingPayload
                }
                heading="Your benefits at a glance"
                subtitle="Approved benefits for your assignment, grouped by theme. Click a theme to see the individual benefit rows. Read-only — only your employer can change policy."
              />
            </Card>
          )}

          <details className="rounded-xl border border-[#e2e8f0] bg-white shadow-sm">
            <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
              <div className="flex items-center justify-between gap-3">
                <span className="text-base font-semibold text-[#0b2b43]">
                  ▸ See per-benefit detail
                </span>
                <span className="text-xs text-[#64748b]">cap, frequency, notes for each row</span>
              </div>
            </summary>
            <div className="px-5 pb-5 space-y-6">
              {sortedCategories.map((cat) => (
                <Card key={cat.category_key} padding="lg" className="border-[#e2e8f0]">
                  <h2 className="text-lg font-semibold text-[#0b2b43] mb-4 pb-2 border-b border-[#f1f5f9]">
                    {(POLICY_CONFIG_CATEGORIES.find((c) => c.key === cat.category_key)?.label) ??
                      cat.category_label ??
                      'Benefits'}
                  </h2>
                  <ul className="space-y-4">
                    {(cat.benefits ?? []).map((b) => (
                      <BenefitReadOnlyCard key={`${cat.category_key}-${b.benefit_key}`} b={b} />
                    ))}
                  </ul>
                </Card>
              ))}
            </div>
          </details>
        </>
      )}
    </div>
  );
};

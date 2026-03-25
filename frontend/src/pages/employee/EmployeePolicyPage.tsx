import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card, Container } from '../../components/antigravity';
import { employeeAPI, policyConfigMatrixAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import type { PolicyConfigBenefitRow, PolicyConfigCategoryBlock } from '../../features/policy-config/types';
import { POLICY_CONFIG_CATEGORIES } from '../../features/policy-config/constants';
import {
  humanizeAssignmentTypeLabel,
  humanizeFamilyStatusLabel,
  normalizeAssignmentType,
  normalizeFamilyStatus,
} from '../../features/policy-config/policyTargeting';
import {
  EMPLOYEE_POLICY_PER_BENEFIT_EXPLANATION,
  formatBenefitBudgetSummary,
  humanizeUnitFrequency,
  mergeNotesAndConditions,
} from './employeePolicyMatrixDisplay';
import { glossaryIdForBenefitKey } from '../../features/policy-config/compensationGlossary';
import { PolicyGlossarySection } from '../../features/policy-config/PolicyGlossarySection';
import { TermHelpIcon } from '../../features/policy-config/TermHelpIcon';

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

function resolveCategoryTitle(cat: PolicyConfigCategoryBlock): string {
  const k = cat.category_key || '';
  const canon = POLICY_CONFIG_CATEGORIES.find((c) => c.key === k);
  return canon?.label ?? cat.category_label ?? 'Benefits';
}

function countBenefits(cats: PolicyConfigCategoryBlock[] | undefined): number {
  return (cats ?? []).reduce((acc, c) => acc + (c.benefits?.length ?? 0), 0);
}

function BenefitReadOnlyCard({ b }: { b: PolicyConfigBenefitRow }) {
  const budget = formatBenefitBudgetSummary(b);
  const unit = humanizeUnitFrequency(b.unit_frequency);
  const notesBlock = mergeNotesAndConditions(b);
  const glossaryId = glossaryIdForBenefitKey(b.benefit_key);

  return (
    <li className="rounded-xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
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

/**
 * Employee read-only view of the published Compensation &amp; Allowance matrix.
 * Route: /employee/policy — data from GET /api/employee/policy-config (covered + applicable rows only).
 */
export const EmployeePolicyPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { assignmentId: contextAssignmentId } = useEmployeeAssignment();
  const assignmentId = searchParams.get('assignmentId') || contextAssignmentId || undefined;
  const caseId = searchParams.get('caseId') || undefined;
  const assignmentTypeRaw = searchParams.get('assignmentType');
  const familyStatusRaw = searchParams.get('familyStatus');
  const assignmentType = normalizeAssignmentType(assignmentTypeRaw ?? '') ?? undefined;
  const familyStatus = normalizeFamilyStatus(familyStatusRaw ?? '') ?? undefined;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<EmployeePolicyPayload | null>(null);
  const [servicesPolicyCtx, setServicesPolicyCtx] = useState<ServicesPolicyContext | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await policyConfigMatrixAPI.employeeGet({
        assignmentId,
        caseId,
        assignmentType,
        familyStatus,
      });
      setData(res as EmployeePolicyPayload);
    } catch {
      setError('We could not load your compensation policy right now. Please try again later.');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [assignmentId, caseId, assignmentType, familyStatus]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (!assignmentId) {
      setServicesPolicyCtx(null);
      return;
    }
    let cancelled = false;
    employeeAPI
      .getServicesPolicyContext(assignmentId)
      .then((ctx) => {
        if (!cancelled) setServicesPolicyCtx(ctx);
      })
      .catch(() => {
        if (!cancelled) setServicesPolicyCtx(null);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  const categoryOrder = useMemo(
    () => new Map(POLICY_CONFIG_CATEGORIES.map((c, i) => [c.key, i])),
    []
  );

  const sortedCategories = useMemo(() => {
    const list = [...(data?.categories ?? [])].sort(
      (a, b) =>
        (categoryOrder.get(a.category_key || '') ?? 99) - (categoryOrder.get(b.category_key || '') ?? 99)
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

  return (
    <AppShell title="Compensation & allowance" subtitle="Approved policy for your assignment">
      <Container maxWidth="xl" className="py-8 space-y-6">
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
            <p className="text-sm text-[#475569] leading-relaxed max-w-2xl">{EMPTY_UNPUBLISHED}</p>
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

            <div className="space-y-6">
              {sortedCategories.map((cat) => (
                <Card key={cat.category_key} padding="lg" className="border-[#e2e8f0]">
                  <h2 className="text-lg font-semibold text-[#0b2b43] mb-4 pb-2 border-b border-[#f1f5f9]">
                    {resolveCategoryTitle(cat)}
                  </h2>
                  <ul className="space-y-4">
                    {(cat.benefits ?? []).map((b) => (
                      <BenefitReadOnlyCard key={`${cat.category_key}-${b.benefit_key}`} b={b} />
                    ))}
                  </ul>
                </Card>
              ))}
            </div>
          </>
        )}
      </Container>
    </AppShell>
  );
};
